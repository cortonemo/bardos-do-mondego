#!/usr/bin/env python3
from pathlib import Path
import yaml

MKDOCS_FILE = Path("mkdocs.yml")
DOCS_DIR = Path("docs")

# match mkdocs.yml exactly
AUTO_NAV_START = "# BEGIN AUTO_NAV"
AUTO_NAV_END = "# END AUTO_NAV"

TOP_LEVEL_ORDER = [
    "adventures", "locations", "loot", "monsters",
    "notable_figures", "npc", "organizations", "pc", "rumors",
]
EXCLUDE_TOP = {"css"}
DISPLAY = {
    "adventures": "Adventures",
    "locations": "Locations",
    "loot": "Loot",
    "monsters": "Monsters",
    "notable_figures": "Notable Figures",
    "npc": "NPCs",
    "organizations": "Organizations",
    "pc": "PCs",
    "rumors": "Rumors",
    "dm": "🔑 DM Access",
}

def nice(name: str) -> str:
    return DISPLAY.get(name, name.replace("_", " ").title())

def rel(p: Path) -> str:
    return str(p.relative_to(DOCS_DIR)).replace("\\", "/")

def build_dir(path: Path) -> list:
    items = []
    # always include index.md, even if gen-files creates it later
    items.append(rel(path / "index.md"))

    # subdirs
    subdirs = sorted(
        [p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.name.lower(),
    )
    for d in subdirs:
        items.append({nice(d.name): build_dir(d)})

    # files (non-index)
    files = sorted(
        [
            p for p in path.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".md"
            and p.name != "index.md"
            and not p.name.startswith(".")
        ],
        key=lambda p: p.name.lower(),
    )
    for fpath in files:
        items.append(rel(fpath))
    return items

def build_full_nav() -> list:
    nav = [{"Home": "index.md"}]

    handled = set()
    for name in TOP_LEVEL_ORDER:
        p = DOCS_DIR / name
        if p.is_dir():
            nav.append({nice(name): build_dir(p)})
            handled.add(name)

    others = sorted(
        [
            p for p in DOCS_DIR.iterdir()
            if p.is_dir()
            and not p.name.startswith(".")
            and p.name not in handled
            and p.name not in EXCLUDE_TOP
            and p.name.lower() != "dm"
        ],
        key=lambda p: p.name.lower(),
    )
    for d in others:
        nav.append({nice(d.name): build_dir(d)})

    dm = DOCS_DIR / "dm"
    if dm.is_dir():
        nav.append({nice("dm"): build_dir(dm)})

    return nav

def insert_nav_into_mkdocs(nav: list) -> None:
    nav_yaml = yaml.dump({"nav": nav}, sort_keys=False, allow_unicode=True)

    text = MKDOCS_FILE.read_text(encoding="utf-8")
    start = text.find(AUTO_NAV_START)
    end = text.find(AUTO_NAV_END)
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("AUTO_NAV markers not found or malformed in mkdocs.yml")

    before = text[: start + len(AUTO_NAV_START)]
    after = text[end:]
    replacement = "\n" + nav_yaml.rstrip() + "\n"
    new_text = before + replacement + after
    MKDOCS_FILE.write_text(new_text, encoding="utf-8")
    print("mkdocs.yml nav updated.")

if __name__ == "__main__":
    nav = build_full_nav()
    insert_nav_into_mkdocs(nav)
