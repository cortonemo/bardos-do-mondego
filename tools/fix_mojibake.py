#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import shutil

PORTUGUESE_DIACRITICS = "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ"
MOJIBAKE_MARKERS = ["Ã", "Â", "â€", "â€™", "â€œ", "â€\x9d", "â€“", "â€”", "ðŸ", "�"]

def looks_mojibake(s: str) -> bool:
    return any(m in s for m in MOJIBAKE_MARKERS)

def score_text(s: str) -> int:
    diacritics = sum(s.count(ch) for ch in PORTUGUESE_DIACRITICS)
    markers = sum(s.count(m) for m in MOJIBAKE_MARKERS)
    # prefer fewer replacement chars too
    return diacritics * 5 - markers * 7 - s.count("�") * 10

def try_fix(text: str) -> str:
    # Two common wrong decodings
    candidates = []
    try:
        candidates.append(text.encode("latin-1", "ignore").decode("utf-8", "ignore"))
    except Exception:
        pass
    try:
        candidates.append(text.encode("cp1252", "ignore").decode("utf-8", "ignore"))
    except Exception:
        pass

    if not candidates:
        return text

    # Keep original as baseline and pick the best by heuristic
    scored = [(score_text(c), c) for c in candidates]
    best_score, best_text = max(scored, key=lambda t: t[0])
    # Only accept if it improves things
    if best_score > score_text(text):
        return best_text
    return text

def process_file(path: Path, dry_run: bool, make_backup: bool) -> tuple[bool, bool]:
    """Returns (changed, skipped)"""
    try:
        raw = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        # If the file itself was wrongly saved in a legacy encoding, load as cp1252 then normalize to UTF-8
        try:
            raw = path.read_text(encoding="cp1252", errors="strict")
        except Exception:
            try:
                raw = path.read_text(encoding="latin-1", errors="strict")
            except Exception:
                return (False, True)

    if not looks_mojibake(raw):
        return (False, True)

    fixed = try_fix(raw)
    if fixed == raw:
        return (False, True)

    if dry_run:
        return (True, False)

    if make_backup:
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)

    path.write_text(fixed, encoding="utf-8", errors="strict")
    return (True, False)

def main():
    p = argparse.ArgumentParser(
        description="Fix mojibake in UTF-8 Markdown and text files (Portuguese-friendly)."
    )
    p.add_argument("root", type=Path, help="Root folder to scan")
    p.add_argument(
        "--ext",
        nargs="+",
        default=[".md", ".markdown", ".txt", ".yml", ".yaml"],
        help="File extensions to include (default: .md .markdown .txt .yml .yaml)",
    )
    p.add_argument("--dry-run", action="store_true", help="Detect and report, but don't modify files")
    p.add_argument("--no-backup", action="store_true", help="Do not create .bak backups")
    args = p.parse_args()

    if not args.root.exists():
        print(f"Path not found: {args.root}", file=sys.stderr)
        sys.exit(1)

    changed = skipped = scanned = 0
    for path in args.root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {e.lower() for e in args.ext}:
            scanned += 1
            c, s = process_file(path, args.dry_run, not args.no_backup)
            changed += int(c)
            skipped += int(s)

    print(f"Scanned: {scanned} files")
    if args.dry_run:
        print(f"Would fix: {changed} files")
    else:
        print(f"Fixed:  {changed} files (backups: {'.bak' if not args.no_backup else 'none'})")
    print(f"Unchanged/Skipped: {skipped} files")

if __name__ == "__main__":
    main()
