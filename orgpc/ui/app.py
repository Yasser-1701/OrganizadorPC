"""Ventana principal."""
import os
import queue
import sys
import threading
from tkinter import messagebox

import customtkinter as ctk

from ..library import Library
from ..platform_utils import IS_WIN, is_admin, load_json, relaunch_as_admin, save_json
from .desktop_view import DesktopView
from .library_view import LibraryView
from .optimize_view import OptimizeView
from .settings_view import SettingsView
from .widgets import (ACCENT, ACCENT_HOVER, BG, BORDER, MUTED, SUCCESS, SURFACE, SURFACE2, TEXT, WARNING,
                      emoji_font, font)

DEFAULT_CONFIG = {
    "theme": "dark", "sort": "Nombre", "include_public": True, "move_folders": False,
    "add_to_library": True, "dest_dir": "", "organize_disabled": [], "auto_organize": False,
    "total_freed": 0, "first_run": True,
}

NAV = [
    ("library", "🎮", "Biblioteca"),
    ("desktop", "🗂", "Organizar escritorio"),
    ("optimize", "⚡", "Optimizar PC"),
    ("settings", "⚙", "Ajustes"),
]


def resource_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base, *parts)


class App(ctk.CTk):
    def __init__(self, minimized=False):
        self.config_data = {**DEFAULT_CONFIG, **load_json("config.json", {})}
        ctk.set_appearance_mode(self.config_data.get("theme", "dark"))
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title("Organizador PC")
        self.geometry("1280x800")
        self.minsize(1060, 680)
        self.configure(fg_color=BG)
        try:
            if IS_WIN:
                self.iconbitmap(resource_path("assets", "icon.ico"))
            else:
                import tkinter as tk
                self._icon_img = tk.PhotoImage(file=resource_path("assets", "icon.png"))
                self.iconphoto(True, self._icon_img)
        except Exception:  # noqa: BLE001
            pass

        self._q = queue.Queue()
        self.after(80, self._poll)
        self.library = Library()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.views = {
            "library": LibraryView(self.content, self),
            "desktop": DesktopView(self.content, self),
            "optimize": OptimizeView(self.content, self),
            "settings": SettingsView(self.content, self),
        }
        self.toast = ctk.CTkLabel(self, text="", font=font(13), fg_color=SURFACE2, text_color=TEXT,
                                  corner_radius=10, height=36)
        self._toast_job = None

        self.show("library")
        self.views["library"].refresh()
        self.after(400, self._startup_tasks)
        if minimized:
            self.after(50, self.iconify)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------ sidebar
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=SURFACE, border_width=0)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)
        sb.pack_propagate(False)

        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(22, 26))
        ctk.CTkLabel(logo, text="🗂", font=emoji_font(22), width=42, height=42, corner_radius=12,
                     fg_color=ACCENT, text_color="#fff").pack(side="left")
        t = ctk.CTkFrame(logo, fg_color="transparent")
        t.pack(side="left", padx=10)
        ctk.CTkLabel(t, text="Organizador PC", font=font(16, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(t, text="Todo en su sitio", font=font(11), text_color=MUTED, anchor="w").pack(anchor="w")

        self.nav_buttons = {}
        for key, icon, label in NAV:
            b = ctk.CTkButton(sb, text=f"  {icon}   {label}", anchor="w", height=42, corner_radius=10,
                              font=font(14), fg_color="transparent", text_color=TEXT, hover_color=SURFACE2,
                              command=lambda k=key: self.show(k))
            b.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = b

        bottom = ctk.CTkFrame(sb, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=14, pady=16)
        self.freed_label = ctk.CTkLabel(bottom, text="", font=font(11), text_color=MUTED, anchor="w", justify="left")
        self.freed_label.pack(fill="x", pady=(0, 8))
        self._update_freed()
        if is_admin():
            ctk.CTkLabel(bottom, text="🛡  Modo administrador", font=font(12, "bold"), text_color=SUCCESS,
                         anchor="w").pack(fill="x")
        elif IS_WIN:
            ctk.CTkLabel(bottom, text="Algunas limpiezas necesitan permisos:", font=font(11), text_color=MUTED,
                         anchor="w").pack(fill="x")
            ctk.CTkButton(bottom, text="🛡  Ejecutar como admin", height=34, corner_radius=10, fg_color=SURFACE2,
                          hover_color=BORDER, text_color=WARNING, font=font(12, "bold"),
                          command=self.elevate).pack(fill="x", pady=(4, 0))

    def show(self, key):
        for k, v in self.views.items():
            if k == key:
                v.grid(row=0, column=0, sticky="nsew")
            else:
                v.grid_forget()
        for k, b in self.nav_buttons.items():
            sel = k == key
            b.configure(fg_color=ACCENT if sel else "transparent", text_color="#ffffff" if sel else TEXT,
                        hover_color=ACCENT_HOVER if sel else SURFACE2, font=font(14, "bold" if sel else "normal"))
        if key == "settings":
            self.views["settings"].update_about()

    def elevate(self):
        if relaunch_as_admin():
            self.on_close()

    # ------------------------------------------------------------ tareas
    def _startup_tasks(self):
        lib = self.views["library"]
        if self.config_data.get("first_run") or not self.library.items:
            self.config_data["first_run"] = False
            self.save_config()
            lib.run_detection(["Escritorio", "Steam", "Epic Games", "GOG"])
        else:
            lib.load_icons_async()
        if self.config_data.get("auto_organize"):
            self.views["desktop"].organize(silent=True)

    def run_bg(self, fn, done=None):
        """Ejecuta fn en segundo plano y llama a done(resultado, error) en la interfaz."""
        def worker():
            try:
                res, err = fn(), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            if done:
                self._q.put(lambda: done(res, err))
        threading.Thread(target=worker, daemon=True).start()

    def call_soon(self, fn):
        """Permite a un hilo actualizar la interfaz de forma segura."""
        self._q.put(fn)

    def _poll(self):
        try:
            while True:
                fn = self._q.get_nowait()
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    print("UI error:", e, file=sys.stderr)
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def notify(self, text):
        self.toast.configure(text=f"   {text}   ")
        self.toast.place(relx=1.0, rely=1.0, x=-24, y=-20, anchor="se")
        self.toast.lift()
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(4500, self.toast.place_forget)

    def add_freed(self, n):
        self.config_data["total_freed"] = self.config_data.get("total_freed", 0) + n
        self.save_config()
        self._update_freed()

    def _update_freed(self):
        from ..platform_utils import human_size
        n = self.config_data.get("total_freed", 0)
        self.freed_label.configure(text=f"🧹 Liberado en total: {human_size(n)}" if n else "")

    def save_config(self):
        try:
            save_json("config.json", self.config_data)
        except OSError as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración:\n{e}")

    def on_close(self):
        self.save_config()
        self.destroy()


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OrganizadorPC.App")
        except Exception:  # noqa: BLE001
            pass
    app = App(minimized="--minimizado" in sys.argv)
    app.mainloop()
