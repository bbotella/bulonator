"""``leer``: abre una página o un documento, guarda su texto en el caso y lo registra.

Es la forma de abrir cualquier fuente que se vaya a citar: ``validar`` comprueba después que la
URL de cada evidencia está registrada y que su cita literal aparece en el texto guardado.
"""
from __future__ import annotations

import io
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from .caso import RegistroPaginas
from .extraccion import extract_page
from .red import decode_body, http_get
from .util import HttpError, slugify

MAX_DOC_BYTES = 60 * 1024 * 1024
MAX_PAGINAS_PDF = 300
_OMITIR = {"script", "style", "noscript", "template", "svg", "head", "iframe", "object"}
_BLOQUE = {"p", "div", "section", "article", "main", "header", "footer", "nav", "aside", "li", "ul", "ol",
           "table", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "figure",
           "figcaption", "br", "hr", "dt", "dd", "caption", "form", "label"}
_TIPOS_TEXTO = ("text/plain", "text/csv", "application/json", "application/xml", "text/xml",
                "application/ld+json", "application/rss+xml", "application/atom+xml")


class _TextoVisible(HTMLParser):
    """Todo el texto visible de una página, con saltos de línea en los elementos de bloque."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list = []
        self.omitir = 0

    def handle_starttag(self, tag, attrs):
        if tag in _OMITIR:
            self.omitir += 1
        elif tag in _BLOQUE:
            self.partes.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in _BLOQUE:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in _OMITIR:
            self.omitir = max(0, self.omitir - 1)
        elif tag in _BLOQUE:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self.omitir:
            self.partes.append(data)

    def texto(self) -> str:
        crudo = "".join(self.partes)
        lineas = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in crudo.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def texto_visible(html_text: str) -> str:
    p = _TextoVisible()
    try:
        p.feed(html_text)
        p.close()
    except (AssertionError, ValueError):
        pass
    return p.texto()


def texto_pdf(datos: bytes) -> Optional[str]:
    """Texto de un PDF con ``pypdf`` (opcional). Devuelve None si no está instalado o falla."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        lector = PdfReader(io.BytesIO(datos))
        paginas = []
        for n, pagina in enumerate(lector.pages[:MAX_PAGINAS_PDF], 1):
            paginas.append(f"[página {n}]\n{pagina.extract_text() or ''}")
        return "\n\n".join(paginas).strip() or None
    except Exception:  # pypdf lanza muchos tipos de error con PDF dañados
        return None


def _recortar(texto: str, maximo: int) -> str:
    if maximo <= 0 or len(texto) <= maximo:
        return texto
    return texto[:maximo] + f"… [recortado: {len(texto)} caracteres en total; el texto completo está guardado]"


def leer(url: str, caso, max_texto: int = 4000, desde_archivo: Optional[str] = None,
         titulo: Optional[str] = None) -> dict:
    """Abre ``url``, guarda su texto en ``<caso>/evidencias/paginas/`` y lo registra.

    Con ``desde_archivo`` no se descarga nada: se registra el texto de ese archivo como obtenido de
    ``url`` por otra vía (un navegador, un PDF leído a mano). Queda marcado con origen ``manual``.
    """
    reg = RegistroPaginas(caso)
    if desde_archivo:
        texto = Path(desde_archivo).expanduser().read_text(encoding="utf-8")
        e = reg.registrar(url, texto, "manual", titulo=titulo)
        return {"url": url, "origen": "manual", "archivo": e["ruta"], "caracteres": len(texto),
                "texto": _recortar(texto, max_texto)}

    _, final, cabeceras, cuerpo = http_get(url, max_bytes=MAX_DOC_BYTES)
    ctype = (cabeceras.get("content-type") or "").split(";")[0].strip().lower()
    res: dict = {"url": url, "url_final": final, "content_type": ctype}
    if ctype == "application/pdf" or cuerpo[:5] == b"%PDF-":
        docs = Path(caso).expanduser().resolve() / "evidencias" / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        destino = docs / (slugify(final, 80) + ".pdf")
        destino.write_bytes(cuerpo)
        res["pdf"] = str(destino)
        texto = texto_pdf(cuerpo)
        if texto is None:
            res.update({"texto_extraido": False, "aviso": (
                "No se ha podido extraer el texto del PDF (instala pypdf o léelo a mano). Para citarlo, "
                "copia el pasaje en un archivo de texto y regístralo con leer --desde-archivo.")})
            return res
        res["titulo"] = titulo or destino.stem
    elif ctype in ("text/html", "application/xhtml+xml") or (not ctype and b"<html" in cuerpo[:2000].lower()):
        html_text = decode_body(cuerpo, cabeceras)
        info = extract_page(final, html_text)
        texto = texto_visible(html_text)
        if info.get("titulo") and info["titulo"] not in texto[:500]:
            texto = info["titulo"] + "\n\n" + texto
        res.update({k: info.get(k) for k in ("titulo", "medio", "autor", "fecha_publicacion", "fecha_modificacion",
                                             "idioma", "canonica")})
        if len(texto) < 300:
            res["aviso"] = ("Se ha extraído poco texto: la página puede cargarse con JavaScript, tener muro de "
                            "pago o requerir sesión. Si lo abres con un navegador, registra el texto con "
                            "leer --desde-archivo.")
    elif ctype.startswith("text/") or ctype in _TIPOS_TEXTO:
        texto = decode_body(cuerpo, cabeceras)
        if "json" in ctype:
            try:
                texto = json.dumps(json.loads(texto), ensure_ascii=False, indent=1)
            except ValueError:
                pass
    else:
        raise HttpError(f"tipo de contenido que no se puede leer como texto ({ctype or 'desconocido'}): {final}")
    e = reg.registrar(url, texto, "leer", titulo=titulo or res.get("titulo"), url_final=final, content_type=ctype)
    res.update({"origen": "leer", "archivo": e["ruta"], "caracteres": len(texto), "texto": _recortar(texto, max_texto),
                "nota": "Copia las citas literales de este texto: validar las buscará en la copia guardada."})
    return res
