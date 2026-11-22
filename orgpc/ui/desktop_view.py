"""Vista Escritorio: analiza el escritorio y lo ordena en carpetas por categoría."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import organizer
from ..classify import CATEGORY_COLOR, CATEGORY_ICON, CATEGORY_NAMES
from ..platform_utils import human_size, open_target, public_desktop, user_desktop
from .widgets import (ACCENT, ACCENT_HOVER, BORDER, MUTED, SURFACE2, TEXT, Card, emoji_font, font,
                      ghost_button, header, primary_button)


class DesktopView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.items = []
        self.rows = []
        cfg = app.config_data

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(24, 12))
        self.head = header(top, "Organizar escritorio",
                           "Agrupa juegos, programas, documentos, fotos… en carpetas, con un clic.")
        self.head.pack(side="left")
        self.undo_btn = ghost_button(top, "↩  Deshacer última", self.undo, width=150)
        self.undo_btn.pack(side="right")
        self.org_btn = primary_button(top, "✨  Organizar ahora", self.organize, width=170)
        self.org_btn.pack(side="right", padx=8)
        ghost_button(top, "🔍  Analizar", self.analyze, width=110).pack(side="right")

        # ---------------- opciones
        opts = Card(self)
        opts.pack(fill="x", padx=28, pady=(0, 10))
        r1 = ctk.CTkFrame(opts, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(r1, text="📂  Carpeta destino:", font=font(13, "bold")).pack(side="left")
        self.dest_label = ctk.CTkLabel(r1, text="", font=font(13), text_color=MUTED)
        self.dest_label.pack(side="left", padx=8)
        ghost_button(r1, "Abrir", lambda: open_target(self.dest()), width=70, height=30).pack(side="right")
        ghost_button(r1, "Restablecer", self.reset_dest, width=100, height=30).pack(side="right", padx=6)
        ghost_button(r1, "Cambiar…", self.change_dest, width=90, height=30).pack(side="right")

        r2 = ctk.CTkFrame(opts, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(4, 12))
        self.v_public = ctk.BooleanVar(value=cfg.get("include_public", True))
        self.v_folders = ctk.BooleanVar(value=cfg.get("move_folders", False))
        self.v_lib = ctk.BooleanVar(value=cfg.get("add_to_library", True))
        for text, var in (("Incluir el escritorio público (accesos de todos los usuarios)", self.v_public),
                          ("Mover también carpetas", self.v_folders),
                          ("Añadir juegos y programas a la Biblioteca", self.v_lib)):
            ctk.CTkCheckBox(r2, text=text, variable=var, font=font(12), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                            command=self._save_opts).pack(side="left", padx=(0, 18))

        # ---------------- resumen por categorías
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.pack(fill="x", padx=28, pady=(0, 6))
        disabled = set(cfg.get("organize_disabled", []))
        self.cat_vars = {c: ctk.BooleanVar(value=c not in disabled) for c in CATEGORY_NAMES}

        # ---------------- lista
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self.list.grid_columnconfigure(1, weight=1)
        self.empty = ctk.CTkLabel(self.list, text="Pulsa «Analizar» para ver qué hay en tu escritorio.",
                                  font=font(14), text_color=MUTED)
        self.empty.grid(row=0, column=0, columnspan=4, pady=40)
        self._update_dest()
        self._update_undo()

    # ------------------------------------------------------------ opciones
    def dest(self):
        return self.app.config_data.get("dest_dir") or user_desktop()

    def _update_dest(self):
        d = self.dest()
        short = d if len(d) <= 60 else d[:22] + "…" + d[-36:]
        self.dest_label.configure(text=short + ("   (en el escritorio)" if d == user_desktop() else ""))

    def change_dest(self):
        p = filedialog.askdirectory(parent=self, title="¿Dónde quieres crear las carpetas?")
        if p:
            self.app.config_data["dest_dir"] = os.path.normpath(p)
            self.app.save_config()
            self._update_dest()

    def reset_dest(self):
        self.app.config_data["dest_dir"] = ""
        self.app.save_config()
        self._update_dest()

    def _save_opts(self):
        c = self.app.config_data
        c["include_public"] = self.v_public.get()
        c["move_folders"] = self.v_folders.get()
        c["add_to_library"] = self.v_lib.get()
        c["organize_disabled"] = [k for k, v in self.cat_vars.items() if not v.get()]
        self.app.save_config()

    def _update_undo(self):
        date = organizer.last_history_date()
        self.undo_btn.configure(state="normal" if date else "disabled",
                                text=f"↩  Deshacer ({date[-5:]})" if date else "↩  Deshacer última")

    def source_dirs(self):
        dirs = [user_desktop()]
        if self.v_public.get():
            p = public_desktop()
            if p:
                dirs.append(p)
        return dirs

    # ------------------------------------------------------------ análisis
    def analyze(self, then=None):
        self.app.notify("Analizando el escritorio…")
        dirs, dest, folders = self.source_dirs(), self.dest(), self.v_folders.get()

        def done(items, err):
            if err:
                messagebox.showerror("Error", str(err), parent=self)
                return
            self.items = items
            self.render()
            self.app.notify(f"{len(items)} elementos encontrados en el escritorio")
            if then:
                then()
        self.app.run_bg(lambda: organizer.scan(dirs, dest, folders), done)

    def render(self):
        for w in self.summary.winfo_children():
            w.destroy()
        for w in self.rows:
            w.destroy()
        self.rows = []

        counts, sizes = {}, {}
        for it in self.items:
            counts[it["category"]] = counts.get(it["category"], 0) + 1
            sizes[it["category"]] = sizes.get(it["category"], 0) + it.get("size", 0)

        col = 0
        for c in CATEGORY_NAMES:
            if not counts.get(c):
                continue
            tile = Card(self.summary, corner_radius=12)
            tile.grid(row=col // 6, column=col % 6, padx=(0, 10), pady=(0, 10), sticky="ew")
            self.summary.grid_columnconfigure(col % 6, weight=1)
            col += 1
            top = ctk.CTkFrame(tile, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 0))
            ctk.CTkLabel(top, text=CATEGORY_ICON[c], font=emoji_font(20), width=34, height=34, corner_radius=8,
                         fg_color=CATEGORY_COLOR[c], text_color="#fff").pack(side="left")
            ctk.CTkCheckBox(top, text="", variable=self.cat_vars[c], width=20, fg_color=ACCENT,
                            hover_color=ACCENT_HOVER, command=self._save_opts).pack(side="right")
            ctk.CTkLabel(tile, text=c, font=font(13, "bold"), anchor="w").pack(fill="x", padx=12, pady=(6, 0))
            ctk.CTkLabel(tile, text=f"{counts[c]} elemento{'s' if counts[c] != 1 else ''} · {human_size(sizes[c])}", font=font(11),
                         text_color=MUTED, anchor="w").pack(fill="x", padx=12, pady=(0, 10))

        if not self.items:
            self.empty.configure(text="🎉  Tu escritorio ya está ordenado: no hay nada suelto que mover.")
            self.empty.grid(row=0, column=0, columnspan=4, pady=40)
            return
        self.empty.grid_forget()

        udesk = os.path.normcase(user_desktop())
        for i, it in enumerate(self.items):
            row = ctk.CTkFrame(self.list, fg_color=("#ffffff", "#181b22") if i % 2 == 0 else "transparent",
                               corner_radius=8, height=40)
            row.grid(row=i, column=0, columnspan=4, sticky="ew", pady=1)
            row.grid_columnconfigure(1, weight=1)
            self.rows.append(row)
            icon = ctk.CTkLabel(row, text=CATEGORY_ICON[it["category"]], font=emoji_font(16), width=30)
            icon.grid(row=0, column=0, padx=(10, 6), pady=6)
            ctk.CTkLabel(row, text=it["name"], font=font(13), anchor="w").grid(row=0, column=1, sticky="ew")
            where = "Escritorio" if os.path.normcase(it["source_dir"]) == udesk else "Escritorio público"
            ctk.CTkLabel(row, text=f"{where} · {human_size(it.get('size', 0))}", font=font(11),
                         text_color=MUTED, width=170, anchor="e").grid(row=0, column=2, padx=10)
            om = ctk.CTkOptionMenu(row, values=CATEGORY_NAMES, width=140, height=28, font=font(12),
                                   fg_color=SURFACE2, button_color=SURFACE2, button_hover_color=BORDER,
                                   text_color=TEXT,
                                   command=lambda v, it=it, ic=icon: self._override(it, v, ic))
            om.set(it["category"])
            om.grid(row=0, column=3, padx=(0, 10))

    def _override(self, item, cat, icon_label):
        item["category"] = cat
        icon_label.configure(text=CATEGORY_ICON[cat])
        self.render()

    # ------------------------------------------------------------ acciones
    def organize(self, silent=False):
        if not self.items:
            self.analyze(then=lambda: self.organize(silent) if self.items else None)
            return
        self._save_opts()
        enabled = {c for c, v in self.cat_vars.items() if v.get()}
        moves = organizer.plan(self.items, self.dest(), enabled)
        if not moves:
            if not silent:
                messagebox.showinfo("Nada que mover", "No hay elementos en las categorías seleccionadas.", parent=self)
            return
        if not silent:
            cats = sorted({os.path.basename(os.path.dirname(d)) for _, d in moves})
            if not messagebox.askyesno(
                    "Organizar escritorio",
                    f"Se moverán {len(moves)} elementos a estas carpetas:\n\n  " + ", ".join(cats) +
                    f"\n\ndentro de:\n{self.dest()}\n\nPodrás deshacerlo con «Deshacer». ¿Continuar?", parent=self):
                return
        add_lib = self.v_lib.get()

        def work():
            done, errors = organizer.execute(moves)
            self.app.library.remap_paths(done)
            added = 0
            if add_lib:
                added, _ = self.app.library.scan_and_import(["Escritorio"])
            return done, errors, added

        def finished(res, err):
            if err:
                messagebox.showerror("Error", str(err), parent=self)
                return
            done, errors, added = res
            msg = f"✨ {len(done)} elementos organizados"
            if added:
                msg += f" · {added} añadidos a la Biblioteca"
            self.app.notify(msg)
            if errors:
                detail = "\n".join(f"• {os.path.basename(s)}: {e}" for s, e in errors[:12])
                hint = ("\n\nLos accesos del escritorio público necesitan permisos de administrador."
                        if any("ermiso" in e or "denied" in e.lower() or "Access" in e for _, e in errors) else "")
                messagebox.showwarning("Algunos elementos no se movieron",
                                       f"No se pudieron mover {len(errors)} elementos:\n\n{detail}{hint}", parent=self)
            self._update_undo()
            self.app.views["library"].refresh()
            self.app.views["library"].load_icons_async()
            self.analyze()
        self.app.run_bg(work, finished)

    def undo(self):
        date = organizer.last_history_date()
        if not date or not messagebox.askyesno("Deshacer", f"¿Devolver al escritorio lo que se organizó el {date}?",
                                               parent=self):
            return

        def work():
            restored, errors = organizer.undo_last()
            self.app.library.remap_paths(restored)
            return restored, errors

        def finished(res, err):
            if err:
                messagebox.showerror("Error", str(err), parent=self)
                return
            restored, errors = res
            self.app.notify(f"↩ {len(restored)} elementos devueltos a su sitio")
            if errors:
                messagebox.showwarning("Aviso", f"{len(errors)} elementos no se pudieron devolver.", parent=self)
            self._update_undo()
            self.app.views["library"].refresh()
            self.analyze()
        self.app.run_bg(work, finished)
