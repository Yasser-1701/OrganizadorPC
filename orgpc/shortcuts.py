"""Lectura de accesos directos de Windows (.lnk y .url) sin dependencias externas.
Implementa la parte necesaria del formato MS-SHLLINK."""
import os
import struct

from .platform_utils import IS_WIN

ANSI = "mbcs" if IS_WIN else "cp1252"


def _read_astr(data, off):
    end = data.find(b"\x00", off)
    if end < 0:
        end = len(data)
    return data[off:end].decode(ANSI, "replace")


def _read_wstr(data, off):
    end = off
    while end + 1 < len(data) and data[end:end + 2] != b"\x00\x00":
        end += 2
    return data[off:end].decode("utf-16-le", "replace")


def parse_lnk(path):
    """Devuelve {'target','args','workdir','icon'} o None si no se puede leer."""
    try:
        with open(path, "rb") as f:
            data = f.read(1024 * 256)
    except OSError:
        return None
    try:
        if len(data) < 0x4C or struct.unpack_from("<I", data, 0)[0] != 0x4C:
            return None
        flags = struct.unpack_from("<I", data, 0x14)[0]
        pos = 0x4C
        if flags & 0x01:  # HasLinkTargetIDList
            idsize = struct.unpack_from("<H", data, pos)[0]
            pos += 2 + idsize

        target = None
        if flags & 0x02:  # HasLinkInfo
            start = pos
            li_size, li_hsize, li_flags, _vol, lbp, cnr, cps = struct.unpack_from("<7I", data, pos)
            lbp_u = cps_u = 0
            if li_hsize >= 0x24:
                lbp_u, cps_u = struct.unpack_from("<2I", data, pos + 28)
            suffix = ""
            if cps_u:
                suffix = _read_wstr(data, start + cps_u)
            elif cps:
                suffix = _read_astr(data, start + cps)
            if li_flags & 0x1:
                base = _read_wstr(data, start + lbp_u) if lbp_u else _read_astr(data, start + lbp)
                target = base + suffix if base else None
            elif li_flags & 0x2 and cnr:
                cstart = start + cnr
                net_off = struct.unpack_from("<I", data, cstart + 8)[0]
                net = _read_astr(data, cstart + net_off)
                if net:
                    target = net + ("\\" + suffix if suffix else "")
            pos = start + li_size

        unicode = bool(flags & 0x80)
        strings = {}
        for bit, key in ((0x04, "name"), (0x08, "relpath"), (0x10, "workdir"),
                         (0x20, "args"), (0x40, "icon")):
            if flags & bit:
                n = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                if unicode:
                    strings[key] = data[pos:pos + n * 2].decode("utf-16-le", "replace")
                    pos += n * 2
                else:
                    strings[key] = data[pos:pos + n].decode(ANSI, "replace")
                    pos += n

        env_target = None
        while pos + 8 <= len(data):
            bsize = struct.unpack_from("<I", data, pos)[0]
            if bsize < 8:
                break
            sig = struct.unpack_from("<I", data, pos + 4)[0]
            if sig == 0xA0000001 and bsize >= 0x314:  # EnvironmentVariableDataBlock
                w = data[pos + 268:pos + 788].decode("utf-16-le", "replace").split("\x00")[0]
                a = data[pos + 8:pos + 268].split(b"\x00")[0].decode(ANSI, "replace")
                env_target = w or a
            pos += bsize

        if not target and env_target:
            target = os.path.expandvars(env_target)
        if not target and strings.get("relpath"):
            target = os.path.normpath(os.path.join(os.path.dirname(path), strings["relpath"]))
        return {
            "target": target or "",
            "args": strings.get("args", ""),
            "workdir": os.path.expandvars(strings.get("workdir", "")),
            "icon": os.path.expandvars(strings.get("icon", "")),
        }
    except (struct.error, IndexError, ValueError):
        return None


def parse_url_file(path):
    """Lee un archivo .url (acceso a internet / juego de Steam, Epic...)."""
    url = icon = ""
    for enc in ("utf-8-sig", ANSI):
        try:
            with open(path, "r", encoding=enc) as f:
                for line in f:
                    line = line.strip()
                    low = line.lower()
                    if low.startswith("url=") and not url:
                        url = line[4:].strip()
                    elif low.startswith("iconfile="):
                        icon = line[9:].strip()
            break
        except (OSError, UnicodeDecodeError):
            continue
    return {"url": url, "icon": icon}
