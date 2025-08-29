#!/usr/bin/env python3
from pathlib import Path
import yaml, sys, re

# --- config ---
MKDOCS_FILE = Path("mkdocs.yml")
DOCS_DIR = Path("docs")

AUTO_NAV_START = "# BEGIN AUTO_NAV"
AUTO_NAV_END   = "# END AUTO_NAV"

# Preferred top order if present, dm goes last automatically
TOP_LEVEL_ORDER = [
    "adventures", "lore", "locations", "loot", "monsters",
    "notable_figures", "npc", "organizations", "pc", "rumors"
]

# Prune anywhere
PRUNE_DIRS = {
    ".obsidian", "assets", "images", "image", "img", "imgs", "timelines", 
    "media", "static", "css", ".summary", ".a_atualizar"
}

# Hide whole folder if one of these files exists inside it
HIDE_SENTINELS = {".nonav", ".navignore"}

INCLUDE_EXT = ".md"

# --- helpers ---
def nice(name: str) -> str:
    n = name.strip().replace("_", " ").replace("-", " ")
    return n[:1].upper() + n[1:] if n else n

def skip_dir_name(name: str) -> bool:
    n = name.lower()
    return n in PRUNE_DIRS or n.startswith(".") or n.startswith("_")

def dir_has_sentinel(p: Path) -> bool:
    return any((p / s).exists() for s in HIDE_SENTINELS)

def is_md_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() == INCLUDE_EXT

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
def page_hidden(p: Path) -> bool:
    if not is_md_file(p):
        return True
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return False
    try:
        data = yaml.safe_load(m.group(1)) or {}
        return bool(isinstance(data, dict) and data.get("nav") is False)
    except Exception:
        return False

def rel_entry(p: Path, base: Path) -> dict:
    return {nice(p.stem): str(p.relative_to(base)).replace("\\", "/")}

def build_virtual_dash_group(container: Path, base: Path) -> list:
    """
    Build a virtual group from a real folder named '-'.
    The '-' folder itself is hidden, only its children appear under a group labeled '-'.
    """
    if not container.is_dir() or container.name != "-":
        return []
    if dir_has_sentinel(container):
        return []

    children = []
    for d in sorted([x for x in container.iterdir() if x.is_dir() and not skip_dir_name(x.name) and not dir_has_sentinel(x)],
                    key=lambda x: x.name.lower()):
        sec = build_dir(d, base)
        if sec:
            children.append({nice(d.name): sec})

    # also allow markdown pages directly inside '-' to show within the group
    files = sorted(
        [f for f in container.iterdir()
         if is_md_file(f) and f.name.lower() != "index.md" and not f.name.startswith(".") and not page_hidden(f)],
        key=lambda f: f.name.lower()
    )
    for f in files:
        children.append(rel_entry(f, base))

    return children

def build_dir(section_dir: Path, base: Path) -> list:
    """
    Build nav for a directory, honoring:
      prune rules, .nonav, page nav:false, index.md first, flatten single 'list',
      and auto virtual groups for any child folder literally named '-'.
    """
    if not section_dir.exists() or not section_dir.is_dir():
        return []
    if skip_dir_name(section_dir.name) or dir_has_sentinel(section_dir):
        return []

    # flatten single child named 'list'
    subs_all = [d for d in section_dir.iterdir() if d.is_dir()]
    if len(subs_all) == 1 and subs_all[0].name.lower() == "list":
        d = subs_all[0]
        if not skip_dir_name(d.name) and not dir_has_sentinel(d):
            section_dir = d

    items = []

    # index.md first
    idx = section_dir / "index.md"
    if idx.exists() and is_md_file(idx) and not page_hidden(idx):
        items.append(rel_entry(idx, base))

    # first, handle a child folder named '-' as a virtual group
    dash_container = section_dir / "-"
    dash_group = build_virtual_dash_group(dash_container, base)
    # subfolders excluding '-' and pruned
    subdirs = sorted(
        [d for d in section_dir.iterdir()
         if d.is_dir()
         and d.name != "-"
         and not skip_dir_name(d.name)
         and not dir_has_sentinel(d)],
        key=lambda d: d.name.lower()
    )
    for d in subdirs:
        child = build_dir(d, base)
        if child:
            items.append({nice(d.name): child})

    # markdown files except index.md
    files = sorted(
        [f for f in section_dir.iterdir()
         if is_md_file(f) and f.name.lower() != "index.md"
         and not f.name.startswith(".") and not page_hidden(f)],
        key=lambda f: f.name.lower()
    )
    for f in files:
        items.append(rel_entry(f, base))

    # append the virtual '-' group last within this section, if it has content
    if dash_group:
        items.append({"-": dash_group})

    return items

