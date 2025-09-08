import tkinter as tk
from tkinter import filedialog, messagebox
import os

def fix_mojibake(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except UnicodeDecodeError:
        return text  # Return original if it can’t be fixed

def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            original = f.read()
        fixed = fix_mojibake(original)
        if original != fixed:
            backup = file_path + ".bak"
            os.rename(file_path, backup)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed)
            return f"[FIXED] {file_path}"
        else:
            return f"[OK] {file_path}"
    except Exception as e:
        return f"[ERROR] {file_path}: {e}"

def process_directory(root_dir, extensions={'.md', '.markdown', '.txt', '.yml', '.yaml'}):
    logs = []
    for foldername, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in extensions):
                full_path = os.path.join(foldername, filename)
                logs.append(process_file(full_path))
    return logs

def browse_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        logs = process_directory(folder_selected)
        result_window = tk.Toplevel(root)
        result_window.title("Processing Results")
        text_area = tk.Text(result_window, wrap=tk.WORD)
        text_area.pack(expand=True, fill='both')
        for log in logs:
            text_area.insert(tk.END, log + "\n")

# GUI setup
root = tk.Tk()
root.title("Mojibake Fixer")

frame = tk.Frame(root, padx=20, pady=20)
frame.pack()

label = tk.Label(frame, text="Select a folder to fix UTF-8 mojibake:")
label.pack(pady=(0, 10))

browse_button = tk.Button(frame, text="Browse Folder", command=browse_folder)
browse_button.pack()

root.mainloop()
