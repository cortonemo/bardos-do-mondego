import os
import re
import unicodedata

def remove_accents(text):
    # Converts characters like ã → a, ç → c, etc.
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def normalize_filename(name):
    # Remove accents, replace spaces with underscores, lowercase
    name = remove_accents(name)
    name = name.replace(" ", "_").lower()
    return name

def rename_md_files(folder):
    renamed = {}
    for root, dirs, files in os.walk(folder):
        for filename in files:
            if filename.endswith(".md"):
                normalized_name = normalize_filename(filename)
                if normalized_name != filename:
                    old_path = os.path.join(root, filename)
                    new_path = os.path.join(root, normalized_name)
                    os.rename(old_path, new_path)
                    print(f"[FILE RENAMED] {filename} → {normalized_name}")
                    renamed[filename[:-3]] = normalized_name[:-3]
    return renamed

def fix_obsidian_links(folder):
    wikilink_pattern = re.compile(r"\[\[([^\[\]]+)\]\]")

    for root, dirs, files in os.walk(folder):
        for filename in files:
            if filename.endswith(".md"):
                path = os.path.join(root, filename)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                changes = []

                def replace_link(match):
                    original = match.group(1)
                    transformed = normalize_filename(original)
                    if transformed != original:
                        changes.append((original, transformed))
                    return f"[[{transformed}]]"

                new_content = wikilink_pattern.sub(replace_link, content)

                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)

                    for orig, trans in changes:
                        print(f"[LINK CHANGED] In {filename}: [[{orig}]] → [[{trans}]]")
                    print(f"[UPDATED FILE] {filename}\n")

if __name__ == "__main__":
    docs_path = "."  # Use "." if running from inside /docs/DM
    print("🔧 Renaming files (accents, spaces, lowercase)...")
    rename_md_files(docs_path)
    print("\n🔍 Fixing internal wiki-style links...")
    fix_obsidian_links(docs_path)
