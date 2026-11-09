"""Utilidades generales del núcleo: errores, fechas, procesos y nombres."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import subprocess
import unicodedata
from pathlib import Path

from .. import __version__ as VERSION

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 Bulonator/" + VERSION
)
TIMEOUT = 30
MAX_PAGE_BYTES = 20 * 1024 * 1024
MAX_MEDIA_BYTES = 500 * 1024 * 1024


class HttpError(Exception):
    """Fallo de red o respuesta HTTP no satisfactoria."""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")



def run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Ejecuta un comando sin shell y devuelve (código, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: no encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: tiempo agotado ({timeout} s)"


def tail(text: str, n: int = 600) -> str:
    text = (text or "").strip()
    return text[-n:]


def slugify(text: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"^https?://", "", text.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:max_len].strip("-")) or "caso"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def texto_plano(datos, excluir=frozenset()) -> str:
    """Convierte un diccionario anidado en líneas ``clave: valor`` (para registrar resultados)."""
    lineas: list = []

    def recorrer(valor, prefijo):
        if isinstance(valor, dict):
            for k, v in valor.items():
                if prefijo == "" and k in excluir:
                    continue
                recorrer(v, f"{prefijo}.{k}" if prefijo else k)
        elif isinstance(valor, list):
            for n, v in enumerate(valor, 1):
                recorrer(v, f"{prefijo}[{n}]")
        elif valor not in (None, ""):
            lineas.append(f"{prefijo}: {valor}")

    recorrer(datos, "")
    return "\n".join(lineas)

