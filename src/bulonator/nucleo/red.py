"""Acceso a la red: URL seguras, descargas y dominios."""
from __future__ import annotations

import gzip
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

from .util import MAX_MEDIA_BYTES, MAX_PAGE_BYTES, TIMEOUT, UA, HttpError


def safe_url(url: str) -> str:
    """Convierte una IRI (con tildes, espacios, eñes...) en una URL ASCII válida."""
    parts = urllib.parse.urlsplit(url.strip())
    try:
        host = (parts.hostname or "").encode("idna").decode("ascii")
    except UnicodeError:
        host = parts.hostname or ""
    netloc = host + (f":{parts.port}" if parts.port else "")
    if parts.username:
        netloc = f"{parts.username}@{netloc}"
    keep = "/%:@!$&'()*+,;=-._~"
    return urllib.parse.urlunsplit((parts.scheme, netloc, urllib.parse.quote(parts.path, safe=keep),
                                    urllib.parse.quote(parts.query, safe=keep + "?"), ""))


_PERMITIR_RED_PRIVADA = False


def permitir_red_privada(valor: bool = True) -> None:
    """Permite (o vuelve a bloquear) las peticiones a direcciones locales y privadas."""
    global _PERMITIR_RED_PRIVADA
    _PERMITIR_RED_PRIVADA = valor


def red_privada_permitida() -> bool:
    env = os.environ.get("BULONATOR_PERMITIR_RED_PRIVADA", "").strip().lower()
    return _PERMITIR_RED_PRIVADA or env in {"1", "true", "si", "sí", "yes"}


def _ip_interna(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified)


def _solo_http(url: str) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        raise HttpError(f"esquema no permitido ({parts.scheme or 'ninguno'}): {url}")
    if not parts.hostname:
        raise HttpError(f"URL sin servidor: {url}")
    return parts


def comprobar_destino(url: str) -> None:
    """Rechaza esquemas que no sean http(s) y, salvo permiso expreso, las direcciones internas.

    Protege frente a peticiones dirigidas a la propia máquina, la red local o el servicio de
    metadatos de la nube cuando se analizan enlaces que envían terceros.
    """
    parts = _solo_http(url)
    host = (parts.hostname or "").strip("[]")
    if red_privada_permitida():
        return
    try:
        direcciones = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parts.port or None, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError, OSError):
            return  # la conexión fallará después con un mensaje propio
        direcciones = []
        for info in infos:
            try:
                direcciones.append(ipaddress.ip_address(info[4][0].split("%")[0]))
            except ValueError:
                continue
    for ip in direcciones:
        if _ip_interna(ip):
            raise HttpError(f"dirección interna bloqueada ({ip}) en {url}. Si es intencionado, "
                            "define BULONATOR_PERMITIR_RED_PRIVADA=1")


class _RedireccionSegura(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        comprobar_destino(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_RedireccionSegura)


def _open(url: str, headers: dict | None, timeout: int, data: bytes | None = None,
          interna_permitida: bool = False):
    try:
        url = safe_url(url)
    except ValueError as e:
        raise HttpError(f"URL no válida: {url} ({e})") from e
    if interna_permitida:
        _solo_http(url)
    else:
        comprobar_destino(url)
    hdrs = {
        "User-Agent": UA,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs)
    try:
        return _OPENER.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise HttpError(f"HTTP {e.code} al pedir {url}") from e
    except urllib.error.URLError as e:
        hint = ""
        if "CERTIFICATE" in str(e.reason).upper():
            hint = " (instala los certificados raíz de Python, p. ej. 'Install Certificates.command')"
        raise HttpError(f"no se pudo conectar con {url}: {e.reason}{hint}") from e
    except (TimeoutError, OSError, ValueError, UnicodeError) as e:
        raise HttpError(f"error de red con {url}: {e}") from e


def http_get(url: str, headers: dict | None = None, timeout: int = TIMEOUT,
             max_bytes: int = MAX_PAGE_BYTES, data: bytes | None = None, interna_permitida: bool = False) -> tuple[int, str, dict, bytes]:
    """GET con descompresión. Devuelve (estado, url_final, cabeceras, cuerpo)."""
    with _open(url, headers, timeout, data, interna_permitida) as r:
        try:
            raw = r.read(max_bytes + 1)
        except (OSError, http.client.HTTPException) as e:
            raise HttpError(f"lectura interrumpida de {url}: {e}") from e
        if len(raw) > max_bytes:
            raise HttpError(f"respuesta demasiado grande (> {max_bytes} bytes): {url}")
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            raw = gzip.decompress(raw)
        elif enc == "deflate":
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        return r.status, r.geturl(), hdrs, raw


def decode_body(raw: bytes, headers: dict) -> str:
    m = re.search(r"charset=([\w.-]+)", headers.get("content-type", ""), re.I)
    charset = m.group(1) if m else None
    if not charset:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w.-]+)", raw[:4096], re.I)
        charset = m2.group(1).decode("ascii", "ignore") if m2 else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def http_json(url: str, headers: dict | None = None, timeout: int = TIMEOUT, datos=None,
              interna_permitida: bool = False):
    """GET (o POST con ``datos``, que se envían como JSON) y decodifica la respuesta JSON."""
    hdrs = {"Accept": "application/json"}
    hdrs.update(headers or {})
    cuerpo = None
    if datos is not None:
        cuerpo = json.dumps(datos).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    _, _, h, raw = http_get(url, hdrs, timeout, data=cuerpo, interna_permitida=interna_permitida)
    return json.loads(decode_body(raw, h))


EXT_BY_CTYPE = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
    "image/avif": ".avif", "image/heic": ".heic", "video/mp4": ".mp4", "video/webm": ".webm",
    "video/quicktime": ".mov", "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "application/pdf": ".pdf",
}


def guess_ext(url: str, ctype: str = "") -> str:
    ctype = (ctype or "").split(";")[0].strip().lower()
    if ctype in EXT_BY_CTYPE:
        return EXT_BY_CTYPE[ctype]
    path = urllib.parse.urlsplit(url).path
    ext = os.path.splitext(path)[1].lower()
    if re.fullmatch(r"\.[a-z0-9]{2,5}", ext):
        return ext
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    fmt = (q.get("format") or [""])[0].lower()
    return f".{fmt}" if fmt in {"jpg", "jpeg", "png", "webp", "gif"} else ".bin"


def download(url: str, dest_dir: Path, stem: str, max_bytes: int = MAX_MEDIA_BYTES,
             timeout: int = 90) -> dict:
    """Descarga un fichero a dest_dir/stem.<ext> y devuelve ruta, tamaño y sha256."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    with _open(url, {"Accept-Encoding": "identity"}, timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        dest = dest_dir / (stem + guess_ext(url, ctype))
        tmp = dest.with_name(dest.name + ".part")
        with open(tmp, "wb") as f:
            while True:
                try:
                    chunk = r.read(1 << 16)
                except (OSError, http.client.HTTPException) as e:
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise HttpError(f"descarga interrumpida de {url}: {e}") from e
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise HttpError(f"fichero demasiado grande (> {max_bytes} bytes): {url}")
                h.update(chunk)
                f.write(chunk)
    tmp.replace(dest)
    return {"archivo": str(dest), "bytes": size, "sha256": h.hexdigest(), "content_type": ctype}


def registered_domain(host: str) -> str:
    host = (host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "gob", "gov", "net", "edu", "ac", "nom", "mil", "gv"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def host_of(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


# ---------------------------------------------------------------------------
