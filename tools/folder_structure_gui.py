import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# --- Settings ---
ALLOWED_TOP_LEVEL = {"docs", "scripts", "tools"}
EXCLUDE_DIRS = {".git", ".github", ".obsidian", ".venv", "__pycache__"}
HIDDEN_PREFIX = "."  # skip any hidden files/folders

def is_repo_root(path: str) -> bool:
    return (
        os.path.isdir(os.path.join(path, ".git"))
        or os.path.isfile(os.path.join(path, "mkdocs.yml"))
    )

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Repo Structure Viewer (GUI)")
        self.geometry("940x640")
        self.folder_var = tk.StringVar()
        self.force_repo_var = tk.BooleanVar(value=True)   # prefer repo-mode
        self.show_sizes_var = tk.BooleanVar(value=False)
        self.running = False
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.X)

        ttk.Label(frm, text="Folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.folder_var, width=88).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Browse…", command=self.browse_folder).grid(row=0, column=2)

        opts = ttk.Frame(frm)
        opts.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10,0))
        ttk.Checkbutton(opts, text="Repo mode (only docs/, scripts/, tools/)", variable=self.force_repo_var).grid(row=0, column=0, padx=(0,12))
        ttk.Checkbutton(opts, text="Show file sizes", variable=self.show_sizes_var).grid(row=0, column=1, padx=(0,12))

        runbar = ttk.Frame(frm)
        runbar.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10,0))
        self.btn_run = ttk.Button(runbar, text="Scan Structure", command=self.run)
        self.btn_run.grid(row=0, column=0)
        ttk.Button(runbar, text="Clear Log", command=self.clear_log).grid(row=0, column=1, padx=8)
        ttk.Button(runbar, text="Quit", command=self.destroy).grid(row=0, column=2)

        frm.columnconfigure(1, weight=1)

        self.log = ScrolledText(self, height=26, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        # log styles to match your other tool
        self.log.tag_configure("ok", foreground="#0a7f00")
        self.log.tag_configure("warn", foreground="#a15c00")
        self.log.tag_configure("err", foreground="#a10000")
        self.log.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
        self._log("Ready. Select your repo root (e.g., bardos-do-mondego) and click Scan.\n", "bold")

    # ---------- Actions ----------
    def browse_folder(self):
        path = filedialog.askdirectory(title="Select repository or folder")
        if path:
            self.folder_var.set(path)

    def run(self):
        if self.running:
            return
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Select a valid folder.")
            return
        self.btn_run.config(state=tk.DISABLED)
        self.running = True
        self._log("\n=== Scanning directory structure ===\n", "bold")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            root = os.path.normpath(self.folder_var.get().strip())
            auto_repo = is_repo_root(root)
            repo_mode = self.force_repo_var.get() and auto_repo

            if self.force_repo_var.get() and not auto_repo:
                self._log("[warn] Repo mode requested, but .git/mkdocs.yml not found. Falling back to full scan.\n", "warn")

            self._log(f"Root: {root}\n", "ok")
            self._log(f"Repo mode: {'ON' if repo_mode else 'OFF'}\n", "ok")

            if repo_mode:
                self._scan_repo(root)
            else:
                self._walk_tree(root, base=root)

            self._log("\nScan complete.\n", "bold")

        except Exception as e:
            self._log(f"[error] {e}\n", "err")
            try:
                messagebox.showerror("Error", str(e))
            except Exception:
                pass
        finally:
            try:
                self.btn_run.config(state=tk.NORMAL)
            except Exception:
                pass
            self.running = False

    # ---------- Scanning logic ----------
    def _scan_repo(self, root: str):
        # List non-hidden root files first
        self._log("Root files:", "bold")
        try:
            for f in sorted(os.listdir(root)):
                p = os.path.join(root, f)
                if os.path.isfile(p) and not f.startswith(HIDDEN_PREFIX):
                    self._log(f"  {f}")
        except Exception as e:
            self._log(f"[warn] Could not list root files: {e}\n", "warn")

        # Walk only allowed top-level dirs
        for name in sorted(ALLOWED_TOP_LEVEL):
            p = os.path.join(root, name)
            if os.path.isdir(p):
                self._log(f"\nIncluding top-level: {p}\n", "bold")
                self._walk_tree(p, base=root)
            else:
                self._log(f"[warn] Missing allowed dir (skipped): {p}\n", "warn")

    def _walk_tree(self, start: str, base: str):
        for current, dirs, files in os.walk(start):
            # prune unwanted/hidden dirs
            dirs[:] = [
                d for d in dirs
                if not d.startswith(HIDDEN_PREFIX) and d not in EXCLUDE_DIRS
            ]

            rel = os.path.relpath(current, base)
            if rel == ".":
                rel = os.path.basename(current)
            self._log(f"{rel}/")

            for f in sorted(files):
                if f.startswith(HIDDEN_PREFIX):
                    continue
                line = f"    {f}"
                if self.show_sizes_var.get():
                    try:
                        size = os.path.getsize(os.path.join(current, f))
                        line += f"  ({size} bytes)"
                    except Exception:
                        pass
                self._log(line)

    # ---------- Logging ----------
    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def _log(self, text, tag=None):
        self.log.insert(tk.END, text + ("\n" if not text.endswith("\n") else ""), tag)
        self.log.see(tk.END)

if __name__ == "__main__":
    App().mainloop()
