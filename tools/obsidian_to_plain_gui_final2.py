#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import queue
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

# -------------------- CONFIG: Asset mapping rules --------------------
# Keys are *folder prefixes relative to ROOT*, values are asset folders (also relative to ROOT).
# The first matching prefix wins (longest-prefix match).
#
# Updated for 'docs/lore-/**' structure. Notes under 'locations' map to assets/location.
# Everything else can still be resolved by filename across ALL_ASSET_DIRS below.
ASSET_MAP = {
    "lore-/locations": "assets/location",
}

# Directories where images are allowed to live. We'll search these as a fallback
# when a bare filename appears and ASSET_MAP can't determine a specific folder.
ALL_ASSET_DIRS = [
    "assets/location",
    "assets/loot",
    "assets/monsters",
    "assets/npc",
    "assets/organization",
    "assets/pc",
    "assets/rumor",
]


# -------------------- Category Defaults --------------------
# If an image can't be resolved, or if the filename is literally 'blank.png',
# pick a default by category inferred from the note's relative path.
CATEGORY_DEFAULTS = {
    "locations": "assets/location/location_blank.png",
    "monsters":  "assets/monsters/monster_blank.png",
    "organizations": "assets/organization/org_blank.png",
    "organization": "assets/organization/org_blank.png",
    "npc": "assets/npc/npc_blank.png",
    "pc":  "assets/pc/pc_blank.png",
    "rumors": "assets/rumor/rumor_blank.png",
    "rumor": "assets/rumor/rumor_blank.png",
    "loot": "assets/loot/object_blank.png",
}
CATEGORY_KEYS = sorted(CATEGORY_DEFAULTS.keys(), key=len, reverse=True)

def infer_category_rel_path(note_rel_path: str) -> str | None:
    p = note_rel_path.lower().replace("\\","/")
    for key in CATEGORY_KEYS:
        # match '/<key>/' segment somewhere in the path
        if f"/{key}/" in p or p.endswith(f"/{key}"):
            return key
    # special: lore-/locations content
    if "/lore-/" in p and "/locations/" in p:
        return "locations"
    return None
# --------------------------------------------------------------------

MD_EXTS = {".md"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".tif", ".tiff", ".svgz"}
MAX_INLINE_DEPTH = 2

RE_EMBED = re.compile(r'!\[\[([^\]]+)\]\]')
RE_WIKI  = re.compile(r'(?<!!)\[\[([^\]]+)\]\]')
RE_YAML  = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

# Markdown image: ![alt](url) or ![alt](url "title")
RE_MD_IMAGE = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+"[^"]*")?\)')

IMG_SIZE_RE = re.compile(r'^\s*(?:(?P<w>\d+)\s*[xX]\s*(?P<h>\d+)|(?P<wonly>\d+))\s*$')

def parse_obsidian_image_opts(label_or_opts: str | None):
    if not label_or_opts:
        return (None, None, None)
    parts = [p.strip() for p in label_or_opts.split("|") if p.strip()]
    alt, w, h = None, None, None
    for p in parts:
        m = IMG_SIZE_RE.match(p)
        if m:
            if m.group("w"):
                w = int(m.group("w"))
                if m.group("h"):
                    h = int(m.group("h"))
            elif m.group("wonly"):
                w = int(m.group("wonly"))
        else:
            alt = p
    return (alt, w, h)

def build_index(root: Path):
    by_stem = {}
    by_rel  = {}
    imgs_by_name = {}
    for p in root.rglob("*"):
        if p.is_file():
            stem = p.stem.lower()
            rel_noext = str(p.relative_to(root).with_suffix("")).replace("\\","/").lower()
            by_stem.setdefault(stem, []).append(p)
            by_rel[rel_noext] = p
            if p.suffix.lower() in IMG_EXTS:
                imgs_by_name.setdefault(p.name.lower(), []).append(p)
    return by_stem, by_rel, imgs_by_name

def choose_best(candidate_list):
    return sorted(candidate_list, key=lambda p: (len(str(p)), str(p)))[0]

@dataclass
class ResolveResult:
    kind: str           # "md" | "img" | "unknown" | "self"
    path: Path | None
    label: str | None
    anchor: str | None

