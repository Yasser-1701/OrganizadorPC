"""Limpieza de archivos temporales y cachés de Windows, navegadores y aplicaciones."""
import glob
import os
import stat

from .platform_utils import IS_WIN

L = os.environ.get("LOCALAPPDATA", "")
R = os.environ.get("APPDATA", "")
W = os.environ.get("WINDIR", os.environ.get("SystemRoot", ""))
P = os.environ.get("PROGRAMDATA", "")
TEMP = os.environ.get("TEMP", "") if IS_WIN else os.environ.get("ORGPC_TEMP", "")


def j(base, *parts):
    return os.path.join(base, *parts) if base else ""


def chromium(base):
    ud = j(base, "User Data")
    return [j(ud, "*", "Cache"), j(ud, "*", "Code Cache"), j(ud, "*", "GPUCache"),
            j(ud, "*", "Service Worker", "CacheStorage"), j(ud, "*", "Service Worker", "ScriptCache"),
            j(ud, "ShaderCache"), j(ud, "GrShaderCache"), j(ud, "GraphiteDawnCache")]


def electron(base):
    return [j(base, "Cache"), j(base, "Code Cache"), j(base, "GPUCache"), j(base, "DawnCache"),
            j(base, "Service Worker", "CacheStorage")]


# Cada objetivo: se borra el CONTENIDO de las carpetas que coinciden con los patrones.
TARGETS = [
    {"id": "temp_user", "name": "Archivos temporales del usuario",
     "desc": "Carpeta %TEMP%: restos de instalaciones y programas.", "default": True,
     "paths": [TEMP]},
    {"id": "temp_win", "name": "Temporales de Windows",
     "desc": "C:\\Windows\\Temp", "default": True, "admin": True,
     "paths": [j(W, "Temp")]},
    {"id": "recycle", "name": "Papelera de reciclaje",
     "desc": "Vacía la papelera de todas las unidades.", "default": False, "special": "recycle"},
    {"id": "chrome", "name": "Caché de Google Chrome", "desc": "No borra contraseñas, historial ni sesiones.",
     "default": True, "paths": chromium(j(L, "Google", "Chrome")), "procs": ["chrome.exe"]},
    {"id": "edge", "name": "Caché de Microsoft Edge", "desc": "No borra contraseñas, historial ni sesiones.",
     "default": True, "paths": chromium(j(L, "Microsoft", "Edge")), "procs": ["msedge.exe"]},
    {"id": "brave", "name": "Caché de Brave", "desc": "Solo la caché de páginas.", "default": True,
     "paths": chromium(j(L, "BraveSoftware", "Brave-Browser")), "procs": ["brave.exe"]},
    {"id": "opera", "name": "Caché de Opera / Opera GX", "desc": "Solo la caché de páginas.", "default": True,
     "paths": [j(L, "Opera Software", "Opera Stable", "Cache"), j(L, "Opera Software", "Opera GX Stable", "Cache"),
               j(R, "Opera Software", "Opera Stable", "Cache"), j(R, "Opera Software", "Opera GX Stable", "Cache"),
               j(R, "Opera Software", "Opera Stable", "Default", "Cache"),
               j(R, "Opera Software", "Opera GX Stable", "Default", "Cache"),
               j(L, "Opera Software", "Opera Stable", "Default", "Cache"),
               j(L, "Opera Software", "Opera GX Stable", "Default", "Cache")],
     "procs": ["opera.exe"]},
    {"id": "firefox", "name": "Caché de Firefox", "desc": "Solo la caché de páginas.", "default": True,
     "paths": [j(L, "Mozilla", "Firefox", "Profiles", "*", "cache2"),
               j(L, "Mozilla", "Firefox", "Profiles", "*", "startupCache")], "procs": ["firefox.exe"]},
    {"id": "apps", "name": "Caché de Discord, Spotify y Teams", "desc": "Se vuelve a descargar al usarlas.",
     "default": True,
     "paths": electron(j(R, "discord")) + electron(j(R, "Microsoft", "Teams")) +
              [j(L, "Spotify", "Data"), j(L, "Spotify", "Browser", "Cache")],
     "procs": ["discord.exe", "spotify.exe", "teams.exe"]},
    {"id": "launchers", "name": "Caché web de Steam y Epic Games",
     "desc": "Caché del navegador interno de los launchers (no toca tus juegos).", "default": True,
     "paths": [j(L, "Steam", "htmlcache"), j(L, "EpicGamesLauncher", "Saved", "webcache"),
               j(L, "EpicGamesLauncher", "Saved", "webcache_4147"), j(L, "EpicGamesLauncher", "Saved", "webcache_4430"),
               j(L, "Battle.net", "BrowserCache")],
     "procs": ["steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe"]},
    {"id": "shaders", "name": "Caché de shaders (DirectX / NVIDIA / AMD)",
     "desc": "Se regenera sola. Los juegos pueden tardar un poco más la primera vez.", "default": False,
     "paths": [j(L, "D3DSCache"), j(L, "NVIDIA", "DXCache"), j(L, "NVIDIA", "GLCache"),
               j(L, "AMD", "DxCache"), j(L, "AMD", "DxcCache"), j(L, "AMD", "VkCache")]},
    {"id": "thumbs", "name": "Caché de miniaturas", "desc": "Miniaturas del Explorador (se regeneran).",
     "default": False, "files": [j(L, "Microsoft", "Windows", "Explorer", "thumbcache_*.db")]},
    {"id": "errors", "name": "Informes de errores y volcados",
     "desc": "Informes de errores de Windows y volcados de programas que se cerraron.", "default": True,
     "paths": [j(L, "CrashDumps"), j(L, "Microsoft", "Windows", "WER", "ReportArchive"),
               j(L, "Microsoft", "Windows", "WER", "ReportQueue"),
               j(P, "Microsoft", "Windows", "WER", "ReportArchive"),
               j(P, "Microsoft", "Windows", "WER", "ReportQueue"), j(W, "Minidump")]},
    {"id": "winupdate", "name": "Caché de Windows Update",
     "desc": "Actualizaciones ya instaladas que se descargaron.", "default": False, "admin": True,
     "paths": [j(W, "SoftwareDistribution", "Download"),
               j(W, "ServiceProfiles", "NetworkService", "AppData", "Local", "Microsoft", "Windows",
                 "DeliveryOptimization", "Cache")]},
    {"id": "prefetch", "name": "Prefetch de Windows",
     "desc": "Windows lo recrea; los programas pueden tardar algo más en abrir la próxima vez.",
     "default": False, "admin": True, "paths": [j(W, "Prefetch")]},
]

FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _protected(path):
    """Evita borrar carpetas raíz por error (unidad, usuario, Windows...)."""
    p = os.path.normcase(os.path.abspath(path)).rstrip("\\/")
    parts = [x for x in p.replace("\\", "/").split("/") if x]
    if len(parts) < 3:
        return True
    bad = {os.path.normcase(os.path.abspath(x)).rstrip("\\/") for x in
           (os.path.expanduser("~"), W, L, R, P, os.path.expanduser("~/Desktop")) if x}
    return p in bad


def resolve(target):
    dirs, files = [], []
    for pat in target.get("paths", []):
        if not pat:
            continue
        for p in glob.glob(pat):
            if os.path.isdir(p) and not _protected(p):
                dirs.append(p)
    for pat in target.get("files", []):
        if pat:
            files.extend(f for f in glob.glob(pat) if os.path.isfile(f))
    return sorted(set(dirs)), sorted(set(files))


def _is_link(entry):
    try:
        if entry.is_symlink():
            return True
        if IS_WIN:
            return bool(entry.stat(follow_symlinks=False).st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True
    return False


def _walk_size(path):
    total = count = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    if _is_link(e):
                        continue
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                            count += 1
                    except OSError:
                        pass
        except OSError:
            pass
    return total, count


# ------------------------------------------------------------- papelera
def _recycle_info():
    if not IS_WIN:
        return 0, 0
    import ctypes

    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]

    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
        return int(info.i64Size), int(info.i64NumItems)
    return 0, 0


def _empty_recycle():
    if not IS_WIN:
        return
    import ctypes
    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)


# -------------------------------------------------------------- público
def measure(target):
    if target.get("special") == "recycle":
        size, n = _recycle_info()
        return {"size": size, "count": n}
    dirs, files = resolve(target)
    total = count = 0
    for d in dirs:
        s, c = _walk_size(d)
        total += s
        count += c
    for f in files:
        try:
            total += os.path.getsize(f)
            count += 1
        except OSError:
            pass
    return {"size": total, "count": count}


def _remove_file(path):
    try:
        os.remove(path)
    except PermissionError:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def _clean_dir_contents(path, stats):
    try:
        entries = list(os.scandir(path))
    except OSError:
        return
    for e in entries:
        if _is_link(e):
            continue
        try:
            if e.is_dir(follow_symlinks=False):
                _clean_dir_contents(e.path, stats)
                try:
                    os.rmdir(e.path)
                except OSError:
                    pass
            else:
                size = e.stat(follow_symlinks=False).st_size
                _remove_file(e.path)
                stats["freed"] += size
                stats["deleted"] += 1
        except OSError:
            stats["failed"] += 1  # en uso o sin permisos: se omite


def clean(target):
    stats = {"freed": 0, "deleted": 0, "failed": 0}
    if target.get("special") == "recycle":
        size, n = _recycle_info()
        _empty_recycle()
        after, _ = _recycle_info()
        stats["freed"] = max(0, size - after)
        stats["deleted"] = n
        return stats
    dirs, files = resolve(target)
    for d in dirs:
        _clean_dir_contents(d, stats)
    for f in files:
        try:
            size = os.path.getsize(f)
            _remove_file(f)
            stats["freed"] += size
            stats["deleted"] += 1
        except OSError:
            stats["failed"] += 1
    return stats


def running_processes(names):
    try:
        import psutil
    except ImportError:
        return []
    wanted = {n.lower() for n in names}
    found = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info.get("name") or "").lower()
        if n in wanted:
            found.add(n)
    return sorted(found)
