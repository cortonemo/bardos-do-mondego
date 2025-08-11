#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_image_links_gui.py
Serelith utility – normalize Markdown/HTML image paths to filename only.

What it does
- Scans .md files (recursively) under a chosen folder.
- Rewrites any Markdown [..](x/y/z/name.ext) or ![..](x\y\z\name.ext)
  and HTML <img src="x/y/z/name.ext"> to just (name.ext) / src="name.ext"
  when the target is a local image (png, jpg, jpeg, gif, webp, svg).
- Preserves Markdown titles: ![alt](path.png "caption") -> ![alt](name.png "caption")
- Skips http(s)://, data:, mailto:, obsidian:, app: and absolute file URLs.
- Dry-run by default. When “Write changes” is enabled, creates .bak backups.

Why good
- Surgical change, low risk, preserves titles and everything else.
Why not
- Regex can’t cover every exotic Markdown edge case. If your files
  use very unusual link syntax, dry-run first and review diffs.

Author: Liora (for Serelith)
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Iterable, Tuple

# ---------- Core logic ----------

IMAGE_EXTS_DEFAULT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}

# Markdown links/images with optional quoted title:
#  group(1) = prefix '![alt](' or '[text]('
#  'path' = the URL/path portion (no closing paren)
#  'tail' = optional whitespace + "title" + closing ')'
MD_LINK_RE = re.compile(
    r'(?P<prefix>!?\[[^\]]*\]\()'
    r'(?P<path>[^)\s]+)'
    r'(?P<tail>\s*(?:"[^"]*"|\'[^\']*\')?\))'
)

# HTML <img ... src="..."> (single or double quotes)
HTML_IMG_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=)'
    r'(?P<quote>["\'])'
    r'(?P<path>[^"\']+)'
    r'(?P=quote)',
    flags=re.IGNORECASE
)

SKIP_SCHEMES = ("http://", "https://", "data:", "mailto:", "obsidian:", "app:", "file://")


def is_local_image(path_str: str, allowed_exts: set[str]) -> bool:
    if any(path_str.lower().startswith(s) for s in SKIP_SCHEMES):
        return False
    # Strip query/fragment for extension test
    bare = re.split(r"[?#]", path_str, maxsplit=1)[0]
    ext = Path(bare).suffix.lower().lstrip(".")
    if ext not in allowed_exts:
        return False
    # Only rewrite when folders are present
    return ("/" in bare) or ("\\" in bare)


def to_basename_only(path_str: str) -> str:
    # Keep query string or fragment if present
    pre, *tail = re.split(r"([?#].*)", path_str, maxsplit=1)
    base = os.path.basename(pre.replace("\\", "/"))
    return base + ("".join(tail) if tail else "")


def normalize_markdown(content: str, allowed_exts: set[str]) -> Tuple[str, int]:
    """Return (new_content, num_rewrites) for Markdown images/links."""
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        path = m.group("path")
        if is_local_image(path, allowed_exts):
            new_path = to_basename_only(path)
            if new_path != path:
                count += 1
                return f'{m.group("prefix")}{new_path}{m.group("tail")}'
        return m.group(0)

    return MD_LINK_RE.sub(repl, content), count


def normalize_html_imgs(content: str, allowed_exts: set[str]) -> Tuple[str, int]:
    """Return (new_content, num_rewrites) for <img src="...">."""
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        path = m.group("path")
        if is_local_image(path, allowed_exts):
            new_path = to_basename_only(path)
            if new_path != path:
                count += 1
                return f'{m.group(1)}{m.group("quote")}{new_path}{m.group("quote")}'
        return m.group(0)

    return HTML_IMG_RE.sub(repl, content), count


def process_file(p: Path, allowed_exts: set[str], write: bool, backups: bool, include_html: bool) -> tuple[int, int]:
    """
    Returns (rewrites, bytes_written). If write=False, bytes_written is 0.
    """
    text = p.read_text(encoding="utf-8", errors="ignore")
    new_text, c1 = normalize_markdown(text, allowed_exts)
    if include_html:
        new_text, c2 = normalize_html_imgs(new_text, allowed_exts)
    else:
        c2 = 0
    total = c1 + c2

    if write and total > 0:
        if backups:
            bak = p.with_suffix(p.suffix + ".bak")
            if not bak.exists():
                bak.write_text(text, encoding="utf-8")
        p.write_text(new_text, encoding="utf-8")
        return total, len(new_text.encode("utf-8"))
    return total, 0


