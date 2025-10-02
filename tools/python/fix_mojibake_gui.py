#!/usr/bin/env python3
"""
fix_mojibake_gui.py — batch-fix mojibake with a minimal GUI (Tkinter) or CLI.

Features
- Detects mojibake (common UTF-8/CP1252/latin-1 mis-decodes), Portuguese-friendly heuristic.
- Two modes:
    * GUI (default when launched without CLI args).
    * CLI (when args are provided, retains original switches).
- Always writes a log of fixed files (default: mojibake_fix_log.txt in chosen root).
- Optional dry-run and backup control.
- Progress bar + live output in GUI.
"""

import sys
import argparse
from pathlib import Path
import shutil
import threading
import queue
import time

# -------------- Core logic --------------

PORTUGUESE_DIACRITICS = "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ"
MOJIBAKE_MARKERS = ["Ã", "Â", "â€", "â€™", "â€œ", "â€\x9d", "â€“", "â€”", "ðŸ", "�"]

def looks_mojibake(s: str) -> bool:
    return any(m in s for m in MOJIBAKE_MARKERS)

def score_text(s: str) -> int:
    diacritics = sum(s.count(ch) for ch in PORTUGUESE_DIACRITICS)
    markers = sum(s.count(m) for m in MOJIBAKE_MARKERS)
    return diacritics * 5 - markers * 7 - s.count("�") * 10

def try_fix(text: str) -> str:
    candidates = []
    # latin-1 -> utf-8
    try:
        candidates.append(text.encode("latin-1", "ignore").decode("utf-8", "ignore"))
    except Exception:
        pass
    # cp1252 -> utf-8
    try:
        candidates.append(text.encode("cp1252", "ignore").decode("utf-8", "ignore"))
    except Exception:
        pass

    if not candidates:
        return text

    scored = [(score_text(c), c) for c in candidates]
    best_score, best_text = max(scored, key=lambda t: t[0])
    if best_score > score_text(text):
        return best_text
    return text

def process_file(path: Path, dry_run: bool, make_backup: bool, log_lines: list) -> tuple[bool, bool]:
    """Returns (changed, skipped) and appends to log_lines when changed"""
    try_encodings = [("utf-8", True), ("cp1252", False), ("latin-1", False)]
    raw = None

    # Load: prefer utf-8, fall back to cp1252/latin-1 if needed
    for enc, strict in try_encodings:
        try:
            errors = "strict" if strict else "strict"
            raw = path.read_text(encoding=enc, errors=errors)
            break
        except UnicodeDecodeError:
            continue
        except Exception:
            continue

    if raw is None:
        # couldn't read cleanly
        return (False, True)

    if not looks_mojibake(raw):
        return (False, True)

    fixed = try_fix(raw)
    if fixed == raw:
        return (False, True)

    if dry_run:
        log_lines.append(f"[DRY] Would fix: {path}")
        return (True, False)

    backup_path = None
    if make_backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        if not backup_path.exists():
            shutil.copy2(path, backup_path)

    path.write_text(fixed, encoding="utf-8", errors="strict")
    if backup_path:
        log_lines.append(f"[FIXED] {path}  (backup: {backup_path})")
    else:
        log_lines.append(f"[FIXED] {path}")

    return (True, False)

def run_batch(root: Path, exts: list[str], dry_run: bool, make_backup: bool, log_path: Path, status_cb=None) -> dict:
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {e.lower() for e in exts}]
    total = len(files)
    changed = skipped = 0
    log_lines: list[str] = []
    for i, path in enumerate(files, 1):
        try:
            c, s = process_file(path, dry_run, make_backup, log_lines)
            changed += int(c); skipped += int(s)
        except Exception as e:
            log_lines.append(f"[ERROR] {path}: {e!r}")
        if status_cb:
            status_cb(i, total, path)

    # write log
    try:
        header = f"Root: {root}\nScanned: {total} files\n"
        if dry_run:
            header += f"Would fix: {changed} files\n"
        else:
            header += f"Fixed: {changed} files (backups: {'yes' if make_backup else 'no'})\n"
        header += f"Unchanged/Skipped: {skipped} files\n\n"
        log_path.write_text(header + "\n".join(log_lines), encoding="utf-8", errors="strict")
    except Exception as e:
        if status_cb:
            status_cb(total, total, f"[LOG ERROR] {e!r}")

    return {"scanned": total, "changed": changed, "skipped": skipped, "log": log_path}

# -------------- CLI --------------

def cli_main(argv=None):
    p = argparse.ArgumentParser(
        description="Fix mojibake in UTF-8 Markdown and text files (Portuguese-friendly). "
                    "Run without arguments to open the GUI."
    )
    p.add_argument("root", type=Path, nargs="?", help="Root folder to scan (omit to open GUI)")
    p.add_argument("--ext", nargs="+", default=[".md", ".markdown", ".txt", ".yml", ".yaml"],
                   help="File extensions to include (default: .md .markdown .txt .yml .yaml)")
    p.add_argument("--dry-run", action="store_true", help="Detect and report, but don't modify files")
    p.add_argument("--no-backup", action="store_true", help="Do not create .bak backups when fixing")
    p.add_argument("--logfile", type=Path, default=None, help="Path to write a detailed log of fixed files")
    args = p.parse_args(argv)

    if args.root is None:
        # fall into GUI
        return gui_main()

    if not args.root.exists():
        print(f"Path not found: {args.root}", file=sys.stderr)
        return 1

    log_path = args.logfile or (args.root / "mojibake_fix_log.txt")
    res = run_batch(args.root, args.ext, args.dry_run, not args.no_backup, log_path)
    print(f"Scanned: {res['scanned']} | {'Would fix' if args.dry_run else 'Fixed'}: {res['changed']} | Skipped: {res['skipped']}")
    print(f"Log written to: {res['log']}")
    return 0

