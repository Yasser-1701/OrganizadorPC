"""Utilidades dependientes del sistema operativo (pensado para Windows,
con alternativas para poder probar en otros sistemas)."""
import json
import os
import subprocess
import sys
import uuid

IS_WIN = os.name == "nt"
APP_NAME = "OrganizadorPC"
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0

FOLDERID_DESKTOP = "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"
FOLDERID_PUBLIC_DESKTOP = "C4AA340D-F20F-4863-AFEF-F87EF2E6BA25"
FOLDERID_STARTUP = "B97D20BB-F46A-4C97-BA10-5E3608430854"
FOLDERID_COMMON_STARTUP = "82A5EA35-D9CD-47C5-9629-E15D2F714E6E"


def known_folder(guid_str):
    """Devuelve la ruta real de una carpeta conocida de Windows (respeta OneDrive)."""
    if not IS_WIN:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        u = uuid.UUID(guid_str)
        g = GUID()
        g.Data1, g.Data2, g.Data3 = u.fields[0], u.fields[1], u.fields[2]
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        p = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p))
        if hr != 0:
            return None
        path = p.value
        ctypes.windll.ole32.CoTaskMemFree(p)
        return path
    except Exception:
        return None


def user_desktop():
    override = os.environ.get("ORGPC_DESKTOP")
    if override:
        return override
    p = known_folder(FOLDERID_DESKTOP)
    if p and os.path.isdir(p):
        return p
    home = os.path.expanduser("~")
    for c in ("Desktop", "Escritorio", os.path.join("OneDrive", "Desktop"),
              os.path.join("OneDrive", "Escritorio")):
        full = os.path.join(home, c)
        if os.path.isdir(full):
            return full
    return os.path.join(home, "Desktop")


def public_desktop():
    if os.environ.get("ORGPC_DESKTOP"):
        return os.environ.get("ORGPC_PUBLIC_DESKTOP")
    p = known_folder(FOLDERID_PUBLIC_DESKTOP)
    if p:
        return p
    pub = os.environ.get("PUBLIC")
    return os.path.join(pub, "Desktop") if pub else None


def startup_folders():
    """(carpeta de inicio del usuario, carpeta de inicio común)"""
    user = known_folder(FOLDERID_STARTUP)
    common = known_folder(FOLDERID_COMMON_STARTUP)
    if not user and os.environ.get("APPDATA"):
        user = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    if not common and os.environ.get("PROGRAMDATA"):
        common = os.path.join(os.environ["PROGRAMDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return user, common


def data_dir():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def load_json(name, default):
    path = os.path.join(data_dir(), name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    path = os.path.join(data_dir(), name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def is_admin():
    try:
        if IS_WIN:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def app_command():
    """Ejecutable + argumentos para volver a lanzar esta app."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    script = os.path.abspath(sys.argv[0])
    exe = sys.executable
    if IS_WIN:
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w):
            exe = w
    return exe, [script]


def relaunch_as_admin():
    if not IS_WIN:
        return False
    import ctypes
    exe, args = app_command()
    params = " ".join(f'"{a}"' for a in args)
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return r > 32


def run_elevated(exe, params):
    """Abre un programa pidiendo permisos de administrador (UAC)."""
    if not IS_WIN:
        return False
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return r > 32


def open_target(target, args=None, workdir=None):
    if IS_WIN:
        if args or workdir:
            import ctypes
            r = ctypes.windll.shell32.ShellExecuteW(None, "open", target, args or None, workdir or None, 1)
            if r <= 32:
                raise OSError(f"No se pudo abrir (código {r})")
        else:
            os.startfile(target)
    else:
        subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reveal_in_explorer(path):
    if IS_WIN:
        if os.path.exists(path):
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            parent = os.path.dirname(path)
            if os.path.isdir(parent):
                os.startfile(parent)
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def is_hidden(path):
    name = os.path.basename(path)
    if name.startswith(".") or name.startswith("~$"):
        return True
    if IS_WIN:
        try:
            attrs = os.stat(path, follow_symlinks=False).st_file_attributes
            return bool(attrs & 0x2) or bool(attrs & 0x4)  # oculto / sistema
        except (OSError, AttributeError):
            return False
    return False


def human_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def unique_path(path):
    if not os.path.exists(path):
        return path
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    if os.path.isdir(path):
        stem, ext = name, ""
    i = 2
    while True:
        cand = os.path.join(folder, f"{stem} ({i}){ext}")
        if not os.path.exists(cand):
            return cand
        i += 1
