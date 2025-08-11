#!/usr/bin/env python3
"""
Generate MkDocs nav from the docs/ tree and inject it into mkdocs.yml
between the AUTO_NAV_START / AUTO_NAV_END markers.

Design:
- "Home: index.md" first.
- Public sections in preferred order, then any other top-level dirs (except excluded).
- DM section grouped at the end under "🔑 DM Access".
- Every directory is a clickable page: we always include its index.md
  even if it will be created in-memory by gen-files during build.
"""

from pathlib import Path
import yaml

MKDOCS_FILE = Path("mkdocs.yml")
DOCS_DIR = Path("docs")
AUTO_NAV_START = "# AUTO_NAV_START"
AUTO_NAV_END = "# AUTO_NAV_END"

# Order for known public sections; anything not listed gets appended alphabetically after these.
TOP_LEVEL_ORDER = [
    "adventures", "locations", "loot", "monsters",
    "notable_figures", "npc", "organizations", "pc", "rumors",
]

# Top-level folders to keep out of the nav entirely.
EXCLUDE_TOP = {"css"}

# Display names
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
    """docs-relative POSIX path."""
    return str(p.relative_to(DOCS_DIR)).replace("\\", "/")

def build_dir(path: Path) -> list:
    """
    Build a nav list for a directory:
    - index.md (always first, even if not on disk; gen-files may create it)
    - subdirectories (sorted)
    - files (sorted, .md only, excluding index.md)
    """
    items: list = []

    # clickable parent page
    items.append(rel(path / "index.md"))

    # subfolders
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
    """Compose the whole nav structure."""
    nav: list = [{"Home": "index.md"}]

    # 1) Known sections in the prescribed order
    handled = set()
    for name in TOP_LEVEL_ORDER:
        p = DOCS_DIR / name
        if p.is_dir():
            nav.append({nice(name): build_dir(p)})
            handled.add(name)

    # 2) Any other top-level dirs (alphabetical), excluding dm and excluded
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

    # 3) DM section last, grouped
    dm = DOCS_DIR / "dm"
    if dm.is_dir():
        nav.append({nice("dm"): build_dir(dm)})

    return nav

def insert_nav_into_mkdocs(nav: list) -> None:
    """Replace the AUTO_NAV block in mkdocs.yml with the new nav."""
    nav_yaml = yaml.dump({"nav": nav}, sort_keys=False, allow_unicode=True)

    text = MKDOCS_FILE.read_text(encoding="utf-8")
    start = text.find(AUTO_NAV_START)
    end = text.find(AUTO_NAV_END)
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("AUTO_NAV markers not found or malformed in mkdocs.yml")

    # Keep markers, replace content between them (including trailing newline handling)
    before = text[: start + len(AUTO_NAV_START)]
    after = text[end:]
    replacement = "\n" + nav_yaml.rstrip() + "\n"
    new_text = before + replacement + after
    MKDOCS_FILE.write_text(new_text, encoding="utf-8")
    print("mkdocs.yml nav updated.")

if __name__ == "__main__":
    nav = build_full_nav()
    insert_nav_into_mkdocs(nav)