def iter_md_files(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.md")


# ---------- GUI ----------

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Normalize Image Links – Markdown/HTML")
        self.geometry("900x600")
        self.minsize(800, 520)

        # Vars
        self.root_var = tk.StringVar()
        self.exts_var = tk.StringVar(value="png,jpg,jpeg,gif,webp,svg")
        self.include_html_var = tk.BooleanVar(value=True)
        self.write_var = tk.BooleanVar(value=False)    # dry-run by default
        self.backup_var = tk.BooleanVar(value=True)

        # Layout
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        # Row 1: Folder
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Root folder:").pack(side="left")
        ttk.Entry(row, textvariable=self.root_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Browse…", command=self.choose_folder).pack(side="left")

        # Row 2: Options
        row2 = ttk.Frame(frm)
        row2.pack(fill="x", pady=(0, 8))
        ttk.Label(row2, text="Image extensions (comma-separated):").pack(side="left")
        ttk.Entry(row2, width=35, textvariable=self.exts_var).pack(side="left", padx=6)
        ttk.Checkbutton(row2, text="Handle HTML <img>", variable=self.include_html_var).pack(side="left", padx=10)
        ttk.Checkbutton(row2, text="Write changes", variable=self.write_var).pack(side="left", padx=10)
        ttk.Checkbutton(row2, text="Create .bak backups", variable=self.backup_var).pack(side="left", padx=10)

        # Row 3: Actions
        row3 = ttk.Frame(frm)
        row3.pack(fill="x", pady=(0, 8))
        ttk.Button(row3, text="Run", command=self.run).pack(side="left")
        ttk.Button(row3, text="Save log…", command=self.save_log).pack(side="left", padx=8)
        ttk.Button(row3, text="Quit", command=self.destroy).pack(side="right")

        # Log area
        self.log = tk.Text(frm, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")
        self.log_tag_ok = "ok"
        self.log_tag_warn = "warn"
        self.log_tag_err = "err"
        self.log.tag_config(self.log_tag_ok, foreground="#0a0")
        self.log.tag_config(self.log_tag_warn, foreground="#a60")
        self.log.tag_config(self.log_tag_err, foreground="#a00")

        self._append("Dry-run by default. Enable “Write changes” to modify files.\n", self.log_tag_warn)

    def choose_folder(self):
        path = filedialog.askdirectory(title="Choose repository root")
        if path:
            self.root_var.set(path)

    def _append(self, text: str, tag: str | None = None):
        self.log.configure(state="normal")
        if tag:
            self.log.insert("end", text, (tag,))
        else:
            self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def run(self):
        root = Path(self.root_var.get().strip() or ".").resolve()
        if not root.exists():
            messagebox.showerror("Error", f"Folder not found:\n{root}")
            return

        exts = {e.strip().lower().lstrip(".") for e in self.exts_var.get().split(",") if e.strip()}
        if not exts:
            exts = IMAGE_EXTS_DEFAULT

        include_html = self.include_html_var.get()
        write = self.write_var.get()
        backups = self.backup_var.get()

        self._append(f"\n=== Scanning: {root} ===\n")
        self._append(f"Extensions: {sorted(exts)} | HTML: {include_html} | Write: {write} | Backups: {backups}\n")

        total_files = 0
        changed_files = 0
        total_rewrites = 0

        for md in iter_md_files(root):
            total_files += 1
            try:
                rewrites, _ = process_file(md, exts, write, backups, include_html)
            except Exception as e:
                self._append(f"[ERROR] {md}: {e}\n", self.log_tag_err)
                continue

            if rewrites:
                changed_files += 1
                total_rewrites += rewrites
                tag = self.log_tag_warn if not write else self.log_tag_ok
                mode = "would rewrite" if not write else "rewrote"
                self._append(f"[{mode}] {md}  ({rewrites} change(s))\n", tag)

        self._append(f"\nDone. Files scanned: {total_files}, files with changes: {changed_files}, total rewrites: {total_rewrites}\n", self.log_tag_ok)
        if not write:
            self._append("Dry-run only. Enable “Write changes” and run again to apply.\n", self.log_tag_warn)

    def save_log(self):
        path = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        data = self.log.get("1.0", "end-1c")
        try:
            Path(path).write_text(data, encoding="utf-8")
            messagebox.showinfo("Saved", f"Log saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
