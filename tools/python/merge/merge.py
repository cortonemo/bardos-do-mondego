import os

# === CONFIGURATION ===
# Folder containing your Markdown files
INPUT_FOLDER = r"G:\Git\bardos-do-mondego\docs\dm\adventures\bullet"

# Output Markdown file
OUTPUT_FILE = r"G:\Git\bardos-do-mondego\sessões1a29.md"

# Separator between files in the final output
SEPARATOR = "\n\n---\n\n"

# === SCRIPT ===
def join_markdown_files(input_folder, output_file, separator):
    # Collect all .md files
    md_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".md")]
    md_files.sort()  # Optional: sort alphabetically

    if not md_files:
        print("No Markdown files found in", input_folder)
        return

    with open(output_file, "w", encoding="utf-8") as outfile:
        for idx, filename in enumerate(md_files):
            file_path = os.path.join(input_folder, filename)
            with open(file_path, "r", encoding="utf-8") as infile:
                content = infile.read().strip()
                outfile.write(content)
            if idx < len(md_files) - 1:
                outfile.write(separator)

    print(f"Joined {len(md_files)} files into {output_file}")

if __name__ == "__main__":
    join_markdown_files(INPUT_FOLDER, OUTPUT_FILE, SEPARATOR)
