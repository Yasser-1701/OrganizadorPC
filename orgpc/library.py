"""Biblioteca de juegos y programas: detecta Steam, Epic, GOG, menú Inicio y escritorio."""
import glob
import hashlib
import json
import os
import re
import subprocess
import time
import uuid

from .classify import classify_path
from .platform_utils import (CREATE_NO_WINDOW, IS_WIN, data_dir, load_json, open_target,
                             public_desktop, save_json, user_desktop)

LIB_FILE = "biblioteca.json"


def _is_url(t):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]+:(//|[^\\])", t or "")) and not re.match(r"^[a-zA-Z]:\\", t or "")


def _name_key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _key(target):
    return (target or "").strip().lower().replace("/", "\\").rstrip("\\")


class Library:
    def __init__(self):
        self.items = load_json(LIB_FILE, {"items": []}).get("items", [])
        if self._dedupe():
            self.save()

    def _dedupe(self):
        """Quita copias del mismo juego (p. ej. Steam + acceso del escritorio)."""
        stores = ("Steam", "Epic Games", "GOG")
        groups = {}
        for it in self.items:
            groups.setdefault(_name_key(it.get("name")), []).append(it)
        drop = set()
        for key, group in groups.items():
            if not key or len(group) < 2:
                continue
            keep = next((i for i in group if i.get("source") in stores), None) or \
                next((i for i in group if i.get("source") == "manual"), None) or group[0]
            for it in group:
                if it is keep or it.get("source") == "manual" and keep.get("source") != "manual":
                    continue
                keep["launches"] = keep.get("launches", 0) + it.get("launches", 0)
                keep["favorite"] = keep.get("favorite") or it.get("favorite")
                drop.add(it["id"])
        if drop:
            self.items = [i for i in self.items if i["id"] not in drop]
        return bool(drop)

    # ---------------------------------------------------------------- datos
    def save(self):
        save_json(LIB_FILE, {"items": self.items})

    def find(self, item_id):
        return next((i for i in self.items if i["id"] == item_id), None)

    def _known_keys(self):
        keys = set()
        for i in self.items:
            keys.add(_key(i.get("target")))
            if i.get("resolved"):
                keys.add(_key(i["resolved"]))
        keys.discard("")
        return keys

    def add(self, name, target, category, source="manual", args="", workdir="", resolved="",
            image="", location=""):
        item = {
            "id": uuid.uuid4().hex[:12], "name": name, "target": target, "args": args,
            "workdir": workdir, "resolved": resolved, "category": category, "source": source,
            "favorite": False, "launches": 0, "last_launched": 0, "added": time.time(),
            "image": image, "location": location,
        }
        self.items.append(item)
        return item

    def remove(self, item_id):
        self.items = [i for i in self.items if i["id"] != item_id]
        self.save()

    def is_broken(self, item):
        t = item.get("target", "")
        if not t or _is_url(t):
            return False
        return not os.path.exists(t)

    def remove_broken(self):
        before = len(self.items)
        self.items = [i for i in self.items if not self.is_broken(i)]
        self.save()
        return before - len(self.items)

    def launch(self, item):
        target = item["target"]
        if not _is_url(target) and not os.path.exists(target):
            alt = item.get("resolved")
            if alt and os.path.exists(alt):
                target = alt
            else:
                raise FileNotFoundError(f"No se encuentra: {target}")
        if _is_url(target) or target.lower().endswith((".lnk", ".url", ".website")):
            open_target(target)  # el acceso directo ya contiene sus argumentos
        else:
            workdir = item.get("workdir") or (os.path.dirname(target) if os.path.isfile(target) else None)
            open_target(target, item.get("args") or None, workdir)
        item["launches"] = item.get("launches", 0) + 1
        item["last_launched"] = time.time()
        self.save()

    def location_of(self, item):
        for cand in (item.get("location"), item.get("resolved"), item.get("target")):
            if cand and not _is_url(cand) and os.path.exists(cand):
                return cand
        return None

    def remap_paths(self, moves):
        """Actualiza rutas después de mover archivos del escritorio."""
        mapping = {os.path.normcase(os.path.abspath(a)): b for a, b in moves}
        changed = False
        for it in self.items:
            t = it.get("target", "")
            if t and not _is_url(t):
                new = mapping.get(os.path.normcase(os.path.abspath(t)))
                if new:
                    it["target"] = new
                    changed = True
        if changed:
            self.save()

    # ------------------------------------------------------------ escaneo
    def import_entries(self, entries):
        known = self._known_keys()
        by_name = {_name_key(i["name"]): i for i in self.items}
        by_target = {_key(i.get("target")): i for i in self.items if i.get("target")}
        added = 0
        for e in entries:
            k1, k2 = _key(e.get("target")), _key(e.get("resolved"))
            if (k1 and k1 in known) or (k2 and k2 in known):
                old = by_target.get(k1)
                if old is not None:
                    for f in ("image", "location"):
                        if e.get(f) and not old.get(f):
                            old[f] = e[f]
                continue
            same = by_name.get(_name_key(e["name"]))
            if same:
                # mismo juego/programa desde otra fuente: completa los datos que falten
                for f in ("image", "location"):
                    if e.get(f) and not same.get(f):
                        same[f] = e[f]
                continue
            self.add(e["name"], e["target"], e["category"], e.get("source", "manual"),
                     e.get("args", ""), e.get("workdir", ""), e.get("resolved", ""),
                     e.get("image", ""), e.get("location", ""))
            known.update(k for k in (k1, k2) if k)
            by_name[_name_key(e["name"])] = self.items[-1]
            added += 1
        self.save()
        return added

    def scan_and_import(self, sources):
        entries = []
        found = {}
        order = list(SCANNERS)
        for src in sorted(sources, key=lambda s: order.index(s) if s in order else 99):
            fn = SCANNERS.get(src)
            if not fn:
                continue
            try:
                res = fn()
            except Exception:  # noqa: BLE001
                res = []
            found[src] = len(res)
            entries.extend(res)
        return self.import_entries(entries), found


# --------------------------------------------------------------- escáneres
def _winreg_value(root_name, path, value):
    if not IS_WIN:
        return None
    import winreg
    root = getattr(winreg, root_name)
    for flag in (0, getattr(winreg, "KEY_WOW64_32KEY", 0), getattr(winreg, "KEY_WOW64_64KEY", 0)):
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_READ | flag) as k:
                return winreg.QueryValueEx(k, value)[0]
        except OSError:
            continue
    return None


