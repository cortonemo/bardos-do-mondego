#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge multiple .txt/.md files into a single output, with GUI.
If the final output exceeds a size threshold (default 20 MB),
the script will split into multiple parts (…_part01.ext, …_part02.ext, …).

- Choose and reorder input files
- Choose output directory and base filename
- Adjustable max part size (in MB)
- Log window with progress
- Progress bar

Author: ChatGPT
"""

import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

APP_TITLE = "Merge TXT/MD (with auto-split)"
DEFAULT_BASE_NAME = "merged.txt"
DEFAULT_MAX_MB = 20  # ChatGPT upload limit guidance

def human_bytes(n: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024

class MergeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("820x620")
        self.minsize(820, 620)

        self.files = []
        self.output_dir = tk.StringVar(value=str(Path.home()))
        self.base_name = tk.StringVar(value=DEFAULT_BASE_NAME)
        self.max_mb = tk.StringVar(value=str(DEFAULT_MAX_MB))

        self._build_ui()

    # --------------- UI ---------------
    def _build_ui(self):
        # Top controls frame
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        # File list + buttons
        file_frame = ttk.LabelFrame(top, text="Ficheiros a juntar")
        file_frame.pack(side="left", fill="both", expand=True, padx=(0,10))

        self.listbox = tk.Listbox(file_frame, height=12, selectmode=tk.EXTENDED, activestyle="dotbox")
        self.listbox.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)

        btns = ttk.Frame(file_frame)
        btns.pack(side="left", fill="y", padx=10, pady=10)

        ttk.Button(btns, text="Adicionar…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Remover", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Limpar", command=self.clear_files).pack(fill="x", pady=2)
        ttk.Separator(btns, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(btns, text="▲ Mover acima", command=lambda: self.move_selection(-1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="▼ Mover abaixo", command=lambda: self.move_selection(1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Ordenar A→Z", command=self.sort_files).pack(fill="x", pady=2)

        # Settings frame
        opts = ttk.LabelFrame(top, text="Opções de saída")
        opts.pack(side="right", fill="y")

        # Output directory
        row = ttk.Frame(opts)
        row.pack(fill="x", padx=10, pady=(10,4))
        ttk.Label(row, text="Diretoria de saída:").pack(side="left")
        self.out_entry = ttk.Entry(row, textvariable=self.output_dir, width=40)
        self.out_entry.pack(side="left", padx=6)
        ttk.Button(row, text="Escolher…", command=self.choose_output_dir).pack(side="left")

        # Base filename
        row2 = ttk.Frame(opts)
        row2.pack(fill="x", padx=10, pady=4)
        ttk.Label(row2, text="Nome base do ficheiro:").pack(side="left")
        self.base_entry = ttk.Entry(row2, textvariable=self.base_name, width=34)
        self.base_entry.pack(side="left", padx=6)

        # Max size
        row3 = ttk.Frame(opts)
        row3.pack(fill="x", padx=10, pady=4)
        ttk.Label(row3, text="Tamanho máx. por parte (MB):").pack(side="left")
        self.max_entry = ttk.Entry(row3, textvariable=self.max_mb, width=8)
        self.max_entry.pack(side="left", padx=6)

        # Progress bar
        self.progress = ttk.Progressbar(opts, orient="horizontal", mode="determinate", length=250)
        self.progress.pack(padx=10, pady=(8,10))

        # Start button
        self.start_btn = ttk.Button(opts, text="Juntar e Dividir", command=self.start_merge_thread)
        self.start_btn.pack(padx=10, pady=(0,10), fill="x")

        # Log
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))

        self.log = ScrolledText(log_frame, height=14, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=10, pady=10)

        # Footer tips
        foot = ttk.Frame(self, padding=(10,0,10,10))
        foot.pack(fill="x")
        ttk.Label(foot, text="Dica: 20 MB é o limite prático para upload no ChatGPT. Ajusta se precisares.").pack(anchor="w")

    # --------------- File list ops ---------------
    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleciona ficheiros .txt ou .md",
            filetypes=[("Text/Markdown", "*.txt *.md"), ("Todos", "*.*")]
        )
        if not paths:
            return
        added = 0
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                added += 1
        if added:
            self.refresh_listbox()
            self.log_msg(f"Adicionados {added} ficheiro(s).")

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        sel.reverse()
        for idx in sel:
            try:
                removed = self.files.pop(idx)
                self.log_msg(f"Removido: {removed}")
            except IndexError:
                pass
        self.refresh_listbox()

    def clear_files(self):
        self.files.clear()
        self.refresh_listbox()
        self.log_msg("Lista de ficheiros limpa.")

    def move_selection(self, direction: int):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        if direction > 0:
            sel = sel[::-1]  # move down from bottom
        for idx in sel:
            new_idx = idx + direction
            if 0 <= new_idx < len(self.files):
                self.files[idx], self.files[new_idx] = self.files[new_idx], self.files[idx]
        self.refresh_listbox()
        # Reselect moved items
        self.listbox.selection_clear(0, tk.END)
        for idx in [i + direction for i in sel[::-1] if 0 <= i + direction < len(self.files)]:
            self.listbox.selection_set(idx)

    def sort_files(self):
        self.files.sort(key=lambda p: Path(p).name.lower())
        self.refresh_listbox()
        self.log_msg("Ficheiros ordenados A→Z.")

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for p in self.files:
            self.listbox.insert(tk.END, p)

    # --------------- Output opts ---------------
    def choose_output_dir(self):
        d = filedialog.askdirectory(title="Escolhe a diretoria de saída", mustexist=True)
        if d:
            self.output_dir.set(d)

    # --------------- Logging helpers ---------------
    def log_msg(self, msg: str):
        def _append():
            self.log.configure(state="normal")
            self.log.insert(tk.END, msg + "\n")
            self.log.see(tk.END)
            self.log.configure(state="disabled")
        self.after(0, _append)

    def set_progress(self, value: float):
        self.after(0, lambda: self.progress.configure(value=value))

    def set_progress_max(self, maximum: float):
        self.after(0, lambda: self.progress.configure(maximum=maximum))

    def set_ui_state(self, enabled: bool):
        def _set():
            state = "normal" if enabled else "disabled"
            for w in [self.start_btn, self.out_entry, self.base_entry, self.max_entry, self.listbox]:
                w.configure(state=state)
        self.after(0, _set)

    # --------------- Merge logic ---------------
    def start_merge_thread(self):
        t = threading.Thread(target=self._merge_and_split, daemon=True)
        t.start()

    def _merge_and_split(self):
        if not self.files:
            messagebox.showwarning("Aviso", "Adiciona pelo menos um ficheiro.")
            return
        out_dir = Path(self.output_dir.get()).expanduser()
        if not out_dir.exists():
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível criar a diretoria:\n{e}")
                return

        base = self.base_name.get().strip() or DEFAULT_BASE_NAME
        # Ensure base has an extension
        base_root, base_ext = os.path.splitext(base)
        if not base_ext:
            base_ext = ".txt"
        # Validate chunk size
        try:
            max_mb = float(self.max_mb.get().replace(",", ".").strip())
            if max_mb <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Erro", "Tamanho máx. por parte inválido.")
            return

        chunk_size = int(max_mb * 1024 * 1024)

        # Confirm overwrite of existing parts
        existing = list(out_dir.glob(f"{base_root}_part*{base_ext}")) + [out_dir / f"{base_root}{base_ext}"]
        if any(p.exists() for p in existing):
            if not messagebox.askyesno("Confirmar", "Ficheiros de saída com o mesmo nome já existem. Substituir?"):
                return

        self.set_ui_state(False)
        self.log_msg(f"Início da junção: {len(self.files)} ficheiro(s).")
        self.log_msg(f"Saída: {out_dir}")
        self.log_msg(f"Base: {base_root}{base_ext}")
        self.log_msg(f"Máx. por parte: {max_mb:.2f} MB")

        # Calculate total size for progress (approx via encoded length)
        total_bytes = 0
        for p in self.files:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    total_bytes += len(f.read().encode("utf-8"))
            except Exception as e:
                self.log_msg(f"[Aviso] Não foi possível medir {p}: {e}")

        self.set_progress_max(total_bytes if total_bytes > 0 else 1)
        processed = 0

        # Prepare output
        part_idx = 1
        current_path = out_dir / (f"{base_root}{base_ext}" if chunk_size >= total_bytes > 0 else f"{base_root}_part{part_idx:02d}{base_ext}")
        current_file = open(current_path, "wb")
        current_size = 0
        written_files = set()

        try:
            for i, p in enumerate(self.files, start=1):
                path = Path(p)
                self.log_msg(f"Lendo [{i}/{len(self.files)}]: {path.name}")
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception as e:
                    self.log_msg(f"[Erro] A ler {path}: {e}")
                    continue

                # Separator header between files (commented out by default)
                header = f"\n\n<!-- ==== {path.name} ==== -->\n\n" if current_size > 0 else ""
                blob = (header + content).encode("utf-8")

                # Write in chunks to respect max part size even if one file is huge
                offset = 0
                while offset < len(blob):
                    space_left = chunk_size - current_size if chunk_size > 0 else len(blob)
                    if space_left <= 0:
                        current_file.close()
                        written_files.add(current_path)
                        part_idx += 1
                        current_path = out_dir / f"{base_root}_part{part_idx:02d}{base_ext}"
                        self.log_msg(f"[Split] Novo ficheiro: {current_path.name}")
                        current_file = open(current_path, "wb")
                        current_size = 0
                        space_left = chunk_size

                    chunk = blob[offset: offset + space_left]
                    current_file.write(chunk)
                    current_size += len(chunk)
                    offset += len(chunk)

                    processed += len(chunk)
                    self.set_progress(processed)

            # Done
            current_file.close()
            written_files.add(current_path)
            self.log_msg("Concluído.")
            self.log_msg("Ficheiros gerados:")
            for p in sorted(written_files):
                try:
                    sz = p.stat().st_size
                    self.log_msg(f" - {p.name}  ({human_bytes(sz)})")
                except Exception:
                    self.log_msg(f" - {p.name}")

            # Open output directory prompt
            try:
                if messagebox.askyesno("Abrir pasta", "Queres abrir a pasta de saída?"):
                    self._reveal_in_explorer(out_dir)
            except Exception:
                pass

        except Exception as e:
            try:
                current_file.close()
            except Exception:
                pass
            messagebox.showerror("Erro", f"Ocorreu um erro durante a junção:\n{e}")
            self.log_msg(f"[Erro] {e}")
        finally:
            self.set_ui_state(True)

    def _reveal_in_explorer(self, path: Path):
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')


def main():
    app = MergeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
