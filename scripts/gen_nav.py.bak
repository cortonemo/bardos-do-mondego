#!/usr/bin/env python3
from pathlib import Path
import yaml

MKDOCS_FILE = Path("mkdocs.yml")
DOCS_DIR = Path("docs")
AUTO_NAV_START = "# BEGIN AUTO_NAV"
AUTO_NAV_END   = "# END AUTO_NAV"

TOP_LEVEL_ORDER = [
    "adventures","locations","loot","monsters",
    "notable_figures","npc","organizations","pc","rumors",
]
EXCLUDE_TOP = {"css"}
DISPLAY = {
    "adventures":"Adventures","locations":"Locations","loot":"Loot",
    "monsters":"Monsters","notable_figures":"Notable Figures","npc":"NPCs",
    "organizations":"Organizations","pc":"PCs","rumors":"Rumors","dm":"🔑 DM Access",
}

def nice(name:str)->str:
    return DISPLAY.get(name, name.replace("_"," ").title())

def rel(p:Path)->str:
    return str(p.relative_to(DOCS_DIR)).replace("\\","/")

def build_dir(path:Path)->list:
    items = []
    # NÃO adiciona index.md aqui; 'navigation.indexes' cuida do clique no pai
    # subpastas
    for d in sorted([p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")], key=lambda p:p.name.lower()):
        items.append({ nice(d.name): build_dir(d) })
    # ficheiros (não-index)
    for f in sorted([p for p in path.iterdir()
                     if p.is_file() and p.suffix.lower()==".md" and p.name!="index.md" and not p.name.startswith(".")],
                    key=lambda p:p.name.lower()):
        items.append(rel(f))
    return items

def build_full_nav()->list:
    nav = [{"Home":"index.md"}]
    handled = set()
    for name in TOP_LEVEL_ORDER:
        p = DOCS_DIR / name
        if p.is_dir():
            nav.append({ nice(name): build_dir(p) })
            handled.add(name)
    others = sorted([p for p in DOCS_DIR.iterdir()
                     if p.is_dir() and not p.name.startswith(".")
                     and p.name not in handled and p.name not in EXCLUDE_TOP
                     and p.name.lower()!="dm"], key=lambda p:p.name.lower())
    for d in others:
        nav.append({ nice(d.name): build_dir(d) })
    dm = DOCS_DIR / "dm"
    if dm.is_dir():
        nav.append({ nice("dm"): build_dir(dm) })
    return nav

def insert_nav_into_mkdocs(nav:list)->None:
    # dump só a LISTA
    nav_yaml = yaml.dump(nav, sort_keys=False, allow_unicode=True).rstrip("\n")
    # indentar 2 espaços porque está dentro da chave 'nav:'
    indented = "\n".join(("  "+line) if line.strip() else line for line in nav_yaml.splitlines())
    text = MKDOCS_FILE.read_text(encoding="utf-8")
    start = text.find(AUTO_NAV_START)
    end   = text.find(AUTO_NAV_END)
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("AUTO_NAV markers not found or malformed in mkdocs.yml")
    before = text[: start + len(AUTO_NAV_START)]
    after  = text[end:]
    new_text = before + "\n" + indented + "\n" + after
    MKDOCS_FILE.write_text(new_text, encoding="utf-8")
    print("mkdocs.yml nav updated.")

if __name__ == "__main__":
    insert_nav_into_mkdocs(build_full_nav())