def steam_root():
    p = _winreg_value("HKEY_CURRENT_USER", r"Software\Valve\Steam", "SteamPath")
    if p and os.path.isdir(p):
        return os.path.normpath(p)
    p = _winreg_value("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
    if p and os.path.isdir(p):
        return p
    for c in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
              os.path.expanduser("~/.steam/steam"), os.path.expanduser("~/.local/share/Steam")):
        if os.path.isdir(c):
            return c
    return None


STEAM_EXCLUDE = re.compile(r"redistributable|steamworks|proton|steam linux runtime|soundtrack|dedicated server|sdk$", re.I)


def _steam_image(root, appid):
    cache = os.path.join(root, "appcache", "librarycache")
    a = str(appid)
    for pat in (f"{a}_header.jpg", os.path.join(a, "header.jpg"), os.path.join(a, "**", "header.jpg"),
                os.path.join(a, "**", "library_header*.jpg"), f"{a}_library_hero.jpg",
                os.path.join(a, "**", "library_hero.jpg"), f"{a}_library_600x900.jpg",
                os.path.join(a, "**", "library_capsule*.jpg"), os.path.join(a, "**", "library_600x900.jpg")):
        hits = glob.glob(os.path.join(cache, pat), recursive=True)
        if hits:
            return hits[0]
    return ""


def scan_steam():
    root = steam_root()
    if not root:
        return []
    libs = {os.path.normcase(root): root}
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, "r", encoding="utf-8", errors="replace") as f:
            for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                p = m.group(1).replace("\\\\", "\\")
                libs[os.path.normcase(p)] = p
    except OSError:
        pass
    out = []
    for lib in libs.values():
        for acf in glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf")):
            try:
                with open(acf, "r", encoding="utf-8", errors="replace") as f:
                    txt = f.read()
            except OSError:
                continue
            appid = re.search(r'"appid"\s+"(\d+)"', txt)
            name = re.search(r'"name"\s+"([^"]+)"', txt)
            idir = re.search(r'"installdir"\s+"([^"]+)"', txt)
            if not appid or not name or STEAM_EXCLUDE.search(name.group(1)) or appid.group(1) == "228980":
                continue
            loc = os.path.join(lib, "steamapps", "common", idir.group(1)) if idir else ""
            out.append({"name": name.group(1), "target": f"steam://rungameid/{appid.group(1)}",
                        "category": "Juegos", "source": "Steam",
                        "image": _steam_image(root, appid.group(1)), "location": loc})
    return out


