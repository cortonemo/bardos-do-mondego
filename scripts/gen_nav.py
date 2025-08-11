import os
import yaml
from pathlib import Path

MKDOCS_FILE = Path("mkdocs.yml")
DOCS_DIR = Path("docs")
AUTO_NAV_START = "# AUTO_NAV_START"
AUTO_NAV_END = "# AUTO_NAV_END"

def build_nav_for_dir(directory: Path):
    """Recursively build nav entries for a given directory."""
    items = []
    entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            # Recurse for subfolder
            items.append({entry.name: build_nav_for_dir(entry)})
        elif entry.suffix.lower() == ".md":
            # Link .md file
            items.append({entry.stem: str(entry.relative_to(DOCS_DIR)).replace("\\", "/")})
    return items

def build_full_nav():
    """Build full nav with public sections first, DM last."""
    nav = []
    for entry in sorted(DOCS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        if entry.name.lower() == "dm":
            continue  # handled last
        nav.append({entry.name: build_nav_for_dir(entry)})

    # Handle DM section
    dm_path = DOCS_DIR / "dm"
    if dm_path.exists():
        nav.append({"🔑 DM Access": build_nav_for_dir(dm_path)})

    return nav

def insert_nav_into_mkdocs(nav):
    """Replace the AUTO_NAV block in mkdocs.yml with new nav."""
    nav_yaml = yaml.dump({"nav": nav}, sort_keys=False, allow_unicode=True)
    with MKDOCS_FILE.open(encoding="utf-8") as f:
        lines = f.readlines()

    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == AUTO_NAV_START:
            start_idx = i
        elif line.strip() == AUTO_NAV_END:
            end_idx = i

    if start_idx is None or end_idx is None:
        raise RuntimeError("AUTO_NAV_START or AUTO_NAV_END markers not found in mkdocs.yml")

    # Keep markers, replace content between them
    new_lines = lines[: start_idx + 1]
    for line in nav_yaml.splitlines():
        new_lines.append(line + "\n")
    new_lines.extend(lines[end_idx:])

    with MKDOCS_FILE.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"Updated nav in {MKDOCS_FILE}")

if __name__ == "__main__":
    nav = build_full_nav()
    insert_nav_into_mkdocs(nav)
