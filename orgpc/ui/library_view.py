"""Vista Biblioteca: todos tus juegos y programas en un solo sitio."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..classify import CATEGORY_COLOR, CATEGORY_ICON, CATEGORY_NAMES, classify_path
from ..library import _is_url, extract_icons, icon_path_for
from ..platform_utils import reveal_in_explorer
from .widgets import (ACCENT, ACCENT_HOVER, BORDER, MUTED, SURFACE, SURFACE2, TEXT, WARNING, Card, Dialog,
                      emoji_font, font, ghost_button, header, popup_menu, primary_button)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

CARD_W = 214
BANNER_H = 100
SORTS = ["Nombre", "Más usados", "Recientes", "Añadidos"]
ALL = "Todos"
FAVS = "★ Favoritos"


class ItemCard(Card):
    def __init__(self, master, view, item):
        super().__init__(master, width=CARD_W, height=232, corner_radius=14)
        self.view = view
        self.item = item
        self.grid_propagate(False)
        self.pack_propagate(False)

        self.banner = ctk.CTkLabel(self, text="", height=BANNER_H, corner_radius=10)
        self.banner.pack(fill="x", padx=6, pady=(6, 4))
        self.name = ctk.CTkLabel(self, text="", font=font(14, "bold"), text_color=TEXT, anchor="w",
                                 justify="left", wraplength=CARD_W - 24)
        self.name.pack(fill="x", padx=12)
        self.meta = ctk.CTkLabel(self, text="", font=font(11), text_color=MUTED, anchor="w")
        self.meta.pack(fill="x", padx=12)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="bottom", fill="x", padx=10, pady=10)
        ctk.CTkButton(row, text="▶  Abrir", width=90, height=32, corner_radius=8, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, font=font(12, "bold"),
                      command=lambda: view.launch(self.item)).pack(side="left", fill="x", expand=True)
        self.fav = ctk.CTkButton(row, text="☆", width=34, height=32, corner_radius=8, fg_color=SURFACE2,
                                 hover_color=BORDER, text_color=TEXT, font=font(15),
                                 command=lambda: view.toggle_fav(self.item))
        self.fav.pack(side="left", padx=(6, 0))
        self.more = ctk.CTkButton(row, text="⋯", width=34, height=32, corner_radius=8, fg_color=SURFACE2,
                                  hover_color=BORDER, text_color=TEXT, font=font(15),
                                  command=lambda: view.item_menu(self.item, self.more))
        self.more.pack(side="left", padx=(6, 0))

        for w in (self.banner, self.name, self.meta, self):
            w.bind("<Double-Button-1>", lambda e: view.launch(self.item))
            w.bind("<Button-3>", lambda e: view.item_menu(self.item, self.more))
        self.update_from_item()

    def update_from_item(self):
        it = self.item
        cat = it.get("category", "Otros")
        name = it.get("name", "")
        self.name.configure(text=name if len(name) <= 44 else name[:42] + "…")
        uses = it.get("launches", 0)
        meta = f"{it.get('source', 'manual')}  ·  {cat}"
        if uses:
            meta += f"  ·  {uses} uso{'s' if uses != 1 else ''}"
        broken = self.view.app.library.is_broken(it)
        self.meta.configure(text="⚠ No encontrado" if broken else meta,
                            text_color=WARNING if broken else MUTED)
        self.fav.configure(text="★" if it.get("favorite") else "☆",
                           text_color="#f5b301" if it.get("favorite") else TEXT)
        img = self.view.image_for(it)
        color = CATEGORY_COLOR.get(cat, "#6b7280")
        if img is not None and img[1] == "banner":
            self.banner.configure(image=img[0], text="", fg_color="transparent")
        elif img is not None:
            self.banner.configure(image=img[0], text="", fg_color=color)
        else:
            self.banner.configure(image=None, text=CATEGORY_ICON.get(cat, "📎"), font=emoji_font(38),
                                  fg_color=color, text_color="#ffffff")


class LibraryView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.cards = {}
        self.images = {}
        self.cols = 0
        self._gen = 0
        self._order = []
        self.category = ALL
        self.label_to_cat = {}

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(24, 10))
        self.head = header(top, "Biblioteca", "Tus juegos y programas, ordenados en un solo lugar.")
        self.head.pack(side="left")
        primary_button(top, "➕  Añadir", self.add_dialog, width=110).pack(side="right")
        ghost_button(top, "🔄  Detectar juegos y programas", self.detect_dialog, width=230).pack(side="right", padx=8)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=28, pady=(0, 6))
        self.search = ctk.CTkEntry(bar, placeholder_text="🔍  Buscar…", height=36, corner_radius=10,
                                   width=280, font=font(13), border_color=BORDER, fg_color=SURFACE)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        self.sort = ctk.CTkOptionMenu(bar, values=SORTS, command=lambda v: self.refresh(), height=36, width=140,
                                      corner_radius=10, font=font(13), fg_color=SURFACE2, button_color=SURFACE2,
                                      button_hover_color=BORDER, text_color=TEXT)
        self.sort.set(app.config_data.get("sort", "Nombre"))
        self.sort.pack(side="right")
        ctk.CTkLabel(bar, text="Ordenar:", font=font(13), text_color=MUTED).pack(side="right", padx=8)

        self.chips = ctk.CTkSegmentedButton(self, values=[ALL], command=self._on_chip, height=32,
                                            font=font(12), selected_color=ACCENT,
                                            selected_hover_color=ACCENT_HOVER)
        self.chips.pack(anchor="w", padx=28, pady=(6, 8))
        self.chips.set(ALL)

        self.grid_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grid_area.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self.grid_area.bind("<Configure>", self._on_resize)

        self.empty = ctk.CTkFrame(self.grid_area, fg_color="transparent")
        ctk.CTkLabel(self.empty, text="🎮", font=emoji_font(56)).pack(pady=(60, 6))
        self.empty_title = ctk.CTkLabel(self.empty, text="Tu biblioteca está vacía", font=font(18, "bold"))
        self.empty_title.pack()
        self.empty_sub = ctk.CTkLabel(self.empty, text="Pulsa «Detectar juegos y programas» para buscar Steam, Epic,\n"
                                                       "GOG y los accesos de tu escritorio, o añade cosas a mano.",
                                      font=font(13), text_color=MUTED)
        self.empty_sub.pack(pady=6)

    # ------------------------------------------------------------ imágenes
    def image_for(self, item):
        if Image is None:
            return None
        path, kind = item.get("image"), "banner"
        if not path or not os.path.exists(path):
            path, kind = icon_path_for(item), "icon"
            if not path or not os.path.exists(path):
                return None
        if path in self.images:
            return self.images[path]
        try:
            im = Image.open(path)
            im.load()
            if kind == "banner":
                w = CARD_W - 12
                h = BANNER_H
                ratio = max(w / im.width, h / im.height)
                im = im.resize((int(im.width * ratio) + 1, int(im.height * ratio) + 1))
                left = (im.width - w) // 2
                top = (im.height - h) // 2
                im = im.crop((left, top, left + w, top + h))
                ci = ctk.CTkImage(light_image=im, dark_image=im, size=(w, h))
            else:
                ci = ctk.CTkImage(light_image=im, dark_image=im, size=(52, 52))
        except Exception:  # noqa: BLE001
            return None
        self.images[path] = (ci, kind)
        return self.images[path]

    def load_icons_async(self):
        items = list(self.app.library.items)

        def done(n, err):
            if n:
                for c in self.cards.values():
                    c.update_from_item()
        self.app.run_bg(lambda: extract_icons(items), done)

    # ------------------------------------------------------------ filtros
    def _on_chip(self, label):
        self.category = self.label_to_cat.get(label, ALL)
        self.refresh()

    def _update_chips(self):
        items = self.app.library.items
        counts = {}
        for it in items:
            counts[it.get("category", "Otros")] = counts.get(it.get("category", "Otros"), 0) + 1
        favs = sum(1 for i in items if i.get("favorite"))
        labels = [f"{ALL} ({len(items)})"]
        self.label_to_cat = {labels[0]: ALL}
        if favs:
            labels.append(f"{FAVS} ({favs})")
            self.label_to_cat[labels[-1]] = FAVS
        for c in CATEGORY_NAMES:
            if counts.get(c):
                lab = f"{CATEGORY_ICON[c]} {c} ({counts[c]})"
                labels.append(lab)
                self.label_to_cat[lab] = c
        if self.category not in self.label_to_cat.values():
            self.category = ALL
        self.chips.configure(values=labels)
        current = next(l for l, c in self.label_to_cat.items() if c == self.category)
        self.chips.set(current)

    def filtered(self):
        q = self.search.get().strip().lower()
        out = []
        for it in self.app.library.items:
            if self.category == FAVS and not it.get("favorite"):
                continue
            if self.category not in (ALL, FAVS) and it.get("category") != self.category:
                continue
            if q and q not in it.get("name", "").lower() and q not in it.get("source", "").lower():
                continue
            out.append(it)
        mode = self.sort.get()
        if mode == "Más usados":
            out.sort(key=lambda i: (-i.get("launches", 0), i["name"].lower()))
        elif mode == "Recientes":
            out.sort(key=lambda i: (-i.get("last_launched", 0), i["name"].lower()))
        elif mode == "Añadidos":
            out.sort(key=lambda i: -i.get("added", 0))
        else:
            out.sort(key=lambda i: (not i.get("favorite"), i["name"].lower()))
        return out

    # ------------------------------------------------------------ grid
    def _on_resize(self, event):
        cols = max(1, (event.width - 10) // (CARD_W + 16))
        if cols != self.cols:
            self.cols = cols
            self._regrid()

    def _regrid(self):
        for idx, it in enumerate(self._order):
            c = self.cards.get(it["id"])
            if c:
                c.grid(row=idx // max(1, self.cols), column=idx % max(1, self.cols), padx=8, pady=8, sticky="n")

    def refresh(self, rebuild=False):
        self.app.config_data["sort"] = self.sort.get()
        self._update_chips()
        ids = {i["id"] for i in self.app.library.items}
        for cid in list(self.cards):
            if rebuild or cid not in ids:
                self.cards.pop(cid).destroy()
        for c in self.cards.values():
            c.grid_forget()
        self._order = self.filtered()
        self._gen += 1
        if not self._order:
            if self.app.library.items:
                self.empty_title.configure(text="No hay resultados")
                self.empty_sub.configure(text="Prueba con otra búsqueda o categoría.")
            else:
                self.empty_title.configure(text="Tu biblioteca está vacía")
                self.empty_sub.configure(text="Pulsa «Detectar juegos y programas» para buscar Steam, Epic,\n"
                                              "GOG y los accesos de tu escritorio, o añade cosas a mano.")
            self.empty.grid(row=0, column=0, columnspan=max(1, self.cols), sticky="ew")
            return
        self.empty.grid_forget()
        self.head.subtitle.configure(text=f"{len(self.app.library.items)} elementos · "
                                          "doble clic para abrir, clic derecho para más opciones")
        self._place(self._gen, 0)

    def _place(self, gen, start):
        if gen != self._gen:
            return
        cols = max(1, self.cols or 4)
        end = min(start + 18, len(self._order))
        for idx in range(start, end):
            it = self._order[idx]
            card = self.cards.get(it["id"])
            if card is None:
                card = ItemCard(self.grid_area, self, it)
                self.cards[it["id"]] = card
            else:
                card.item = it
            card.grid(row=idx // cols, column=idx % cols, padx=8, pady=8, sticky="n")
        if end < len(self._order):
            self.after(15, self._place, gen, end)

    # ------------------------------------------------------------ acciones
    def launch(self, item):
        try:
            self.app.library.launch(item)
            self.app.notify(f"Abriendo {item['name']}…")
            c = self.cards.get(item["id"])
            if c:
                c.update_from_item()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("No se pudo abrir", f"{item['name']}\n\n{e}", parent=self)

    def toggle_fav(self, item):
        item["favorite"] = not item.get("favorite")
        self.app.library.save()
        self.refresh()

    def item_menu(self, item, widget):
        cats = [(f"{CATEGORY_ICON[c]}  {c}", lambda c=c: self.set_category(item, c)) for c in CATEGORY_NAMES]
        entries = [("▶  Abrir", lambda: self.launch(item))]
        loc = self.app.library.location_of(item)
        if loc:
            entries.append(("📂  Abrir ubicación", lambda: reveal_in_explorer(loc)))
        entries += [
            ("✏  Renombrar…", lambda: self.rename(item)),
            ("🏷  Cambiar categoría", cats),
            ("★  Quitar de favoritos" if item.get("favorite") else "☆  Añadir a favoritos",
             lambda: self.toggle_fav(item)),
            None,
            ("🗑  Quitar de la biblioteca", lambda: self.remove(item)),
        ]
        popup_menu(widget, entries)

    def set_category(self, item, cat):
        item["category"] = cat
        self.app.library.save()
        c = self.cards.get(item["id"])
        if c:
            c.update_from_item()
        self.refresh()

    def rename(self, item):
        d = ctk.CTkInputDialog(text=f"Nuevo nombre para «{item['name']}»:", title="Renombrar")
        new = d.get_input()
        if new and new.strip():
            item["name"] = new.strip()
            self.app.library.save()
            c = self.cards.get(item["id"])
            if c:
                c.update_from_item()
            self.refresh()

    def remove(self, item):
        if messagebox.askyesno("Quitar", f"¿Quitar «{item['name']}» de la biblioteca?\n"
                                         "(No se borra nada de tu PC)", parent=self):
            self.app.library.remove(item["id"])
            self.refresh()

    def add_dialog(self):
        AddDialog(self.app, self)

    def detect_dialog(self):
        DetectDialog(self.app, self)

    def run_detection(self, sources, quiet=False):
        if not quiet:
            self.app.notify("Buscando juegos y programas…")

        def done(res, err):
            if err:
                if not quiet:
                    messagebox.showerror("Error", str(err), parent=self)
                return
            added, found = res
            detail = ", ".join(f"{k}: {v}" for k, v in found.items() if v)
            if not quiet or added:
                self.app.notify(f"Añadidos {added} elementos nuevos" + (f"  ({detail})" if detail else ""))
            self.refresh()
            self.load_icons_async()
        self.app.run_bg(lambda: self.app.library.scan_and_import(sources), done)


class DetectDialog(Dialog):
    SOURCES = [("Escritorio", "Accesos directos de tu escritorio", True),
               ("Steam", "Juegos instalados en Steam", True),
               ("Epic Games", "Juegos instalados en Epic Games", True),
               ("GOG", "Juegos de GOG Galaxy", True),
               ("Menú Inicio", "Todos los programas del menú Inicio (pueden ser muchos)", False)]

    def __init__(self, app, view):
        super().__init__(app, "Detectar juegos y programas", 600, 410)
        self.view = view
        ctk.CTkLabel(self, text="¿Dónde quieres buscar?", font=font(18, "bold")).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self, text="Solo se añade lo que no esté ya en la biblioteca.", font=font(12),
                     text_color=MUTED).pack(anchor="w", padx=24, pady=(0, 10))
        self.vars = {}
        for name, desc, default in self.SOURCES:
            v = ctk.BooleanVar(value=default)
            self.vars[name] = v
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=4)
            ctk.CTkCheckBox(row, text=name, variable=v, font=font(13, "bold"), fg_color=ACCENT,
                            hover_color=ACCENT_HOVER).pack(side="left")
            ctk.CTkLabel(row, text=desc, font=font(12), text_color=MUTED).pack(side="left", padx=10)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(side="bottom", fill="x", padx=24, pady=20)
        primary_button(btns, "Detectar", self.go, width=120).pack(side="right")
        ghost_button(btns, "Cancelar", self.destroy, width=100).pack(side="right", padx=8)

    def go(self):
        sources = [k for k, v in self.vars.items() if v.get()]
        self.destroy()
        if sources:
            self.view.run_detection(sources)


class AddDialog(Dialog):
    def __init__(self, app, view):
        super().__init__(app, "Añadir a la biblioteca", 520, 380)
        self.app = app
        self.view = view
        ctk.CTkLabel(self, text="Añadir a la biblioteca", font=font(18, "bold")).pack(anchor="w", padx=24, pady=(20, 10))

        ctk.CTkLabel(self, text="Programa, archivo, carpeta o dirección web", font=font(12),
                     text_color=MUTED).pack(anchor="w", padx=24)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(2, 10))
        self.target = ctk.CTkEntry(row, height=34, placeholder_text="C:\\Juegos\\juego.exe  o  https://…")
        self.target.pack(side="left", fill="x", expand=True)
        ghost_button(row, "Archivo…", self.pick_file, width=84, height=34).pack(side="left", padx=(6, 0))
        ghost_button(row, "Carpeta…", self.pick_dir, width=84, height=34).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(self, text="Nombre", font=font(12), text_color=MUTED).pack(anchor="w", padx=24)
        self.name = ctk.CTkEntry(self, height=34)
        self.name.pack(fill="x", padx=24, pady=(2, 10))

        ctk.CTkLabel(self, text="Categoría", font=font(12), text_color=MUTED).pack(anchor="w", padx=24)
        self.cat = ctk.CTkOptionMenu(self, values=CATEGORY_NAMES, height=34, fg_color=SURFACE2,
                                     button_color=SURFACE2, button_hover_color=BORDER, text_color=TEXT)
        self.cat.set("Programas")
        self.cat.pack(anchor="w", padx=24, pady=(2, 10))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(side="bottom", fill="x", padx=24, pady=20)
        primary_button(btns, "Guardar", self.save, width=120).pack(side="right")
        ghost_button(btns, "Cancelar", self.destroy, width=100).pack(side="right", padx=8)

    def _fill(self, path):
        self.target.delete(0, "end")
        self.target.insert(0, path)
        info = classify_path(path)
        if not self.name.get().strip():
            self.name.insert(0, info["name"])
        self.cat.set(info["category"])

    def pick_file(self):
        p = filedialog.askopenfilename(parent=self, title="Elige un programa o archivo")
        if p:
            self._fill(os.path.normpath(p))

    def pick_dir(self):
        p = filedialog.askdirectory(parent=self, title="Elige una carpeta")
        if p:
            self._fill(os.path.normpath(p))

    def save(self):
        target = self.target.get().strip().strip('"')
        if not target:
            messagebox.showwarning("Falta la ruta", "Escribe una ruta o dirección web.", parent=self)
            return
        if not _is_url(target) and not os.path.exists(target):
            if "." in target and " " not in target and not os.path.isabs(target):
                target = "https://" + target
            else:
                messagebox.showwarning("No existe", "Esa ruta no existe en tu PC.", parent=self)
                return
        name = self.name.get().strip() or os.path.basename(target.rstrip("\\/")) or target
        resolved = ""
        if target.lower().endswith(".lnk"):
            resolved = classify_path(target).get("target", "")
        self.app.library.add(name, target, self.cat.get(), "manual", resolved=resolved)
        self.app.library.save()
        self.destroy()
        self.view.refresh()
        self.view.load_icons_async()
        self.app.notify(f"«{name}» añadido a la biblioteca")