def resolve_target(raw: str, current_file: Path, root: Path, by_stem, by_rel) -> ResolveResult:
    if "|" in raw:
        target, label = raw.split("|", 1)
    else:
        target, label = raw, None

    anchor = None
    if "#" in target:
        target, anchor = target.split("#", 1)

    target = target.strip()
    label = label.strip() if label else None
    anchor = anchor.strip() if anchor else None

    if target == "":
        return ResolveResult("self", current_file, label or anchor or "", anchor)

    if Path(target).suffix.lower() in IMG_EXTS:
        cand = list(root.rglob(target))
        p = choose_best(cand) if cand else None
        if not p:
            rel_noext = target.rsplit(".",1)[0].lower()
            p = by_rel.get(rel_noext)
            if p and p.suffix.lower() not in IMG_EXTS:
                p = None
        return ResolveResult("img", p, label, anchor)

    if "/" in target or "\\" in target:
        rel_noext = target.replace("\\","/").lower()
        p = by_rel.get(rel_noext)
        if not p:
            alt = rel_noext.replace(" ", "_")
            p = by_rel.get(alt)
        if p and p.suffix.lower() in MD_EXTS:
            return ResolveResult("md", p, label, anchor)
        pm = root / (target + ".md")
        if pm.exists():
            return ResolveResult("md", pm, label, anchor)

    p = None
    matches = by_stem.get(target.lower())
    if matches:
        md_matches = [m for m in matches if m.suffix.lower() in MD_EXTS]
        p = choose_best(md_matches) if md_matches else choose_best(matches)
    if p:
        kind = "md" if p.suffix.lower() in MD_EXTS else ("img" if p.suffix.lower() in IMG_EXTS else "unknown")
        return ResolveResult(kind, p, label, anchor)

    return ResolveResult("unknown", None, label, anchor)

def make_rel_link(src: Path, dst: Path, anchor: str | None):
    rel = Path(os.path.relpath(dst, start=src.parent)).as_posix()
    if anchor:
        return f"{rel}#{anchor.strip().replace(' ', '-').lower()}"
    return rel

def strip_front_matter(text: str):
    m = RE_YAML.match(text)
    if m:
        return text[m.end():]
    return text

def longest_prefix_match(rel_src: str, mapping: dict[str, str]) -> tuple[str, str] | None:
    # both arguments use forward slashes, lowercased
    candidates = [(k, v) for k, v in mapping.items() if rel_src.startswith(k)]
    if not candidates:
        return None
    # pick the longest key (deepest)
    return max(candidates, key=lambda kv: len(kv[0]))


