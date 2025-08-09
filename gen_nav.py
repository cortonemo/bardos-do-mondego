import os, sys, yaml, re
from pathlib import Path

ROOT = Path("docs")
SKIP_DIRS = {".obsidian", "image DL", "site", "__pycache__"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TITLE_MAP = {
    "dm": "DM",
    "adventures": "Aventuras",
    "Locations": "Localizações",
    "loot": "Loot",
    "monsters": "Monstros",
    "npc": "NPCs",
    "organizations": "Organizações",
    "pc": "PCs",
    "rumors": "Rumores",
    "Sessions": "Sessões",
    "summary": "Resumos",
    "tables": "Tabelas",
    "notable figures": "Figuras Notáveis",
}

def title_from_file(p: Path) -> str:
    name = p.stem.replace("_", " ").strip()
    return name[:1].upper() + name[1:]

def build_section(dir_path: Path):
    items = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if entry.is_dir():
            if entry.name in SKIP_DIRS: 
                continue
            sub = build_section(entry)
            if sub:
                items.append({TITLE_MAP.get(entry.name, title_from_file(entry)): sub})
        else:
            if entry.suffix.lower() != ".md" or entry.suffix.lower() in SKIP_EXT:
                continue
            rel = entry.relative_to(ROOT).as_posix()
            items.append({title_from_file(entry): rel})
    return items

def main():
    nav = []
    # Home
    home = ROOT / "home.md"
    index = ROOT / "index.md"
    if index.exists():
        nav.append({"Início": "index.md"})
    elif home.exists():
        nav.append({"Início": "home.md"})
    # Players (pc)
    if (ROOT / "pc").exists():
        nav.append({"Jogadores": build_section(ROOT / "pc")})
    # DM block
    dm = ROOT / "dm"
    if dm.exists():
        dm_nav = build_section(dm)
        nav.append({"DM": dm_nav})
    data = {"nav": nav}
    print(yaml.dump(data, allow_unicode=True, sort_keys=False))

if __name__ == "__main__":
    main()