def build_full_nav() -> list:
    if not DOCS_DIR.is_dir():
        print("docs/ not found", file=sys.stderr)
        sys.exit(1)

    nav = []
    handled = set()

    # Home
    home = DOCS_DIR / "index.md"
    if home.exists() and is_md_file(home) and not page_hidden(home):
        nav.append({"Home": str(home.relative_to(DOCS_DIR)).replace("\\", "/")})

    # top level virtual group from docs/- if present
    top_dash_children = build_virtual_dash_group(DOCS_DIR / "-", DOCS_DIR)

    # ordered sections, excluding dm and anything that lives under top-level '-'
    for name in TOP_LEVEL_ORDER:
        if name.lower() in handled:
            continue
        p = DOCS_DIR / name
        # skip if this name actually resides under docs/- to avoid duplication
        if (DOCS_DIR / "-" / name).is_dir():
            continue
        sec = build_dir(p, DOCS_DIR) if p.is_dir() else []
        if sec:
            nav.append({nice(name): sec})
            handled.add(name.lower())

    # remaining top-level sections, excluding dm, pruned, sentinel, and those under docs/-
    others = sorted(
        [p for p in DOCS_DIR.iterdir()
         if p.is_dir()
         and p.name.lower() not in handled
         and p.name.lower() != "dm"
         and p.name != "-"
         and not skip_dir_name(p.name)
         and not dir_has_sentinel(p)],
        key=lambda p: p.name.lower()
    )
    for d in others:
        # if this dir also exists under docs/-, prefer grouping and skip here
        if (DOCS_DIR / "-" / d.name).is_dir():
            continue
        sec = build_dir(d, DOCS_DIR)
        if sec:
            nav.append({nice(d.name): sec})
            handled.add(d.name.lower())

    # finally, inject the top-level virtual '-' group if it has content
    if top_dash_children:
        nav.append({"-": top_dash_children})

    # dm last
    dm = DOCS_DIR / "dm"
    if dm.is_dir() and not dir_has_sentinel(dm) and not skip_dir_name(dm.name):
        dm_sec = build_dir(dm, DOCS_DIR)
        if dm_sec:
            nav.append({"🔑 DM Access": dm_sec})

    return nav

def insert_nav_into_mkdocs(nav: list) -> None:
    nav_yaml = yaml.safe_dump(nav, sort_keys=False, allow_unicode=True).rstrip("\n")
    indented = "\n".join(("  " + line) if line.strip() else line for line in nav_yaml.splitlines())

    text = MKDOCS_FILE.read_text(encoding="utf-8")
    s, e = text.find(AUTO_NAV_START), text.find(AUTO_NAV_END)
    if s == -1 or e == -1 or e <= s:
        raise RuntimeError("AUTO_NAV markers not found or malformed in mkdocs.yml")
    new = text[: s + len(AUTO_NAV_START)] + "\n" + indented + "\n" + text[e:]
    MKDOCS_FILE.write_text(new, encoding="utf-8")
    print("mkdocs.yml nav updated.")

if __name__ == "__main__":
    insert_nav_into_mkdocs(build_full_nav())
