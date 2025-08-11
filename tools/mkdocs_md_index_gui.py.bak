import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# --- Patterns ---
# Match #, ## ... ###### at start, allow BOM/space before
TITLE_RE = re.compile(r'^\s*\ufeff?\s*#{1,6}\s+(.*\S)\s*$')

# Remove ": Resumo Detalhado", "- Resumo Detalhado", "— Resumo Detalhado",
# plain "Resumo Detalhado", and also ": Resumo" (you have that variant too)
RESUMO_PAIR_RE = re.compile(
    r'\s*(?:[:\-–—]\s*)?Resumo(?:\s+Detalhado)?\b',
    re.IGNORECASE
)

# Remove leading "Sessão <num>" with optional dash/colon after
SESSAO_RE = re.compile(
    r'^\s*Sess[aã]o\s+\d+\s*(?:[-–—:]\s*)?',
    re.IGNORECASE
)

def yaml_quote(s: str) -> str:
    """Quote string for YAML if needed."""
    if s == "" or any(c in s for c in ':#-?&*!|>\'"%@`{}[]'):
        s2 = s.replace('"', '\\"')
        return f'"{s2}"'
    return s

def clean_title(title: str) -> str:
    if not title:
        return title
    t = SESSAO_RE.sub('', title)             # drop "Sessão xx ..."
    t = RESUMO_PAIR_RE.sub('', t)            # drop "Resumo Detalhado" variants, and ": Resumo"
    t = re.sub(r'\s{2,}', ' ', t).strip()    # collapse spaces
    # tidy stray leading dashes like "– " or "- "
    t = re.sub(r'^[\-\–—]\s*', '', t)
    return t

def extract_title(md_path: str) -> str | None:
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            for line in f:
                m = TITLE_RE.match(line)
                if m:
                    return clean_title(m.group(1).strip())
    except Exception:
        return None
    return None

def find_md_files(root: str, recursive: bool):
    def is_index(fn: str) -> bool:
        return fn.lower() == 'index.md'
    if recursive:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith('.md') and not is_index(fn):
                    yield os.path.join(dirpath, fn)
    else:
        for fn in os.listdir(root):
            if fn.lower().endswith('.md') and not is_index(fn):
                yield os.path.join(root, fn)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Markdown .pages Builder (title/file mapping)")
        self.geometry("920x600")

        self.folder_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.dryrun_var = tk.BooleanVar(value=False)
        self.running = False

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.X)

        ttk.Label(frm, text="Folder:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.folder_var, width=85).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Browse…", command=self.browse_folder).grid(row=0, column=2)

        opt = ttk.Frame(frm)
        opt.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10,0))
        ttk.Checkbutton(opt, text="Recursive", variable=self.recursive_var).grid(row=0, column=0, padx=(0,12))
        ttk.Checkbutton(opt, text="Dry run (no write)", variable=self.dryrun_var).grid(row=0, column=1, padx=(0,12))

        runbar = ttk.Frame(frm)
        runbar.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10,0))
        self.btn_run = ttk.Button(runbar, text="Build .pages", command=self.run)
        self.btn_run.grid(row=0, column=0)
        ttk.Button(runbar, text="Clear Log", command=self.clear_log).grid(row=0, column=1, padx=8)
        ttk.Button(runbar, text="Quit", command=self.destroy).grid(row=0, column=2)

        frm.columnconfigure(1, weight=1)

        self.log = ScrolledText(self, height=26, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.log.tag_configure("ok", foreground="#0a7f00")
        self.log.tag_configure("warn", foreground="#a15c00")
        self.log.tag_configure("err", foreground="#a10000")
        self.log.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
        self._log("Ready.\n", "bold")

    def browse_folder(self):
        path = filedialog.askdirectory(title="Select folder with Markdown files")
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
        self._log("\n=== Building .pages (title/file) ===\n", "bold")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        folder = self.folder_var.get().strip()
        recursive = self.recursive_var.get()
        dry = self.dryrun_var.get()

        items = []   # list of (relpath, cleaned_title)
        total = 0
        missing = 0

        try:
            for md in find_md_files(folder, recursive):
                total += 1
                rel = os.path.relpath(md, start=folder).replace(os.sep, '/')
                title = extract_title(md)
                if not title:
                    missing += 1
                    self._log(f"[warn] No H1 found, using filename  {rel}\n", "warn")
                    # fallback to filename without .md, humanize a bit
                    stem = os.path.splitext(os.path.basename(md))[0]
                    title = re.sub(r'[_\-]+', ' ', stem).strip()
                items.append((rel, title))
                self._log(f"[ok] Parsed  {rel}\n", "ok")

            # De-duplicate by relpath (not title), keep first occurrence
            seen = set()
            uniq = []
            for rel, title in items:
                if rel.lower() not in seen:
                    seen.add(rel.lower())
                    uniq.append((rel, title))

            # Sort by cleaned title (case-insensitive)
            uniq.sort(key=lambda it: it[1].lower())

            # YAML content: arrange: - title: ...  file: ...
            lines = ["arrange:"]
            for rel, title in uniq:
                lines.append(f"  - title: {yaml_quote(title)}")
                lines.append(f"    file: {yaml_quote(rel)}")
            content = "\n".join(lines) + "\n"

            self._log(f"\nFiles scanned: {total}\n", "bold")
            self._log(f"Without H1 (fell back to filename): {missing}\n", "bold")

            pages_path = os.path.join(folder, ".pages")
            if dry:
                self._log("\nDry run, no file written.\n", "warn")
                self._log("\nPreview (.pages YAML):\n", "bold")
                self._log(content + "\n")
            else:
                with open(pages_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                self._log(f"\nWritten: {pages_path}\n", "ok")

        except Exception as e:
            self._log(f"\n[error] {e}\n", "err")
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_run.config(state=tk.NORMAL)
            self.running = False

    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def _log(self, text, tag=None):
        self.log.insert(tk.END, text, tag)
        self.log.see(tk.END)

if __name__ == "__main__":
    App().mainloop()
