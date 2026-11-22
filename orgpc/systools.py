"""Información del sistema, procesos, programas de inicio y herramientas rápidas."""
import os
import shutil
import struct
import subprocess
import time

from .platform_utils import (CREATE_NO_WINDOW, IS_WIN, app_command, open_target, run_elevated,
                             startup_folders)

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def system_drive():
    if IS_WIN:
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def stats():
    s = {"cpu": None, "ram_pct": None, "ram_used": 0, "ram_total": 0,
         "disk_pct": None, "disk_free": 0, "disk_total": 0, "uptime": None}
    if psutil:
        s["cpu"] = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        s.update(ram_pct=vm.percent, ram_used=vm.used, ram_total=vm.total)
        s["uptime"] = time.time() - psutil.boot_time()
    try:
        du = shutil.disk_usage(system_drive())
        s.update(disk_pct=du.used / du.total * 100, disk_free=du.free, disk_total=du.total)
    except OSError:
        pass
    return s


PROTECTED = {
    "system", "system idle process", "registry", "memory compression", "smss.exe", "csrss.exe",
    "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
    "explorer.exe", "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "msmpeng.exe", "audiodg.exe",
    "spoolsv.exe", "taskhostw.exe", "runtimebroker.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "securityhealthservice.exe", "lsaiso.exe", "conhost.exe", "dllhost.exe",
    "wudfhost.exe", "nissrv.exe", "textinputhost.exe", "systemsettings.exe", "init", "systemd",
}


def top_processes(limit=25):
    if not psutil:
        return []
    me = os.getpid()
    groups = {}
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = p.info["name"] or "?"
            mem = p.info["memory_info"].rss if p.info["memory_info"] else 0
        except (psutil.Error, AttributeError):
            continue
        g = groups.setdefault(name.lower(), {"name": name, "count": 0, "mem": 0, "pids": []})
        g["count"] += 1
        g["mem"] += mem
        g["pids"].append(p.info["pid"])
    own = {n for n, g in groups.items() if me in g["pids"]}
    out = sorted(groups.values(), key=lambda g: g["mem"], reverse=True)[:limit]
    for g in out:
        g["protected"] = g["name"].lower() in PROTECTED or g["name"].lower() in own
    return out


def kill_pids(pids):
    killed = failed = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            killed += 1
        except Exception:  # noqa: BLE001
            failed += 1
    return killed, failed


# ------------------------------------------------------------ inicio
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN32 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def _approved_state(winreg, root, kind, name):
    try:
        with winreg.OpenKey(root, APPROVED + "\\" + kind) as k:
            data, _ = winreg.QueryValueEx(k, name)
            return not (bytes(data)[0] & 1)
    except OSError:
        return True


def startup_items():
    if not IS_WIN:
        return []
    import winreg
    items = []
    locations = [
        (winreg.HKEY_CURRENT_USER, RUN, "Run", "Usuario (registro)"),
        (winreg.HKEY_LOCAL_MACHINE, RUN, "Run", "Todos los usuarios (registro)"),
        (winreg.HKEY_LOCAL_MACHINE, RUN32, "Run32", "Todos los usuarios (registro 32 bits)"),
    ]
    for root, path, kind, label in locations:
        try:
            key = winreg.OpenKey(root, path)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                items.append({"name": name, "command": str(value), "where": label,
                              "root": "HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM",
                              "kind": kind, "enabled": _approved_state(winreg, root, kind, name)})
    user_sf, common_sf = startup_folders()
    for folder, root, label in ((user_sf, winreg.HKEY_CURRENT_USER, "Carpeta Inicio (usuario)"),
                                (common_sf, winreg.HKEY_LOCAL_MACHINE, "Carpeta Inicio (todos)")):
        if not folder or not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if f.lower() == "desktop.ini":
                continue
            items.append({"name": f, "command": os.path.join(folder, f), "where": label,
                          "root": "HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM",
                          "kind": "StartupFolder",
                          "enabled": _approved_state(winreg, root, "StartupFolder", f)})
    items.sort(key=lambda x: x["name"].lower())
    return items


def set_startup_enabled(item, enabled):
    """Activa/desactiva igual que el Administrador de tareas (reversible)."""
    import winreg
    root = winreg.HKEY_CURRENT_USER if item["root"] == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    if enabled:
        data = bytes([2]) + bytes(11)
    else:
        ft = int((time.time() + 11644473600) * 10_000_000)
        data = bytes([3, 0, 0, 0]) + struct.pack("<Q", ft)
    with winreg.CreateKeyEx(root, APPROVED + "\\" + item["kind"], 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, item["name"], 0, winreg.REG_BINARY, data)


# ---------------------------------------------- arrancar esta app con Windows
SELF_RUN_NAME = "OrganizadorPC"


def self_autostart_enabled():
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            winreg.QueryValueEx(k, SELF_RUN_NAME)
            return True
    except OSError:
        return False


def set_self_autostart(enabled):
    if not IS_WIN:
        return
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            exe, args = app_command()
            cmd = " ".join(f'"{x}"' for x in [exe] + args) + " --minimizado"
            winreg.SetValueEx(k, SELF_RUN_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, SELF_RUN_NAME)
            except OSError:
                pass


# ------------------------------------------------------- herramientas
def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
                       encoding="cp850" if IS_WIN else None, errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def flush_dns():
    code, out = _run(["ipconfig", "/flushdns"])
    return code == 0, "Caché DNS vaciada correctamente." if code == 0 else out.strip()


HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def set_power_plan(guid):
    code, out = _run(["powercfg", "/setactive", guid])
    if code != 0 and guid in (HIGH_PERF, ULTIMATE):
        # En algunos portátiles el plan está oculto: se duplica y se activa
        code2, out2 = _run(["powercfg", "-duplicatescheme", guid])
        import re
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", out2, re.I)
        if code2 == 0 and m:
            code, out = _run(["powercfg", "/setactive", m.group(1)])
    return code == 0, "Plan de energía cambiado." if code == 0 else (out.strip() or "No disponible en este equipo.")


def active_power_plan():
    code, out = _run(["powercfg", "/getactivescheme"])
    if code != 0:
        return "?"
    if "(" in out:
        return out[out.rfind("(") + 1:out.rfind(")")]
    return out.strip()


def open_tool(name):
    tools = {
        "cleanmgr": lambda: subprocess.Popen(["cleanmgr"]),
        "dfrgui": lambda: subprocess.Popen(["dfrgui"]),
        "taskmgr": lambda: subprocess.Popen(["taskmgr"]),
        "storage": lambda: open_target("ms-settings:storagesense"),
        "apps": lambda: open_target("ms-settings:appsfeatures"),
        "startup_settings": lambda: open_target("ms-settings:startupapps"),
        "sfc": lambda: run_elevated("cmd.exe", "/k sfc /scannow"),
        "dism": lambda: run_elevated("cmd.exe", "/k DISM /Online /Cleanup-Image /RestoreHealth"),
        "gamemode": lambda: open_target("ms-settings:gaming-gamemode"),
        "graphics": lambda: open_target("ms-settings:display-advancedgraphics"),
        "visual": lambda: subprocess.Popen(["SystemPropertiesPerformance.exe"]),
    }
    tools[name]()
