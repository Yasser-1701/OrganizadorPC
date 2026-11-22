"""Colores, fuentes y pequeños componentes reutilizables."""
import tkinter as tk

import customtkinter as ctk

# (modo claro, modo oscuro)
BG = ("#eef0f4", "#0f1115")
SURFACE = ("#ffffff", "#181b22")
SURFACE2 = ("#e4e7ec", "#222631")
BORDER = ("#d9dde4", "#2a2f3b")
TEXT = ("#111827", "#e8eaf0")
MUTED = ("#6b7280", "#8b93a3")
ACCENT = ("#6d5dfc", "#7c6cff")
ACCENT_HOVER = ("#5847e8", "#6857f0")
SUCCESS = ("#15803d", "#22c55e")
WARNING = ("#b45309", "#f59e0b")
DANGER = ("#b91c1c", "#ef4444")
DANGER_HOVER = ("#991b1b", "#dc2626")

FAMILY = "Segoe UI"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FAMILY, size=size, weight=weight)


def emoji_font(size=28):
    return ctk.CTkFont(family="Segoe UI Emoji", size=size)


class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", SURFACE)
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", BORDER)
        super().__init__(master, **kw)


def header(parent, title, subtitle=""):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=title, font=font(26, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
    sub = ctk.CTkLabel(f, text=subtitle, font=font(13), text_color=MUTED, anchor="w", justify="left")
    sub.pack(anchor="w")
    f.subtitle = sub
    return f


def primary_button(parent, text, command, **kw):
    kw.setdefault("height", 36)
    kw.setdefault("corner_radius", 10)
    return ctk.CTkButton(parent, text=text, command=command, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                         font=font(13, "bold"), **kw)


def ghost_button(parent, text, command, **kw):
    kw.setdefault("height", 36)
    kw.setdefault("corner_radius", 10)
    return ctk.CTkButton(parent, text=text, command=command, fg_color=SURFACE2, hover_color=BORDER,
                         text_color=TEXT, font=font(13), **kw)


def danger_button(parent, text, command, **kw):
    kw.setdefault("height", 30)
    kw.setdefault("corner_radius", 8)
    return ctk.CTkButton(parent, text=text, command=command, fg_color=DANGER, hover_color=DANGER_HOVER,
                         font=font(12, "bold"), **kw)


def badge(parent, text, color):
    return ctk.CTkLabel(parent, text=f" {text} ", fg_color=color, text_color="#ffffff",
                        corner_radius=6, font=font(11, "bold"), height=20)


def popup_menu(widget, entries):
    """entries: lista de (texto, funcion) | None (separador) | (texto, [(sub, fn), ...])"""
    m = tk.Menu(widget, tearoff=0, font=(FAMILY, 10))
    for e in entries:
        if e is None:
            m.add_separator()
        elif isinstance(e[1], list):
            sub = tk.Menu(m, tearoff=0, font=(FAMILY, 10))
            for label, fn in e[1]:
                sub.add_command(label=label, command=fn)
            m.add_cascade(label=e[0], menu=sub)
        else:
            m.add_command(label=e[0], command=e[1])
    x = widget.winfo_rootx()
    y = widget.winfo_rooty() + widget.winfo_height()
    try:
        m.tk_popup(x, y)
    finally:
        m.grab_release()


class Dialog(ctk.CTkToplevel):
    """Ventana modal centrada sobre la principal."""

    def __init__(self, master, title, width=460, height=360):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.transient(master)
        master.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.after(150, self._grab)

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass
