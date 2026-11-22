"""Organizador PC — organiza tu escritorio, tus juegos y programas, y optimiza Windows."""
import sys

try:
    import customtkinter  # noqa: F401
except ImportError:
    import tkinter.messagebox as mb
    mb.showerror("Falta una dependencia",
                 "No se encontró «customtkinter».\n\nEjecuta «Iniciar.bat» o en una consola:\n"
                 "    py -m pip install -r requirements.txt")
    sys.exit(1)

from orgpc.ui.app import main

if __name__ == "__main__":
    main()
