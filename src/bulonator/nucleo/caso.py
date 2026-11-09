"""Carpeta del caso y registro de lo que se ha abierto durante la investigación.

Cada página, documento o respuesta de una API que se abre en un caso se guarda como texto en
``evidencias/paginas/`` y se anota en ``evidencias/paginas/indice.jsonl``. ``validar`` usa este
registro para comprobar que cada evidencia procede de una fuente abierta en el caso y que su cita
literal aparece en ella. Las búsquedas se anotan en ``evidencias/busquedas.jsonl``.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
import urllib.parse
from pathlib import Path
from typing import Optional

from .util import now_iso, slugify

SUBCARPETAS = ("media", "evidencias", "evidencias/paginas", "evidencias/docs", "captura_raw")
ORIGENES = {"leer", "captura", "boe", "ine", "wayback", "dominio", "factcheck", "manual"}
_ALIAS_HOST = {"twitter.com": "x.com", "mobile.twitter.com": "x.com", "mobile.x.com": "x.com",
               "m.youtube.com": "youtube.com", "youtu.be": "youtube.com"}
_CERROJO = threading.Lock()


def crear_caso(entrada: str, base: str = "bulonator-casos") -> dict:
    """Crea la carpeta de un caso nuevo y devuelve sus rutas."""
    raiz = Path(base).expanduser()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    caso = (raiz / f"{stamp}-{slugify(entrada)}").resolve()
    n = 2
    while caso.exists():
        caso = (raiz / f"{stamp}-{slugify(entrada)}-{n}").resolve()
        n += 1
    for sub in SUBCARPETAS:
        (caso / sub).mkdir(parents=True, exist_ok=True)
    return {"caso": str(caso), "media": str(caso / "media"), "evidencias": str(caso / "evidencias")}


def normalizar_url(url: str) -> str:
    """Forma canónica de una URL para comparar registros: sin esquema, www, fragmento ni barra final."""
    url = (url or "").strip()
    parts = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    host = _ALIAS_HOST.get(host, host)
    path = urllib.parse.unquote(parts.path or "").rstrip("/")
    query = urllib.parse.unquote(parts.query or "")
    return host + path + (f"?{query}" if query else "")


def _nombre_archivo(url: str, origen: str) -> str:
    h = hashlib.sha1(normalizar_url(url).encode("utf-8")).hexdigest()[:12]
    return f"p-{h}-{origen}.txt"


class RegistroPaginas:
    """Registro de los textos abiertos en un caso."""

    def __init__(self, caso):
        self.caso = Path(caso).expanduser().resolve()
        self.carpeta = self.caso / "evidencias" / "paginas"
        self.indice = self.carpeta / "indice.jsonl"

    def registrar(self, url: str, texto: str, origen: str, titulo: Optional[str] = None,
                  url_final: Optional[str] = None, content_type: Optional[str] = None,
                  extra: Optional[dict] = None) -> dict:
        if origen not in ORIGENES:
            raise ValueError(f"origen desconocido: {origen}")
        self.carpeta.mkdir(parents=True, exist_ok=True)
        archivo = self.carpeta / _nombre_archivo(url, origen)
        texto = texto or ""
        entrada = {
            "url": url, "url_final": url_final or url, "origen": origen, "titulo": titulo,
            "archivo": archivo.name, "caracteres": len(texto),
            "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
            "content_type": content_type, "registrado": now_iso(),
        }
        if extra:
            entrada.update(extra)
        with _CERROJO:
            archivo.write_text(texto, encoding="utf-8")
            with open(self.indice, "a", encoding="utf-8") as f:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        return dict(entrada, ruta=str(archivo))

    def entradas(self) -> list:
        if not self.indice.is_file():
            return []
        vistas = {}
        for linea in self.indice.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                e = json.loads(linea)
            except ValueError:
                continue
            vistas[(normalizar_url(e.get("url", "")), e.get("origen"))] = e  # la última gana
        return list(vistas.values())

    def de(self, url: str) -> list:
        """Registros de una URL (coincide con la URL pedida o con la final tras redirecciones)."""
        clave = normalizar_url(url)
        return [e for e in self.entradas()
                if clave in {normalizar_url(e.get("url", "")), normalizar_url(e.get("url_final", ""))}]

    def texto(self, entrada: dict) -> str:
        archivo = self.carpeta / entrada["archivo"]
        return archivo.read_text(encoding="utf-8") if archivo.is_file() else ""

    def textos_de(self, url: str) -> list:
        return [(e, self.texto(e)) for e in self.de(url)]


def registrar_busqueda(caso, consulta: str, herramienta: str, resultados: list,
                       dominios: Optional[list] = None, error: Optional[str] = None) -> None:
    """Anota una búsqueda (también las que no dan resultados) en ``evidencias/busquedas.jsonl``."""
    destino = Path(caso).expanduser().resolve() / "evidencias" / "busquedas.jsonl"
    destino.parent.mkdir(parents=True, exist_ok=True)
    fila = {"consulta": consulta, "herramienta": herramienta, "dominios": dominios or [],
            "resultados": len(resultados), "urls": [r.get("url") for r in resultados[:10]],
            "error": error, "fecha": now_iso()}
    with _CERROJO, open(destino, "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def busquedas(caso) -> list:
    destino = Path(caso).expanduser().resolve() / "evidencias" / "busquedas.jsonl"
    if not destino.is_file():
        return []
    filas = []
    for linea in destino.read_text(encoding="utf-8").splitlines():
        try:
            filas.append(json.loads(linea))
        except ValueError:
            continue
    return filas
