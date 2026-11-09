"""Consulta y solicitud de copias en la Wayback Machine."""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

from .red import http_get, http_json
from .util import HttpError


def wayback_info(url: str) -> dict:
    res: dict = {"enlace_archive_today": f"https://archive.ph/newest/{url}"}
    try:
        j = http_json("https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=""), timeout=25)
        closest = (j.get("archived_snapshots") or {}).get("closest")
        if closest:
            res["copia_mas_reciente"] = {"url": closest.get("url"), "fecha": closest.get("timestamp")}
    except (HttpError, ValueError) as e:
        res["error_disponibilidad"] = str(e)
    try:
        q = urllib.parse.urlencode({"url": url, "output": "json", "limit": "1", "fl": "timestamp,original,statuscode"})
        rows = http_json("https://web.archive.org/cdx/search/cdx?" + q, timeout=40)
        if isinstance(rows, list) and len(rows) > 1:
            ts, orig, code = rows[1]
            res["primera_copia"] = {"fecha": ts, "url": f"https://web.archive.org/web/{ts}/{orig}", "estado": code}
    except (HttpError, ValueError) as e:
        res["error_cdx"] = str(e)
    return res


def wayback_save(url: str) -> dict:
    try:
        _, final, h, _ = http_get("https://web.archive.org/save/" + url, timeout=150, max_bytes=50 * 1024 * 1024)
        loc = h.get("content-location")
        snap = final if "/web/" in final else (f"https://web.archive.org{loc}" if loc else None)
        return {"guardado": bool(snap), "url": snap}
    except HttpError as e:
        return {"guardado": False, "error": str(e)}


def wayback(url: str, guardar: bool = False, caso=None) -> dict:
    """Copias existentes de una URL y, si se pide, una copia nueva. Con ``caso``, registra las copias
    para poder citarlas como evidencia de tipo ``archivo``."""
    res = wayback_info(url)
    if guardar:
        res["nueva_copia"] = wayback_save(url)
    if caso is not None:
        from .caso import RegistroPaginas

        reg = RegistroPaginas(caso)
        for clave in ("primera_copia", "copia_mas_reciente", "nueva_copia"):
            copia = res.get(clave) or {}
            if copia.get("url"):
                reg.registrar(copia["url"], texto_registro(url, res), "wayback", titulo=f"Copia de {url}")
    return res


def texto_registro(url: str, res: dict) -> str:
    """Texto que se registra en el caso para poder citar la existencia y la fecha de las copias."""
    lineas = [f"Copias en archivos web de {url}"]
    for clave in ("primera_copia", "copia_mas_reciente"):
        copia = res.get(clave) or {}
        if copia.get("url"):
            lineas.append(f"{clave.replace('_', ' ')}: {copia['url']} | fecha {copia.get('fecha')}")
    nueva = res.get("nueva_copia") or {}
    if nueva.get("url"):
        lineas.append(f"nueva copia: {nueva['url']}")
    return "\n".join(lineas)
