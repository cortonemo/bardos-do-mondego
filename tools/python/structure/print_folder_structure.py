import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox


def print_structure(root: Path, prefix: str = "") -> list[str]:
    output = []
    entries = sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    files = [e for e in entries if e.is_file()]
    dirs = [e for e in entries if e.is_dir()]

    for i, folder in enumerate(dirs):
        connector = "└── " if i == len(dirs) - 1 and not files else "├── "
        output.append(prefix + connector + f"📂 {folder.name}/")
        output.extend(print_structure(folder, prefix + ("    " if connector == "└── " else "│   ")))

    for j, file in enumerate(files):
        connector = "└── " if j == len(files) - 1 else "├── "
        output.append(prefix + connector + f"📄 {file.name}")

    return output


def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        path = Path(folder)
        structure = [f"📁 Root: {path}"] + print_structure(path)
        output_box.delete(1.0, tk.END)
        output_box.insert(tk.END, "\n".join(structure))
        output_box.tag_add("content", "1.0", tk.END)
        root.current_structure = structure
        root.current_path = path


def save_to_txt():
    if not hasattr(root, "current_structure"):
        messagebox.showwarning("No Structure", "Please select a folder first.")
        return

    save_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt")],
        initialfile=f"{root.current_path.name}_structure.txt"
    )

    if save_path:
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(root.current_structure))
            messagebox.showinfo("Success", f"Structure saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")


# GUI setup
root = tk.Tk()
root.title("Folder Structure Viewer")
root.geometry("700x600")

frame = tk.Frame(root)
frame.pack(pady=10)

choose_btn = tk.Button(frame, text="Choose Folder", command=choose_folder, font=("Segoe UI", 12))
choose_btn.pack(side=tk.LEFT, padx=10)

save_btn = tk.Button(frame, text="Save to TXT", command=save_to_txt, font=("Segoe UI", 12))
save_btn.pack(side=tk.LEFT, padx=10)

output_box = scrolledtext.ScrolledText(root, width=100, height=35, font=("Consolas", 10))
output_box.pack(padx=10, pady=10)

root.mainloop()