def resolve_bare_image_by_map(src: Path, root: Path, filename: str, mapping: dict[str, str]):
    # literal 'blank.png' is not stored; handled by category defaults. Return None here.
    if filename.lower() == "blank.png":
        return None
    \"\"\"
    Given a note src and a bare image filename, find it inside the mapped asset folder.
    If no mapping applies, fall back to searching across ALL_ASSET_DIRS.
    Returns Path or None.
    """
    rel_src = str(src.relative_to(root).parent).replace("\","/").lower()
    match = longest_prefix_match(rel_src, mapping)
    fl = unquote(filename).lower()

    # 1) If a mapping applies, search that folder first
    if match:
        asset_rel = match[1]  # e.g. docs/assets/location
        asset_dir = root / asset_rel
        if asset_dir.is_dir():
            candidates = [p for p in asset_dir.rglob("*") if p.is_file() and p.name.lower() == fl]
            if candidates:
                return choose_best(candidates)

    # 2) Fallback: search across all declared asset directories
    for asset_rel in ALL_ASSET_DIRS:
        asset_dir = root / asset_rel
        if asset_dir.is_dir():
            candidates = [p for p in asset_dir.rglob("*") if p.is_file() and p.name.lower() == fl]
            if candidates:
                return choose_best(candidates)

    return None

def convert_text(text: str, src: Path, root: Path, idx_stem, idx_rel, imgs_by_name,
                 embed_mode: str, normalize_md_images: bool,
                 unknowns=None, log=None):
    unknowns = unknowns if unknowns is not None else set()
    def logmsg(s): 
        if log: log(s)

    # 1) Obsidian embeds
    def _repl_embed(m):
        raw = m.group(1)
        r = resolve_target(raw, src, root, idx_stem, idx_rel)
        if r.kind == "img" and r.path:
            alt, w, h = parse_obsidian_image_opts(r.label)
            alt_text = alt or r.path.stem
            url = make_rel_link(src, r.path, r.anchor)
            attrs = []
            if w is not None: attrs.append(f"width={w}")
            if h is not None: attrs.append(f"height={h}")
            logmsg(f"[img] {src.name}: ![[{raw}]] -> {url} {'{'+' '.join(attrs)+'}' if attrs else ''}")
            return f"![{alt_text}]({url})" + (("{" + " ".join(attrs) + "}") if attrs else "")
        if r.kind == "md" and r.path:
            if embed_mode == "inline" and MAX_INLINE_DEPTH > 0:
                try:
                    body = r.path.read_text(encoding="utf-8")
                    body = strip_front_matter(body)
                    body = convert_text(body, r.path, root, idx_stem, idx_rel, imgs_by_name,
                                        embed_mode, normalize_md_images,
                                        unknowns, log)
                    logmsg(f"[inline] {src.name} <= {r.path.name}")
                    return body.strip()
                except Exception as e:
                    logmsg(f"[inline-error] {r.path}: {e}")
            title = (r.label or r.path.stem) if r.label else r.path.stem
            url = make_rel_link(src, r.path, r.anchor)
            logmsg(f"[embed-link] {src.name}: ![[{raw}]] -> {url}")
            return f"[{title}]({url})"
        unknowns.add((str(src), raw))
        logmsg(f"[unresolved-embed] {src.name}: ![[{raw}]]")
        return m.group(0)

    text = RE_EMBED.sub(_repl_embed, text)

    # 2) Obsidian links
    def _repl_link(m):
        raw = m.group(1)
        r = resolve_target(raw, src, root, idx_stem, idx_rel)
        if r.kind == "img" and r.path:
            url = make_rel_link(src, r.path, r.anchor)
            logmsg(f"[img-link] {src.name}: [[{raw}]] -> {url}")
            return f"![]({url})"
        if r.kind == "md" and r.path:
            title = r.label or (f"{r.path.stem} — {r.anchor}" if r.anchor else r.path.stem)
            url = make_rel_link(src, r.path, r.anchor)
            logmsg(f"[link] {src.name}: [[{raw}]] -> {url}")
            return f"[{title}]({url})"
        if r.kind == "self":
            title = r.label or (r.anchor or "")
            if not title:
                return m.group(0)
            link = f"#{r.anchor.strip().replace(' ', '-').lower()}" if r.anchor else ""
            logmsg(f"[self-link] {src.name}: [[{raw}]] -> {link}")
            return f"[{title}]({link})"
        unknowns.add((str(src), raw))
        logmsg(f"[unresolved] {src.name}: [[{raw}]]")
        return m.group(0)

    text = RE_WIKI.sub(_repl_link, text)

    # 3) Normalize plain Markdown images
    if normalize_md_images:
        def _repl_md_image(m):
            alt = m.group("alt")
            url = m.group("url")

            # normalize slashes
            url_norm = url.replace("\\", "/")

            # leave absolute http/file as-is
            if "://" in url_norm or url_norm.startswith("file:/"):
                return f"![{alt}]({url_norm})"

            # Windows drive absolute: leave
            if re.match(r"^[A-Za-z]:/", url_norm):
                return f"![{alt}]({url_norm})"

            # If url already has '/', we still normalize but don't “resolve”
            if "/" in url_norm:
                if url_norm != url:
                    logmsg(f"[img-norm] {src.name}: {url} -> {url_norm}")
                return f"![{alt}]({url_norm})"

            # Bare filename -> use ASSET_MAP to locate it
            dst = resolve_bare_image_by_map(src, root, url_norm, {k.lower(): v for k, v in ASSET_MAP.items()})
            if not dst:
                # fallback: do nothing, but log miss
                logmsg(f"[img-miss] {src.name}: '{url_norm}' (no mapped asset found)")
                return f"![{alt}]({url_norm})"

            rel = Path(os.path.relpath(dst, start=src.parent)).as_posix()
            if rel != url:
                logmsg(f"[img-rel] {src.name}: {url} -> {rel}")
            return f"![{alt}]({rel})"

        text = RE_MD_IMAGE.sub(_repl_md_image, text)

    return text

def process_file(p: Path, root: Path, idx_stem, idx_rel, imgs_by_name,
                 embed_mode: str, normalize_md_images: bool,
                 dry_run=False, unknowns=None, log=None, stop_event: threading.Event | None = None):
    if p.suffix.lower() not in MD_EXTS:
        return
    if stop_event and stop_event.is_set():
        return
    try:
        orig = p.read_text(encoding="utf-8")
    except Exception as e:
        if log: log(f"[read-error] {p}: {e}")
        return
    converted = convert_text(
        orig, p, root, idx_stem, idx_rel, imgs_by_name,
        embed_mode, normalize_md_images,
        unknowns=unknowns, log=log
    )
    if converted != orig:
        if dry_run:
            if log: log(f"[dry] would write: {p}")
        else:
            try:
                p.write_text(converted, encoding="utf-8")
                if log: log(f"[write] {p}")
            except Exception as e:
                if log: log(f"[write-error] {p}: {e}")

# -------------------- GUI --------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Obsidian → Plain Markdown (Zettlr + MkDocs) — assets-aware for lore-/ + ALL_ASSET_DIRS (relative to Root)")
        self.geometry("1000x640")
        self.minsize(900, 540)

        self.root_path_var = tk.StringVar()
        self.embed_mode_var = tk.StringVar(value="link")
        self.dry_run_var = tk.BooleanVar(value=False)
        self.normalize_imgs_var = tk.BooleanVar(value=True)

        self._build_ui()

        self.log_q = queue.Queue()
        self.after(100, self._drain_log_queue)

        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        row1 = ttk.Frame(frm); row1.pack(fill="x", pady=(0,8))
        ttk.Label(row1, text="Root folder (vault or docs/):", width=30).pack(side="left")
        e = ttk.Entry(row1, textvariable=self.root_path_var)
        e.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row1, text="Browse…", command=self.choose_root).pack(side="left")
        ttk.Button(row1, text="Open", command=self.open_root).pack(side="left", padx=(6,0))

        row2 = ttk.Frame(frm); row2.pack(fill="x", pady=(0,8))
        ttk.Checkbutton(row2, text="Dry-run (don’t write files)", variable=self.dry_run_var).pack(side="left")
        ttk.Label(row2, text="Embeds:").pack(side="left", padx=(16,6))
        cmb = ttk.Combobox(row2, textvariable=self.embed_mode_var, values=["link","inline"], width=8, state="readonly")
        cmb.pack(side="left")
        ttk.Checkbutton(row2, text="Normalize Markdown image paths (slashes + map bare filenames)", variable=self.normalize_imgs_var).pack(side="left", padx=(16,0))

        # Mapping view (read-only hint)
        row_map = ttk.Frame(frm); row_map.pack(fill="x", pady=(0,8))
        ttk.Label(row_map, text="Asset mapping rules (prefix → assets):").pack(anchor="w")
        txt = ScrolledText(row_map, height=6)
        txt.pack(fill="x")
        txt.insert("1.0", "\n".join(f"- {k}  →  {v}" for k, v in ASSET_MAP.items()))
        txt.configure(state="disabled", font=("Consolas", 10))

        row3 = ttk.Frame(frm); row3.pack(fill="x", pady=(0,8))
        self.run_btn = ttk.Button(row3, text="Run", command=self.run_convert); self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(row3, text="Stop", command=self.stop_convert, state="disabled"); self.stop_btn.pack(side="left", padx=(6,0))
        ttk.Button(row3, text="Clear Log", command=self.clear_log).pack(side="left", padx=(12,0))

        self.log = ScrolledText(frm, height=18); self.log.pack(fill="both", expand=True)
        self.log.configure(font=("Consolas", 10), state="disabled")

        self.status = ttk.Label(self, text="Ready", anchor="w"); self.status.pack(fill="x", side="bottom")

    def choose_root(self):
        path = filedialog.askdirectory(title="Choose vault/docs root")
        if path:
            self.root_path_var.set(Path(path).as_posix())

    def open_root(self):
        p = self.root_path_var.get().strip()
        if not p: return
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{p}"')
            else:
                os.system(f'xdg-open "{p}"')
        except Exception as e:
            messagebox.showerror("Open error", str(e))

    def append_log(self, s: str):
        self.log_q.put(s)

    def _drain_log_queue(self):
        try:
            while True:
                s = self.log_q.get_nowait()
                self._write_log_line(s)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def _write_log_line(self, s: str):
        self.log.configure(state="normal")
        self.log.insert("end", s.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def run_convert(self):
        root_str = self.root_path_var.get().strip() or "."
        root = Path(root_str).resolve()
        if not root.is_dir():
            messagebox.showerror("Error", "Pick a valid folder.")
            return

        self.clear_log()
        self.append_log(f"[start] root = {root}")
        self.status.config(text="Indexing…")
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.stop_event.clear()

        def worker():
            try:
                idx_stem, idx_rel, imgs_by_name = build_index(root)
                self.append_log(f"[index] files indexed: stems={len(idx_stem)} rels={len(idx_rel)} imgs={sum(len(v) for v in imgs_by_name.values())}")

                unknowns = set()
                count = 0
                for p in sorted(root.rglob("*.md"), key=lambda x: str(x).lower()):
                    if self.stop_event.is_set():
                        self.append_log("[stop] requested, exiting.")
                        break
                    process_file(
                        p, root, idx_stem, idx_rel, imgs_by_name,
                        embed_mode=self.embed_mode_var.get(),
                        normalize_md_images=self.normalize_imgs_var.get(),
                        dry_run=self.dry_run_var.get(),
                        unknowns=unknowns,
                        log=lambda msg: self.append_log(msg),
                        stop_event=self.stop_event
                    )
                    count += 1
                    if count % 25 == 0:
                        self.status.config(text=f"Processed {count} files…")

                if unknowns:
                    self.append_log("\n[summary] Unresolved wikilinks/embeds:")
                    for src, raw in sorted(unknowns):
                        self.append_log(f"- {src}: [[{raw}]]")
                else:
                    self.append_log("\n[summary] All wikilinks/embeds resolved or none found.")

                self.append_log(f"[done] processed {count} file(s). dry_run={self.dry_run_var.get()} embeds={self.embed_mode_var.get()} normalize_imgs={self.normalize_imgs_var.get()}")
                self.status.config(text="Done.")
            except Exception as e:
                self.append_log(f"[fatal] {e}")
                self.status.config(text="Error.")
            finally:
                self.run_btn.config(state="normal")
                self.stop_btn.config(state="disabled")

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def stop_convert(self):
        self.stop_event.set()
        self.append_log("[stop] signal sent.")
        self.status.config(text="Stopping…")

# -------------------- CLI fallback --------------------
def cli_main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    ap.add_argument("root", nargs="?", help="Root folder")
    ap.add_argument("--embeds", choices=["link","inline"], default="link")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--normalize-images", action="store_true")
    args, _ = ap.parse_known_args()

    if not args.cli:
        return False

    root = Path(args.root or ".").resolve()
    print(f"[start] root={root} embeds={args.embeds} dry_run={args.dry_run} normalize_imgs={args.normalize_images}")
    idx_stem, idx_rel, imgs_by_name = build_index(root)
    unknowns = set()
    for p in root.rglob("*.md"):
        process_file(
            p, root, idx_stem, idx_rel, imgs_by_name,
            embed_mode=args.embeds,
            normalize_md_images=args.normalize_images,
            dry_run=args.dry_run,
            unknowns=unknowns,
            log=print
        )
    if unknowns:
        print("\n[summary] Unresolved:")
        for src, raw in sorted(unknowns):
            print(f"- {src}: [[{raw}]]")
    print("[done]")
    return True

if __name__ == "__main__":
    if not cli_main():
        # GUI
        import tkinter as tk  # noqa: F401 (ensures Tk is loaded in some environments)
        from tkinter import ttk  # noqa: F401
        app = App()
        app.mainloop()
