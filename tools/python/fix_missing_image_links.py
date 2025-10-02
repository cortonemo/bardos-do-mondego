#!/usr/bin/env python3
"""
Markdown Missing Image Fixer (GUI + Dry Run + In-App Log)

- Finds Markdown links like: [Alt Text](image.png)
- If target image is missing next to the Markdown file, replaces with: ![Alt Text](blank.png)
- Ensures a local blank.png exists beside the Markdown (non-dry runs)
- Shows a live log in the GUI and also writes a .log file

Defaults:
  BLANK_SOURCE = G:\Git\bardos-do-mondego\tools\blank.png
  LOG_FOLDER   = G:\Git\bardos-do-mondego\tools
"""

import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from datetime import datetime

# ---------- CONFIG ----------
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
MARKDOWN_EXTS = {".md", ".markdown"}
LINK_TO_IMAGE_RE = re.compile(r'(?<!\!)\[(?P<alt>[^\]]+)\]\((?P<url>[^)]+)\)')
BLANK_SOURCE = Path(r"G:\Git\bardos-do-mondego\tools\blank.png")
LOG_FOLDER   = Path(r"G:\Git\bardos-do-mondego\tools")
# ----------------------------


def is_probably_local_image(url: str) -> bool:
    u = url.strip()
    if u.startswith(("http://", "https://", "data:", "mailto:")):
        return False
    if u.startswith("#"):
        return False
    for sep in ("?", "#"):
        if sep in u:
            u = u.split(sep, 1)[0]
    return Path(u).suffix.lower() in IMAGE_EXTS


def ensure_blank_in_folder(dest_folder: Path, blank_source: Path) -> Path:
    dest = dest_folder / "blank.png"
    if not dest.exists():
        dest_folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(blank_source, dest)
    return dest