# -------------- GUI --------------

def gui_main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Fix Mojibake — Portuguese-friendly")
    root.geometry("820x560")

    # Variables
    v_path = tk.StringVar(value="")
    v_ext  = tk.StringVar(value=".md .markdown .txt .yml .yaml")
    v_dry  = tk.BooleanVar(value=False)
    v_bak  = tk.BooleanVar(value=True)
    v_log  = tk.StringVar(value="mojibake_fix_log.txt")

    # Layout
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)

    # Path row
    row = ttk.Frame(frm)
    row.pack(fill="x", pady=4)
    ttk.Label(row, text="Root folder").pack(side="left")
    ent_path = ttk.Entry(row, textvariable=v_path)
    ent_path.pack(side="left", fill="x", expand=True, padx=6)
    def pick_dir():
        d = filedialog.askdirectory(title="Select root folder")
        if d:
            v_path.set(d)
    ttk.Button(row, text="Browse…", command=pick_dir).pack(side="left")

    # Ext row
    row2 = ttk.Frame(frm); row2.pack(fill="x", pady=4)
    ttk.Label(row2, text="Extensions (space-separated)").pack(side="left")
    ent_ext = ttk.Entry(row2, textvariable=v_ext)
    ent_ext.pack(side="left", fill="x", expand=True, padx=6)

    # Options row
    row3 = ttk.Frame(frm); row3.pack(fill="x", pady=4)
    ttk.Checkbutton(row3, text="Dry run (don't modify files)", variable=v_dry).pack(side="left")
    ttk.Checkbutton(row3, text="Create .bak backups", variable=v_bak).pack(side="left", padx=12)

    # Log file
    row4 = ttk.Frame(frm); row4.pack(fill="x", pady=4)
    ttk.Label(row4, text="Log file").pack(side="left")
    ent_log = ttk.Entry(row4, textvariable=v_log)
    ent_log.pack(side="left", fill="x", expand=True, padx=6)
    def pick_log():
        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="mojibake_fix_log.txt",
                                         filetypes=[("Text files","*.txt"),("All files","*.*")])
        if f:
            v_log.set(f)
    ttk.Button(row4, text="…", width=3, command=pick_log).pack(side="left")

    # Progress & actions
    pb = ttk.Progressbar(frm, mode="determinate"); pb.pack(fill="x", pady=8)
    lbl = ttk.Label(frm, text="Idle"); lbl.pack(anchor="w")

    # Output
    txt = tk.Text(frm, height=18, wrap="word")
    txt.pack(fill="both", expand=True, pady=(6,0))
    txt.configure(state="disabled")

    def log_line(s: str):
        txt.configure(state="normal")
        txt.insert("end", s + "\n")
        txt.see("end")
        txt.configure(state="disabled")
        root.update_idletasks()

    # Worker thread
    def run_worker():
        from urllib.parse import unquote
        path = Path(v_path.get().strip())
        if not path.exists() or not path.is_dir():
            messagebox.showerror("Error", "Please choose a valid root folder.")
            return

        exts = [e if e.startswith(".") else ("." + e) for e in v_ext.get().split() if e.strip()]
        dry  = bool(v_dry.get())
        bak  = bool(v_bak.get())
        log_file = Path(v_log.get().strip())
        if not log_file.is_absolute():
            log_file = path / log_file

        # Pre-scan count
        files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {e.lower() for e in exts}]
        total = len(files)
        if total == 0:
            messagebox.showinfo("Nothing to do", "No matching files under the selected folder.")
            return

        pb["maximum"] = total
        pb["value"] = 0
        lbl.config(text=f"Scanning {total} files…")
        txt.configure(state="normal"); txt.delete("1.0","end"); txt.configure(state="disabled")

        def status_cb(i, total, current):
            pb["value"] = i
            lbl.config(text=f"{i}/{total}  {current}")
            if isinstance(current, Path):
                s = str(current)
            else:
                s = str(current)
            if s:
                log_line(str(s))

        # Run batch on a background thread
        def work():
            try:
                res = run_batch(path, exts, dry, bak, log_file, status_cb=status_cb)
            except Exception as e:
                res = {"error": repr(e)}
            finally:
                lbl.config(text="Done")
                if "error" in res:
                    messagebox.showerror("Error", res["error"])
                else:
                    summary = f"Scanned: {res['scanned']} | {'Would fix' if dry else 'Fixed'}: {res['changed']} | Skipped: {res['skipped']}\nLog: {res['log']}"
                    log_line(summary)
                    messagebox.showinfo("Complete", summary)

        threading.Thread(target=work, daemon=True).start()

    btns = ttk.Frame(frm); btns.pack(fill="x", pady=6)
    ttk.Button(btns, text="Run", command=run_worker).pack(side="right")
    ttk.Button(btns, text="Quit", command=root.destroy).pack(side="right", padx=6)

    root.mainloop()
    return 0

if __name__ == "__main__":
    # If arguments were provided, run CLI; else, open GUI.
    if len(sys.argv) > 1:
        sys.exit(cli_main(sys.argv[1:]))
    else:
        sys.exit(gui_main())
