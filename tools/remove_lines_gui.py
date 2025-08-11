#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remove_lines_gui.py
Delete exact lines (or lines containing a given snippet) from Markdown files.

What it does
- You paste one or more lines (e.g., a full Markdown link like
  [(Voltar a Localizações / Back to Locations)](localizacoes.md))
- The tool searches all .md files under a chosen folder.
- Dry-run shows previews with file + line numbers.
- When "Write changes" is ON, it deletes those lines.
- Optional: "Contains match" to remove any line that contains a pasted snippet.
- Creates a .bak once per file when writing.

Notes
- Matching is line-based. We normalize only trailing whitespace and line endings.
- Exact mode → line must match exactly (after trimming trailing spaces).
- Contains mode → line is removed if it contains your pasted snippet (after trimming your snippet).
"""

from __future__ import annotations
from pathlib import Path
import re
from typing import Iterable, List, Tuple

# ---------- Core ----------

def iter_md_files(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.md")

def normalize_line(s: str) -> str:
    # Compare lines without trailing spaces or \r\n noise
    return s.rstrip()

def parse_targets(pasted: str, contains: bool) -> List[str]:
    """
    Each non-empty line is a target.
    - Exact mode: use as-is (minus trailing spaces).
    - Contains mode: also strip leading spaces for robustness.
    """
    targets: List[str] = []
    for raw in pasted.splitlines():
        t = raw.strip() if contains else normalize_line(raw)
        if t:
            targets.append(t)
    return targets

def find_matches_in_file(text: str, targets: List[str], contains: bool) -> List[Tuple[int, str]]:
    """
    Return list of (lineno, line_text) that match any target.
    """
    lines = text.splitlines(keepends=False)
    hits: List[Tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        norm = normalize_line(line)
        if contains:
            if any(t in norm for t in targets):
                hits.append((i, line))
        else:
            if any(norm == t for t in targets):
                hits.append((i, line))
    return hits

def remove_matches(text: str, targets: List[str], contains: bool) -> Tuple[str, int]:
    """
    Remove matched lines and collapse 3+ blank lines to 2.
    Returns (new_text, removed_count).
    """
    lines = text.splitlines(keepends=True)  # keepends to preserve file formatting
    out: List[str] = []
    removed = 0
    for line in lines:
        norm = normalize_line(line[:-1] if line.endswith(("\n", "\r")) else line)
        match = False
        if contains:
            match = any(t in norm for t in targets)
        else:
            match = any(norm == t for t in targets)
        if match:
            removed += 1
            continue
        out.append(line)

    new_text = "".join(out)
    # Collapse excessive blank lines (3+ → 2)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text, flags=re.MULTILINE)
    return new_text, removed

def process_file(p: Path, targets: List[str], contains: bool, write: bool, backups: bool) -> Tuple[int, List[Tuple[int, str]]]:
    """
    Returns (removed_count, previews)
    previews = list of (lineno, original_line)
    """
    text = p.read_text(encoding="utf-8", errors="ignore")
    previews = find_matches_in_file(text, targets, contains)

    if not write or not previews:
        return len(previews), previews

    # Write mode
    new_text, removed = remove_matches(text, targets, contains)
    if removed:
        if backups:
            bak = p.with_suffix(p.suffix + ".bak")
            if not bak.exists():
                bak.write_text(text, encoding="utf-8")
        p.write_text(new_text, encoding="utf-8")

    return removed, previews

# ---------- GUI ----------

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Remove Lines from Markdown (exact or contains)")
        self.geometry("1000x700")
        self.minsize(900, 600)

        self.root_var = tk.StringVar()
        self.contains_var = tk.BooleanVar(value=False)  # exact match by default
        self.write_var = tk.BooleanVar(value=False)     # dry-run by default
        self.backup_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        # Root chooser
        r = ttk.Frame(frm); r.pack(fill="x", pady=(0,8))
        ttk.Label(r, text="Root folder:").pack(side="left")
        ttk.Entry(r, textvariable=self.root_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r, text="Browse…", command=self.choose_folder).pack(side="left")

        # Targets box
        tbox = ttk.LabelFrame(frm, text="Paste lines to remove (one per line)")
        tbox.pack(fill="both", pady=(0,8))
        self.targets_text = tk.Text(tbox, height=8, wrap="none")
        self.targets_text.pack(fill="both", expand=True, padx=8, pady=8)

        # Options
        opts = ttk.Frame(frm); opts.pack(fill="x", pady=(0,8))
        ttk.Checkbutton(opts, text="Contains match (remove lines that contain the snippet)", variable=self.contains_var).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="Write changes", variable=self.write_var).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="Create .bak backups", variable=self.backup_var).pack(side="left", padx=8)

        # Actions
        act = ttk.Frame(frm); act.pack(fill="x", pady=(0,8))
        ttk.Button(act, text="Run", command=self.run).pack(side="left")
        ttk.Button(act, text="Save log…", command=self.save_log).pack(side="left", padx=8)
        ttk.Button(act, text="Quit", command=self.destroy).pack(side="right")

        # Log
        self.log = tk.Text(frm, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        self.log.tag_config("ok", foreground="#0a0")
        self.log.tag_config("warn", foreground="#a60")
        self.log.tag_config("err", foreground="#a00")
        self.log.tag_config("mono", font=("Consolas", 10))
        self._append("Dry-run by default. Enable 'Write changes' to apply.\n", "warn")

    def choose_folder(self):
        p = filedialog.askdirectory(title="Choose root")
        if p:
            self.root_var.set(p)

    def _append(self, text: str, tag: str | None = None):
        self.log.configure(state="normal")
        self.log.insert("end", text, (tag,) if tag else ())
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def run(self):
        root = Path(self.root_var.get().strip() or ".").resolve()
        if not root.exists():
            messagebox.showerror("Error", f"Folder not found:\n{root}")
            return

        pasted = self.targets_text.get("1.0", "end-1c")
        contains = self.contains_var.get()
        write = self.write_var.get()
        backups = self.backup_var.get()

        targets = parse_targets(pasted, contains)
        if not targets:
            messagebox.showwarning("No targets", "Paste at least one non-empty line.")
            return

        self._append(f"\n=== Scanning: {root} ===\n")
        self._append(f"Mode: {'contains' if contains else 'exact'} | Write: {write} | Backups: {backups}\n")
        self._append("Targets:\n", None)
        for t in targets:
            self._append(f"  • {t}\n", "mono")

        total_files = 0
        changed_files = 0
        total_removed = 0

        for md in iter_md_files(root):
            total_files += 1
            try:
                removed, previews = process_file(md, targets, contains, write, backups)
            except Exception as e:
                self._append(f"[ERROR] {md}: {e}\n", "err")
                continue

            if previews:
                changed_files += 1
                total_removed += removed if write else len(previews)
                mode = "removed" if write else "would remove"
                self._append(f"[{mode}] {md} ({len(previews)} line(s))\n", "warn" if not write else "ok")
                # Inline preview (always shown)
                for lineno, line in previews:
                    self._append(f"    L{lineno:>5}: ", "mono")
                    self._append(line + "\n", "mono")

        self._append(f"\nDone. Files scanned: {total_files}, touched: {changed_files}, "
                     f"lines {'removed' if write else 'matching'}: {total_removed}\n", "ok")
        if not write:
            self._append("Dry-run only. Enable 'Write changes' and run again to apply.\n", "warn")

    def save_log(self):
        path = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            filetypes=[("Text files","*.txt"), ("All files","*.*")]
        )
        if not path:
            return
        data = self.log.get("1.0", "end-1c")
        try:
            Path(path).write_text(data, encoding="utf-8")
            messagebox.showinfo("Saved", f"Log saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    App().mainloop()