def process_markdown_file(md_path: Path, blank_source: Path, logger, dry_run: bool):
    """
    logger: callable(str) -> None
    Returns tuple: (changed, replacements_count, blank_copies_count)
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger(f"[ERROR] {md_path}  {e}")
        return (False, 0, 0)

    changed = False
    replacements = 0
    copies = 0

    def repl(m: re.Match) -> str:
        nonlocal changed, replacements, copies
        alt = m.group("alt").strip()
        url = m.group("url").strip()

        if not is_probably_local_image(url):
            return m.group(0)

        candidate = (md_path.parent / url).resolve()
        if candidate.exists():
            return m.group(0)

        changed = True
        replacements += 1

        blank_here = (md_path.parent / "blank.png")
        if not blank_here.exists():
            if dry_run:
                copies += 1
            else:
                try:
                    ensure_blank_in_folder(md_path.parent, blank_source)
                    copies += 1
                except Exception as e:
                    # Continue, but record the error. We still replace to point at blank.png.
                    logger(f"[WARN]  {md_path}  failed to copy blank.png: {e}")

        return f"![{alt}](blank.png)"

    new_text = LINK_TO_IMAGE_RE.sub(repl, text)

    if changed:
        if dry_run:
            logger(f"[DRY]   {md_path}  would replace: {replacements}  would copy blank: {copies}")
        else:
            try:
                backup = md_path.with_suffix(md_path.suffix + ".bak")
                md_path.replace(backup)  # move original -> .bak
                md_path.write_text(new_text, encoding="utf-8")
                logger(f"[FIXED] {md_path}  replaced: {replacements}  copied blank: {copies}")
            except Exception as e:
                # Try to restore original if write failed
                try:
                    if 'backup' in locals() and backup.exists() and not md_path.exists():
                        backup.replace(md_path)
                except Exception:
                    pass
                logger(f"[ERROR] {md_path}  {e}")
                return (False, 0, 0)

    return (changed, replacements, copies)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Markdown Missing Image Fixer")
        self.geometry("820x520")
        self.minsize(760, 480)

        self.selected_root: Path | None = None
        self.var_dry = tk.BooleanVar(value=True)
        self.current_log_path: Path | None = None
        LOG_FOLDER.mkdir(parents=True, exist_ok=True)

        # Header
        tk.Label(self, text="Scan Markdown for missing image links and replace with blank.png").pack(pady=(10, 4))

        # Folder chooser
        top = tk.Frame(self)
        top.pack(fill="x", padx=10)
        tk.Button(top, text="Choose Folder…", command=self.choose_folder).pack(side="left")
        self.lbl_folder = tk.Label(top, text="No folder selected", anchor="w")
        self.lbl_folder.pack(side="left", padx=8)

        # Options
        opts = tk.Frame(self)
        opts.pack(fill="x", padx=10, pady=6)
        tk.Checkbutton(opts, text="Dry Run (no changes, just log)", variable=self.var_dry).pack(side="left")
        tk.Button(opts, text="Run", width=10, command=self.run).pack(side="right")
        tk.Button(opts, text="Open Log", width=10, command=self.open_log).pack(side="right", padx=(0, 8))

        # Live Log
        tk.Label(self, text="Log:").pack(anchor="w", padx=10)
        self.txt_log = ScrolledText(self, wrap="word", height=18)
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_log.configure(state="disabled")

        # Footer info
        self.lbl_status = tk.Label(self, text=f"Uses blank: {BLANK_SOURCE}", fg="gray")
        self.lbl_status.pack(anchor="w", padx=10, pady=(0, 8))

    def log(self, line: str):
        # Append to GUI log
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", line + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        # Also keep in memory to save later
        if not hasattr(self, "_log_buffer"):
            self._log_buffer = []
        self._log_buffer.append(line)
        # Keep UI responsive during long runs
        self.update_idletasks()

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select Root Folder")
        if folder:
            self.selected_root = Path(folder)
            self.lbl_folder.config(text=str(self.selected_root))

    def run(self):
        if not self.selected_root:
            messagebox.showwarning("Select Folder", "Please choose a root folder first.")
            return

        if not BLANK_SOURCE.exists():
            messagebox.showerror("Error", f"blank.png not found at {BLANK_SOURCE}")
            return

        # Clear previous log view + buffer
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")
        self._log_buffer = []

        dry = self.var_dry.get()
        mode = "Dry Run" if dry else "Apply Changes"
        self.log(f"[INFO]  Mode: {mode}")
        self.log(f"[INFO]  Root: {self.selected_root}")
        self.log(f"[INFO]  Blank source: {BLANK_SOURCE}")

        total_files = total_changed = total_repl = total_copies = 0

        # Iterate files
        for md in self.selected_root.rglob("*"):
            if md.is_file() and md.suffix.lower() in MARKDOWN_EXTS:
                total_files += 1
                changed, repl, copies = process_markdown_file(md, BLANK_SOURCE, self.log, dry_run=dry)
                if changed:
                    total_changed += 1
                    total_repl += repl
                    total_copies += copies

        # Write log file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        suffix = "dryrun" if dry else "fixed"
        self.current_log_path = LOG_FOLDER / f"missing_images_{suffix}_{timestamp}.log"
        try:
            self.current_log_path.write_text("\n".join(self._log_buffer), encoding="utf-8")
            self.log(f"[INFO]  Log saved to: {self.current_log_path}")
        except Exception as e:
            self.log(f"[ERROR] Failed to write log: {e}")

        # Summary
        summary = (
            f"{'Would change' if dry else 'Changed'} files: {total_changed} | "
            f"{'Would replace' if dry else 'Replacements'}: {total_repl} | "
            f"{'Would copy' if dry else 'blank.png copies'}: {total_copies}"
        )
        self.log(f"[SUMMARY] Scanned markdown files: {total_files}")
        self.log(f"[SUMMARY] {summary}")
        messagebox.showinfo("Scan Complete", summary)

    def open_log(self):
        if not self.current_log_path or not self.current_log_path.exists():
            messagebox.showinfo("Open Log", "No log file yet. Run a scan first.")
            return
        try:
            # Windows: startfile opens with default app (Notepad)
            import os
            os.startfile(self.current_log_path)  # type: ignore[attr-defined]
        except Exception as e:
            messagebox.showerror("Open Log", f"Failed to open log: {e}")


if __name__ == "__main__":
    App().mainloop()