def scan_epic():
    base = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                        "Epic", "EpicGamesLauncher", "Data", "Manifests")
    out = []
    for item in glob.glob(os.path.join(base, "*.item")):
        try:
            with open(item, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if d.get("bIsIncompleteInstall"):
            continue
        main = d.get("MainGameAppName")
        if main and main != d.get("AppName"):
            continue  # DLC
        ns, cid, app = d.get("CatalogNamespace", ""), d.get("CatalogItemId", ""), d.get("AppName", "")
        url = f"com.epicgames.launcher://apps/{ns}%3A{cid}%3A{app}?action=launch&silent=true"
        loc = d.get("InstallLocation", "")
        exe = os.path.join(loc, d.get("LaunchExecutable", "")) if loc and d.get("LaunchExecutable") else ""
        out.append({"name": d.get("DisplayName") or app, "target": url, "category": "Juegos",
                    "source": "Epic Games", "resolved": exe, "location": loc})
    return out


def scan_gog():
    if not IS_WIN:
        return []
    import winreg
    out = []
    for path in (r"SOFTWARE\WOW6432Node\GOG.com\Games", r"SOFTWARE\GOG.com\Games"):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(key, sub) as k:
                        vals = {}
                        for v in ("gameName", "exe", "path", "workingDir", "launchParam"):
                            try:
                                vals[v] = winreg.QueryValueEx(k, v)[0]
                            except OSError:
                                vals[v] = ""
                except OSError:
                    continue
                if vals["exe"] and os.path.exists(vals["exe"]):
                    out.append({"name": vals["gameName"] or sub, "target": vals["exe"],
                                "args": vals["launchParam"], "workdir": vals["workingDir"],
                                "category": "Juegos", "source": "GOG", "location": vals["path"]})
        break
    return out


START_SKIP = re.compile(r"uninstall|desinstal|readme|l[eé]ame|help|ayuda|manual|website|sitio web|"
                        r"documentation|documentaci|release notes|license|licencia|support|soporte|"
                        r"faq|changelog|notas de la versi|eliminar", re.I)


def _entry_from_path(path, source):
    info = classify_path(path)
    resolved = info.get("target") if path.lower().endswith(".lnk") else ""
    target = path
    if path.lower().endswith((".url", ".website")) and info.get("target"):
        target = info["target"]
    return {"name": info["name"], "target": target, "category": info["category"],
            "source": source, "resolved": resolved or ""}


def scan_start_menu():
    roots = []
    if os.environ.get("APPDATA"):
        roots.append(os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs"))
    if os.environ.get("PROGRAMDATA"):
        roots.append(os.path.join(os.environ["PROGRAMDATA"], "Microsoft", "Windows", "Start Menu", "Programs"))
    out = []
    for r in roots:
        for lnk in glob.glob(os.path.join(r, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(lnk))[0]
            if START_SKIP.search(name) or os.sep + "Startup" + os.sep in lnk or os.sep + "Inicio" + os.sep in lnk:
                continue
            e = _entry_from_path(lnk, "Menú Inicio")
            if e["category"] not in ("Juegos", "Programas"):
                continue
            res = (e.get("resolved") or "").lower()
            if res.endswith((".chm", ".txt", ".html", ".htm", ".pdf")) or "unins" in os.path.basename(res):
                continue
            out.append(e)
    return out


def scan_desktop():
    out = []
    for d in (user_desktop(), public_desktop()):
        if not d or not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            # incluye las subcarpetas que crea el organizador (Juegos, Programas...)
            depth = root[len(d):].count(os.sep)
            if depth >= 1:
                dirs[:] = []
            for f in files:
                if f.lower().endswith((".lnk", ".url", ".exe", ".appref-ms")):
                    e = _entry_from_path(os.path.join(root, f), "Escritorio")
                    if e["category"] in ("Juegos", "Programas", "Web", "Carpetas"):
                        out.append(e)
    return out


# El orden importa: las tiendas primero (sus accesos no se rompen al mover el escritorio)
SCANNERS = {
    "Steam": scan_steam,
    "Epic Games": scan_epic,
    "GOG": scan_gog,
    "Escritorio": scan_desktop,
    "Menú Inicio": scan_start_menu,
}


# --------------------------------------------------------------- iconos
def icon_cache_dir():
    d = os.path.join(data_dir(), "iconos")
    os.makedirs(d, exist_ok=True)
    return d


def icon_path_for(item):
    src = icon_source(item)
    if not src:
        return None
    h = hashlib.sha1(("v2|" + src.lower()).encode("utf-8")).hexdigest()[:16]
    return os.path.join(icon_cache_dir(), h + ".png")


def icon_source(item):
    t = item.get("target") or ""
    # Los accesos directos los resuelve PowerShell (icono propio del acceso, sin flecha)
    if t.lower().endswith((".lnk", ".url", ".website")) and os.path.isfile(t):
        return t
    for cand in (item.get("resolved"), t):
        if cand and not _is_url(cand) and os.path.isfile(cand):
            return cand
    loc = item.get("location")
    if loc and os.path.isdir(loc):
        exes = glob.glob(os.path.join(loc, "*.exe"))
        exes = [e for e in exes if not re.search(r"unins|crash|setup|launcher|helper|update", os.path.basename(e), re.I)]
        if exes:
            return max(exes, key=lambda e: os.path.getsize(e))
    return None


PS_SCRIPT = r"""
Add-Type -AssemblyName System.Drawing
$wsh = New-Object -ComObject WScript.Shell
function Save-Icon($src, $dst) {
  if (-not $src) { return $false }
  $src = [Environment]::ExpandEnvironmentVariables($src.Trim().Trim('"'))
  if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { return $false }
  $ext = [IO.Path]::GetExtension($src).ToLower()
  if ($ext -eq '.dll') { return $false }
  if ($ext -eq '.ico') { $ic = New-Object System.Drawing.Icon($src, 64, 64) }
  else { $ic = [System.Drawing.Icon]::ExtractAssociatedIcon($src) }
  if (-not $ic) { return $false }
  $bmp = $ic.ToBitmap()
  $bmp.Save($dst, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose(); $ic.Dispose()
  return $true
}
$lines = Get-Content -LiteralPath $args[0] -Encoding UTF8
foreach ($line in $lines) {
  $parts = $line -split "`t"
  if ($parts.Count -lt 2) { continue }
  $src = $parts[0]; $dst = $parts[1]
  try {
    $ext = [IO.Path]::GetExtension($src).ToLower()
    if ($ext -eq '.lnk') {
      $s = $wsh.CreateShortcut($src)
      $loc = ($s.IconLocation -split ',')[0]
      $ok = $false
      try { $ok = Save-Icon $loc $dst } catch {}
      if (-not $ok) { [void](Save-Icon $s.TargetPath $dst) }
    } elseif ($ext -eq '.url' -or $ext -eq '.website') {
      $ico = Get-Content -LiteralPath $src | Where-Object { $_ -match '^IconFile=' } | Select-Object -First 1
      if ($ico) { [void](Save-Icon ($ico -replace '^IconFile=', '') $dst) }
    } else {
      [void](Save-Icon $src $dst)
    }
  } catch {}
}
"""


def extract_icons(items):
    """Extrae iconos de los .exe/.lnk con PowerShell (una sola llamada). Devuelve nº generados."""
    if not IS_WIN:
        return 0
    todo = []
    for it in items:
        if it.get("image"):
            continue
        dst = icon_path_for(it)
        if dst and not os.path.exists(dst):
            todo.append((icon_source(it), dst))
    if not todo:
        return 0
    d = icon_cache_dir()
    lst = os.path.join(d, "_lista.txt")
    ps1 = os.path.join(d, "_extraer.ps1")
    with open(lst, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(f"{s}\t{t}" for s, t in todo))
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(PS_SCRIPT)
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, lst],
                       creationflags=CREATE_NO_WINDOW, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for _, t in todo if os.path.exists(t))
