"""``buscar``: búsqueda web con buscadores intercambiables (SearXNG, Brave o Tavily).

El buscador se elige con ``BULONATOR_BUSCADOR`` o, si no se indica, por la configuración que haya:
``BULONATOR_SEARXNG_URL`` (instancia propia, con el formato JSON activado), ``BRAVE_API_KEY`` o
``TAVILY_API_KEY``. Los resultados solo sirven para encontrar páginas: un extracto de buscador no es
una evidencia; la página hay que abrirla con ``leer``.
"""
from __future__ import annotations

import os
import urllib.parse
from typing import Optional

from .caso import registrar_busqueda
from .red import host_of, http_json
from .util import HttpError

BUSCADORES = ("searxng", "brave", "tavily")
NOTA = ("Los extractos no son evidencia: abre con `leer` las páginas que vayas a citar. "
        "Anota también las búsquedas sin resultados.")


def buscador_configurado() -> Optional[str]:
    elegido = os.environ.get("BULONATOR_BUSCADOR", "").strip().lower()
    if elegido:
        return elegido if elegido in BUSCADORES else None
    if os.environ.get("BULONATOR_SEARXNG_URL"):
        return "searxng"
    if os.environ.get("BRAVE_API_KEY"):
        return "brave"
    if os.environ.get("TAVILY_API_KEY"):
        return "tavily"
    return None


def _con_dominios(consulta: str, dominios: list) -> str:
    if not dominios:
        return consulta
    sitios = " OR ".join(f"site:{d}" for d in dominios)
    return f"{consulta} ({sitios})" if len(dominios) > 1 else f"{consulta} {sitios}"


def _en_dominios(url: str, dominios: list) -> bool:
    if not dominios:
        return True
    host = host_of(url)
    return any(host == d or host.endswith("." + d) for d in dominios)


def _searxng(consulta: str, dominios: list, maximo: int, idioma: str) -> list:
    base = os.environ.get("BULONATOR_SEARXNG_URL", "").rstrip("/")
    if not base:
        raise ValueError("falta BULONATOR_SEARXNG_URL")
    q = urllib.parse.urlencode({"q": _con_dominios(consulta, dominios), "format": "json", "language": idioma})
    # La instancia de SearXNG la configura quien usa Bulonator: puede estar en la red local.
    data = http_json(f"{base}/search?{q}", timeout=40, interna_permitida=True)
    return [{"titulo": r.get("title"), "url": r.get("url"), "extracto": r.get("content"),
             "fecha": r.get("publishedDate")} for r in data.get("results", [])[: maximo * 2]]


def _brave(consulta: str, dominios: list, maximo: int, idioma: str) -> list:
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        raise ValueError("falta BRAVE_API_KEY")
    q = urllib.parse.urlencode({"q": _con_dominios(consulta, dominios), "count": min(20, maximo * 2),
                                "search_lang": idioma})
    data = http_json(f"https://api.search.brave.com/res/v1/web/search?{q}",
                     headers={"X-Subscription-Token": key}, timeout=30)
    return [{"titulo": r.get("title"), "url": r.get("url"), "extracto": r.get("description"),
             "fecha": r.get("page_age") or r.get("age")} for r in (data.get("web") or {}).get("results", [])]


def _tavily(consulta: str, dominios: list, maximo: int, idioma: str) -> list:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise ValueError("falta TAVILY_API_KEY")
    cuerpo = {"query": consulta, "max_results": min(20, maximo), "search_depth": "basic"}
    if dominios:
        cuerpo["include_domains"] = dominios
    data = http_json("https://api.tavily.com/search", headers={"Authorization": f"Bearer {key}"},
                     timeout=40, datos=cuerpo)
    return [{"titulo": r.get("title"), "url": r.get("url"), "extracto": r.get("content"),
             "fecha": r.get("published_date")} for r in data.get("results", [])]


_FUNCIONES = {"searxng": _searxng, "brave": _brave, "tavily": _tavily}


def buscar(consulta: str, dominios: Optional[list] = None, max_resultados: int = 10,
           buscador: Optional[str] = None, idioma: str = "es", caso=None) -> dict:
    """Busca en la web. Con ``caso``, anota la búsqueda en ``evidencias/busquedas.jsonl``."""
    dominios = [d.strip().lower().removeprefix("www.") for d in (dominios or []) if d.strip()]
    nombre = (buscador or buscador_configurado() or "").lower()
    if nombre not in _FUNCIONES:
        raise ValueError("no hay buscador configurado: define BULONATOR_SEARXNG_URL, BRAVE_API_KEY o "
                         "TAVILY_API_KEY (o BULONATOR_BUSCADOR=searxng|brave|tavily)")
    try:
        crudos = _FUNCIONES[nombre](consulta, dominios, max_resultados, idioma)
    except (HttpError, ValueError) as e:
        if caso is not None:
            registrar_busqueda(caso, consulta, nombre, [], dominios, error=str(e))
        raise
    vistos, resultados = set(), []
    for r in crudos:
        url = r.get("url")
        if not url or url in vistos or not _en_dominios(url, dominios):
            continue
        vistos.add(url)
        resultados.append(r)
        if len(resultados) >= max_resultados:
            break
    if caso is not None:
        registrar_busqueda(caso, consulta, nombre, resultados, dominios)
    return {"consulta": consulta, "buscador": nombre, "dominios": dominios, "resultados": resultados,
            "nota": NOTA}
