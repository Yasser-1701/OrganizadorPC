"""Organizador del escritorio: analiza, mueve en carpetas por categoría y permite deshacer."""
import os
import shutil
import time

from .classify import CATEGORY_NAMES, classify_path
from .platform_utils import is_hidden, load_json, save_json, unique_path

SKIP_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
HISTORY_FILE = "historial_organizacion.json"


def folder_size(path, limit=20000):
    total, n = 0, 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
            n += 1
            if n > limit:
                return total
    return total


def scan(dirs, dest_base, include_folders=False):
    """Analiza las carpetas indicadas (escritorio del usuario/público)."""
    items = []
    dest_norm = os.path.normcase(os.path.abspath(dest_base))
    reserved = {c.lower() for c in CATEGORY_NAMES}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for name in entries:
            full = os.path.join(d, name)
            if name.lower() in SKIP_NAMES or is_hidden(full):
                continue
            if os.path.isdir(full):
                # No tocar las carpetas que crea el propio organizador ni el destino
                if name.lower() in reserved or os.path.normcase(os.path.abspath(full)) == dest_norm:
                    continue
                if not include_folders:
                    continue
            info = classify_path(full)
            info["source_dir"] = d
            try:
                info["size"] = folder_size(full) if os.path.isdir(full) else os.path.getsize(full)
            except OSError:
                info["size"] = 0
            items.append(info)
    items.sort(key=lambda i: (CATEGORY_NAMES.index(i["category"]), i["name"].lower()))
    return items


def plan(items, dest_base, enabled_categories):
    moves = []
    for it in items:
        cat = it["category"]
        if cat not in enabled_categories:
            continue
        dst_dir = os.path.join(dest_base, cat)
        moves.append((it["path"], os.path.join(dst_dir, os.path.basename(it["path"]))))
    return moves


def execute(moves):
    """Mueve los archivos. Devuelve (movidos, errores)."""
    done, errors = [], []
    for src, dst in moves:
        try:
            if not os.path.exists(src):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            final = unique_path(dst)
            shutil.move(src, final)
            done.append((src, final))
        except Exception as e:  # noqa: BLE001
            errors.append((src, str(e)))
    if done:
        hist = load_json(HISTORY_FILE, [])
        hist.append({"fecha": time.strftime("%Y-%m-%d %H:%M"), "movimientos": done})
        save_json(HISTORY_FILE, hist[-20:])
    return done, errors


def has_history():
    return bool(load_json(HISTORY_FILE, []))


def last_history_date():
    hist = load_json(HISTORY_FILE, [])
    return hist[-1]["fecha"] if hist else None


def undo_last():
    """Devuelve los archivos de la última organización a su sitio."""
    hist = load_json(HISTORY_FILE, [])
    if not hist:
        return [], []
    op = hist.pop()
    restored, errors = [], []
    for src, dst in reversed(op["movimientos"]):
        try:
            if not os.path.exists(dst):
                continue
            os.makedirs(os.path.dirname(src), exist_ok=True)
            final = unique_path(src)
            shutil.move(dst, final)
            restored.append((dst, final))
            parent = os.path.dirname(dst)
            if os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except Exception as e:  # noqa: BLE001
            errors.append((dst, str(e)))
    save_json(HISTORY_FILE, hist)
    return restored, errors
