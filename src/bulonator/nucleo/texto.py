"""Longitud de los textos para redes sociales y extracción de los bloques de ``publicacion.md``."""
from __future__ import annotations

import re
import unicodedata

from .reglas import plataformas

URL_RE = re.compile(r"https?://\S+|\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|es|org|net|gob\.es|eu|cat|gal|eus|info|io|me|ly)(?:/\S*)?",
                    re.I)
BLOQUE_RE = re.compile(r"```(?:text|txt|post)?\n(.*?)```", re.S)


def limites() -> dict:
    return {nombre: conf["limite"] for nombre, conf in plataformas().items()}


def x_weight(text: str) -> int:
    """Longitud ponderada según las reglas de X: cada URL cuenta 23, emojis y CJK cuentan 2."""
    conf = plataformas()["x"]
    total = 0
    pos = 0
    for m in URL_RE.finditer(text):
        total += _x_chars(text[pos:m.start()], conf.get("emoji", 2)) + conf.get("enlace", 23)
        pos = m.end()
    return total + _x_chars(text[pos:], conf.get("emoji", 2))


def _x_chars(text: str, pesado: int = 2) -> int:
    n = 0
    for ch in unicodedata.normalize("NFC", text):
        cp = ord(ch)
        if cp in (0x200D, 0xFE0F) or 0x1F3FB <= cp <= 0x1F3FF:
            continue  # unión de emojis, selector de variación, tono de piel
        light = (cp <= 0x10FF or 0x2000 <= cp <= 0x200D or 0x2010 <= cp <= 0x201F or 0x2032 <= cp <= 0x2037)
        n += 1 if light else pesado
    return n


def longitud(texto: str, plataforma: str) -> int:
    """Longitud de un texto según cómo cuenta cada plataforma (``reglas.json`` → ``plataformas``)."""
    conf = plataformas()[plataforma]
    if conf["cuenta"] == "ponderada":
        return x_weight(texto)
    if "enlace" in conf:
        total, pos = 0, 0
        for m in URL_RE.finditer(texto):
            total += len(unicodedata.normalize("NFC", texto[pos:m.start()])) + conf["enlace"]
            pos = m.end()
        return total + len(unicodedata.normalize("NFC", texto[pos:]))
    return len(unicodedata.normalize("NFC", texto))


def bloques(markdown: str) -> list:
    """Bloques ```text … ``` de un Markdown, sin los saltos de línea de los extremos."""
    return [b.strip("\n") for b in BLOQUE_RE.findall(markdown)]


def contar(texto: str, por_bloques: bool = False) -> dict:
    trozos = bloques(texto) if por_bloques else [texto]
    rows = []
    for i, b in enumerate(trozos, 1):
        medidas = {nombre: longitud(b, nombre) for nombre in plataformas()}
        rows.append({"bloque": i, "inicio": b[:60], "x_ponderado": medidas["x"],
                     "caracteres": len(unicodedata.normalize("NFC", b)),
                     "cabe_en": [n for n, lim in limites().items() if medidas[n] <= lim]})
    return {"limites": limites(), "bloques": rows,
            "nota": "X cuenta cada enlace como 23 caracteres y los emojis como 2. Bluesky y Threads cuentan "
                    "caracteres; Mastodon cuenta cada enlace como 23 (aproximado)."}
