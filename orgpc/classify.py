"""Clasificación de archivos y accesos directos en categorías."""
import os

from .shortcuts import parse_lnk, parse_url_file

# (nombre, icono, color)
CATEGORIES = [
    ("Juegos", "🎮", "#7c3aed"),
    ("Programas", "🧩", "#2563eb"),
    ("Web", "🌐", "#0891b2"),
    ("Carpetas", "📁", "#ca8a04"),
    ("Documentos", "📄", "#16a34a"),
    ("Imágenes", "🖼", "#db2777"),
    ("Vídeos", "🎬", "#dc2626"),
    ("Música", "🎵", "#ea580c"),
    ("Comprimidos", "🗜", "#64748b"),
    ("Instaladores", "📦", "#0d9488"),
    ("Código", "💻", "#4f46e5"),
    ("Otros", "📎", "#6b7280"),
]
CATEGORY_NAMES = [c[0] for c in CATEGORIES]
CATEGORY_ICON = {c[0]: c[1] for c in CATEGORIES}
CATEGORY_COLOR = {c[0]: c[2] for c in CATEGORIES}

EXTENSIONS = {
    "Documentos": "pdf doc docx odt rtf txt md xls xlsx xlsm ods csv ppt pptx odp epub one pages key numbers",
    "Imágenes": "jpg jpeg png gif bmp webp svg heic heif ico tif tiff psd raw cr2 nef ai xcf avif",
    "Vídeos": "mp4 mkv avi mov wmv webm flv m4v mpg mpeg 3gp ts",
    "Música": "mp3 wav flac ogg m4a aac wma opus mid midi",
    "Comprimidos": "zip rar 7z tar gz bz2 xz iso img cab tgz",
    "Instaladores": "msi msix msixbundle appx appxbundle",
    "Código": "py js ts html htm css java c cpp h hpp cs json xml yml yaml ini sql sh ps1 bat cmd php rb go rs lua ipynb",
}
EXT_TO_CAT = {}
for _cat, _exts in EXTENSIONS.items():
    for _e in _exts.split():
        EXT_TO_CAT["." + _e] = _cat

PROGRAM_EXT = {".exe", ".bat", ".cmd", ".msc", ".com", ".appref-ms", ".jar", ".vbs"}

GAME_PATH_HINTS = [
    "steamapps", "epic games", "gog galaxy", "gog games", "riot games", "ubisoft game launcher",
    "ubisoft\\", "ea games", "origin games", "battle.net", "xboxgames", "rockstar games",
    "\\games\\", "\\juegos\\", "minecraft", "roblox", "blizzard", "wargaming", "bethesda",
    "itch\\apps", "hoyoplay", "genshin", "valorant", "league of legends", "fortnite",
    "curseforge", "heroic", "playnite", "emulator", "retroarch", "\\steam\\", "steam.exe",
    "epicgameslauncher", "ea desktop", "eadesktop", "riotclient",
]
GAME_URL_SCHEMES = [
    "steam://", "com.epicgames.launcher://", "uplay://", "origin://", "origin2://",
    "battlenet://", "goggalaxy://", "riotclient://", "roblox", "minecraft:", "xbox",
    "eadesktop", "link2ea://", "itch://", "heroic://", "playnite://",
]
INSTALLER_HINTS = ["setup", "install", "instalador", "installer", "_x64", "x86_64", "update", "-win64", "win64", "redist"]


def is_game_target(text):
    t = (text or "").lower()
    return any(h in t for h in GAME_PATH_HINTS)


def category_for_extension(ext):
    return EXT_TO_CAT.get(ext.lower())


def classify_path(path):
    """Clasifica un archivo/carpeta. Devuelve dict con name, category, target, args, workdir."""
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    info = {"path": path, "name": stem if ext else name, "category": "Otros",
            "target": "", "args": "", "workdir": ""}

    if os.path.isdir(path):
        info["name"] = name
        info["category"] = "Carpetas"
        return info

    if ext == ".lnk":
        lnk = parse_lnk(path) or {}
        target = lnk.get("target", "")
        info.update(target=target, args=lnk.get("args", ""), workdir=lnk.get("workdir", ""))
        joined = f"{target} {lnk.get('args', '')} {lnk.get('workdir', '')}"
        t_ext = os.path.splitext(target)[1].lower()
        if is_game_target(joined) or is_game_target(stem):
            info["category"] = "Juegos"
        elif target and (os.path.isdir(target) or (not t_ext and not os.path.isfile(target))):
            info["category"] = "Carpetas"
        elif t_ext in PROGRAM_EXT or not t_ext:
            info["category"] = "Programas"
        elif t_ext in (".url", ".html", ".htm"):
            info["category"] = "Web"
        else:
            info["category"] = category_for_extension(t_ext) or "Programas"
        return info

    if ext in (".url", ".website"):
        u = parse_url_file(path)
        url = u.get("url", "")
        info["target"] = url
        low = url.lower()
        if any(low.startswith(s) for s in GAME_URL_SCHEMES):
            info["category"] = "Juegos"
        elif low.startswith(("http://", "https://")):
            info["category"] = "Web"
        else:
            info["category"] = "Programas"
        return info

    if ext == ".exe":
        low = stem.lower()
        if any(h in low for h in INSTALLER_HINTS):
            info["category"] = "Instaladores"
        elif is_game_target(path):
            info["category"] = "Juegos"
        else:
            info["category"] = "Programas"
        return info

    if ext in PROGRAM_EXT:
        info["category"] = "Programas"
        return info

    info["category"] = category_for_extension(ext) or "Otros"
    return info
