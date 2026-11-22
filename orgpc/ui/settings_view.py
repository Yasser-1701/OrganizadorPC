"""Vista Ajustes."""
import os
import shutil
from tkinter import messagebox

import customtkinter as ctk

from .. import systools
from ..library import icon_cache_dir
from ..platform_utils import IS_WIN, data_dir, human_size, open_target
from .widgets import ACCENT, ACCENT_HOVER, MUTED, Card, font, ghost_button, header

THEMES = {"Oscuro": "dark", "Claro": "light", "Sistema": "system"}


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        cfg = app.config_data
        header(self, "Ajustes", "Personaliza cómo funciona Organizador PC.").pack(anchor="w", padx=28, pady=(24, 14))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        # Apariencia
        c = self._section(body, "🎨  Apariencia")
        seg = ctk.CTkSegmentedButton(c, values=list(THEMES), command=self.set_theme, selected_color=ACCENT,
                                     selected_hover_color=ACCENT_HOVER, font=font(13))
        seg.set(next((k for k, v in THEMES.items() if v == cfg.get("theme", "dark")), "Oscuro"))
        seg.pack(anchor="w", padx=16, pady=(0, 14))

        # Inicio
        c = self._section(body, "🚀  Inicio")
        self.sw_auto = ctk.CTkSwitch(c, text="Iniciar Organizador PC al encender Windows (minimizado)",
                                     font=font(13), progress_color=ACCENT, command=self.toggle_autostart)
        self.sw_auto.pack(anchor="w", padx=16, pady=4)
        if systools.self_autostart_enabled():
            self.sw_auto.select()
        if not IS_WIN:
            self.sw_auto.configure(state="disabled")
        self.sw_org = ctk.CTkSwitch(c, text="Organizar el escritorio automáticamente al abrir la app",
                                    font=font(13), progress_color=ACCENT, command=self.toggle_auto_org)
        self.sw_org.pack(anchor="w", padx=16, pady=(4, 14))
        if cfg.get("auto_organize"):
            self.sw_org.select()

        # Datos
        c = self._section(body, "🗃  Datos")
        ctk.CTkLabel(c, text=f"Tu biblioteca y ajustes se guardan en:\n{data_dir()}", font=font(12),
                     text_color=MUTED, justify="left").pack(anchor="w", padx=16)
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(anchor="w", padx=16, pady=(8, 14))
        ghost_button(row, "📂  Abrir carpeta de datos", lambda: open_target(data_dir()), width=200).pack(side="left")
        ghost_button(row, "🧹  Quitar elementos rotos", self.remove_broken, width=200).pack(side="left", padx=8)
        ghost_button(row, "🖼  Regenerar iconos", self.reset_icons, width=170).pack(side="left")

        # Acerca de
        c = self._section(body, "ℹ  Acerca de")
        self.about = ctk.CTkLabel(c, text="", font=font(12), text_color=MUTED, justify="left")
        self.about.pack(anchor="w", padx=16, pady=(0, 14))
        self.update_about()

    def _section(self, parent, title):
        c = Card(parent)
        c.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(c, text=title, font=font(15, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        return c

    def update_about(self):
        freed = self.app.config_data.get("total_freed", 0)
        self.about.configure(text="Organizador PC 1.0 — organiza tu escritorio, tu biblioteca de juegos y programas,\n"
                                  "y mantiene tu equipo limpio.\n\n"
                                  f"Espacio liberado en total con esta app: {human_size(freed)}")

    def set_theme(self, label):
        mode = THEMES[label]
        ctk.set_appearance_mode(mode)
        self.app.config_data["theme"] = mode
        self.app.save_config()

    def toggle_autostart(self):
        try:
            systools.set_self_autostart(bool(self.sw_auto.get()))
            self.app.notify("Se iniciará con Windows" if self.sw_auto.get() else "Ya no se iniciará con Windows")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", str(e), parent=self)

    def toggle_auto_org(self):
        self.app.config_data["auto_organize"] = bool(self.sw_org.get())
        self.app.save_config()

    def remove_broken(self):
        n = self.app.library.remove_broken()
        self.app.views["library"].refresh()
        self.app.notify(f"{n} elementos rotos quitados de la biblioteca")

    def reset_icons(self):
        shutil.rmtree(icon_cache_dir(), ignore_errors=True)
        os.makedirs(icon_cache_dir(), exist_ok=True)
        lib = self.app.views["library"]
        lib.images.clear()
        lib.refresh(rebuild=True)
        lib.load_icons_async()
        self.app.notify("Regenerando iconos…")
