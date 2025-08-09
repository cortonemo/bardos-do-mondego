# scripts/gen_indexes.py
from pathlib import Path
import mkdocs_gen_files

DOCS = Path("docs")

SKIP_DIRS = {".obsidian", "site", "image DL", "__pycache__"}

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

def nice_title(p: Path) -> str:
    name = TITLE_MAP.get(p.name, p.name)
    return name.replace("_", " ").strip().title()

def write_index(dir_path: Path) -> None:
    rel_dir = dir_path.relative_to(DOCS).as_posix()
    lines = [f"# {nice_title(dir_path)}", ""]

    subs = sorted([d for d in dir_path.iterdir()
                   if d.is_dir() and d.name not in SKIP_DIRS],
                  key=lambda x: x.name.lower())
    files = sorted([f for f in dir_path.iterdir()
                    if f.is_file() and f.suffix.lower() == ".md" and f.name.lower() != "index.md"],
                   key=lambda x: x.name.lower())

    for d in subs:
        lines.append(f"- [{nice_title(d)}]({d.name}/)")
    for f in files:
        title = f.stem.replace("_", " ").strip().title()
        lines.append(f"- [{title}]({f.name})")
    lines.append("")

    with mkdocs_gen_files.open(f"{rel_dir}/index.md", "w") as fh:
        fh.write("\n".join(lines))


# Generate indexes for all folders under docs/
for d in DOCS.rglob("*"):
    if d.is_dir() and d.name not in SKIP_DIRS:
        write_index(d)
