"""Organizador PC — organiza tu escritorio, tus juegos y programas, y optimiza Windows."""
import os
import sys
import traceback


def _report(exc_text):
    """Guarda el error en un archivo y lo muestra en pantalla."""
    log = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "OrganizadorPC", "error.log")
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "w", encoding="utf-8") as f:
            f.write(exc_text)
    except OSError:
        log = "(no se pudo guardar)"
    print(exc_text, file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Organizador PC — error",
                             "La app no ha podido arrancar.\n\n" + exc_text[-1500:] +
                             f"\n\nEl error completo está guardado en:\n{log}")
        root.destroy()
    except Exception:  # noqa: BLE001
        pass


def run():
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])) if not getattr(sys, "frozen", False) else os.getcwd())
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        _report("Falta la librería «customtkinter».\n\nAbre la app con «Iniciar.bat» o ejecuta en una consola:\n"
                "    py -m pip install -r requirements.txt")
        sys.exit(1)
    try:
        from orgpc.ui.app import main
        main()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        _report(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    run()
