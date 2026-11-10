"""Herramientas del motor: las capacidades de la metodología como herramientas tipadas de Pydantic AI.

El modelo nunca recibe una terminal: solo estas funciones, que llaman al núcleo y registran en el
caso lo que abren. Los errores se devuelven como ``{"error": …}`` para que el modelo pueda seguir.
Los nombres coinciden con las capacidades que citan los agentes (`buscar`, `leer`, `boe`…).
"""
from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic_ai import BinaryContent, FunctionToolset, RunContext

from .. import nucleo
from ..nucleo.caso import RegistroPaginas
from ..nucleo.util import HttpError
from .config import Config

MAX_IMAGEN = 8 * 1024 * 1024
_BUSQUEDAS = {"buscar", "boe", "boe_sumario", "ine_operaciones", "ine_tablas", "ine_datos", "factcheck", "wayback",
              "dominio", "buscar_imagen"}


@dataclass
class Servicios:
    """Funciones del núcleo que usan las herramientas (se pueden sustituir, por ejemplo en pruebas)."""

    capturar: Callable = nucleo.capturar
    leer: Callable = nucleo.leer
    buscar: Callable = nucleo.buscar
    boe: Callable = nucleo.boe
    boe_sumario: Callable = nucleo.boe_sumario
    ine_operaciones: Callable = nucleo.ine_operaciones
    ine_tablas: Callable = nucleo.ine_tablas
    ine_datos: Callable = nucleo.ine_datos
    wayback: Callable = nucleo.wayback
    dominio: Callable = nucleo.dominio
    factcheck: Callable = nucleo.factcheck
    buscar_imagen: Callable = nucleo.buscar_imagen
    analizar_media: Callable = nucleo.analizar_media


@dataclass
class Contexto:
    """Dependencias de cada ejecución de un papel."""

    caso: Path
    config: Config
    servicios: Servicios = field(default_factory=Servicios)
    papel: str = ""
    prefijo: Optional[str] = None
    ids_previos: set = field(default_factory=set)
    llamadas: list = field(default_factory=list)
    urls_fallidas: int = 0


def _resumen(resultado: Any) -> str:
    if isinstance(resultado, dict):
        if "error" in resultado:
            return f"error: {resultado['error']}"
        for clave in ("resultados", "operaciones", "tablas", "series", "verificaciones"):
            if isinstance(resultado.get(clave), list):
                return f"{len(resultado[clave])} resultados"
        if resultado.get("primera_copia") or resultado.get("copia_mas_reciente"):
            return "hay copias archivadas"
    return "consultado"


def _llamar(ctx: RunContext[Contexto], herramienta: str, consulta: dict, fn: Callable, /, *pos, **kw) -> dict:
    try:
        res = fn(*pos, **kw)
    except (HttpError, ValueError, FileNotFoundError, OSError, KeyError) as e:
        res = {"error": f"{type(e).__name__}: {e}"}
    if herramienta in _BUSQUEDAS:
        ctx.deps.llamadas.append({"herramienta": herramienta, "consulta": consulta, "resultado": _resumen(res)})
    return res


def _dentro_del_caso(ctx: RunContext[Contexto], archivo: str) -> Path:
    ruta = Path(archivo)
    if not ruta.is_absolute():
        ruta = ctx.deps.caso / ruta
    ruta = ruta.resolve()
    if ctx.deps.caso.resolve() not in ruta.parents:
        raise ValueError("solo se pueden abrir archivos de la carpeta del caso")
    if not ruta.is_file():
        raise FileNotFoundError(f"no existe {archivo}")
    return ruta


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------


def leer(ctx: RunContext[Contexto], url: str, desde: int = 0) -> dict:
    """Abre una página o documento, guarda su texto en el caso y devuelve un trozo.

    Es obligatorio abrir con esta herramienta toda página que se cite en una evidencia: la cita literal
    se comprueba contra el texto guardado. Para leer más de un documento largo, vuelve a llamarla con
    ``desde`` igual al valor de ``siguiente``.
    """
    maximo = ctx.deps.config.max_texto_herramienta
    reg = RegistroPaginas(ctx.deps.caso)
    previos = [(e, t) for e, t in reg.textos_de(url) if e.get("origen") in {"leer", "manual"}]
    if previos and desde > 0:
        entrada, texto = previos[0]
        res = {"url": url, "titulo": entrada.get("titulo"), "caracteres": len(texto)}
    else:
        res = _llamar(ctx, "leer", {"url": url}, ctx.deps.servicios.leer, url, ctx.deps.caso, max_texto=0)
        if "error" in res:
            ctx.deps.urls_fallidas += 1
            if ctx.deps.urls_fallidas >= 3:
                res["aviso"] = (f"Ya van {ctx.deps.urls_fallidas} URL que no existen o no se pueden abrir: no adivines "
                                "URL. Usa las URL que te den `buscar` y las demás herramientas o los datos del caso, o "
                                "declara la laguna y entrega la salida.")
            return res
        if "texto" not in res:
            return res
        texto = res.pop("texto")
        res.pop("archivo", None)
    trozo = texto[desde:desde + maximo]
    res.update({"desde": desde, "texto": trozo,
                "siguiente": desde + maximo if desde + maximo < len(texto) else None})
    return res


def buscar(ctx: RunContext[Contexto], consulta: str, dominios: Optional[list[str]] = None) -> dict:
    """Busca en la web (los extractos no son evidencia: abre con `leer` lo que vayas a citar).

    ``dominios`` restringe la búsqueda, por ejemplo ``["boe.es"]`` o los dominios de los verificadores.
    """
    cfg = ctx.deps.config
    return _llamar(ctx, "buscar", {"consulta": consulta, "dominios": dominios}, ctx.deps.servicios.buscar,
                   consulta, dominios or [], 8, cfg.buscador_local(), cfg.idioma, caso=ctx.deps.caso)


_CAMPOS_BOE = ("identificador", "titulo", "rango", "fecha_publicacion", "vigencia_agotada", "url")


def boe(ctx: RunContext[Contexto], texto: str, desde: Optional[str] = None, hasta: Optional[str] = None) -> dict:
    """Busca en el título de la legislación consolidada del BOE. Fechas en formato AAAAMMDD."""
    res = _llamar(ctx, "boe", {"texto": texto, "desde": desde, "hasta": hasta}, ctx.deps.servicios.boe,
                  texto, desde, hasta, 10, caso=ctx.deps.caso)
    if isinstance(res.get("resultados"), list):  # menos campos: cada consulta ocupa menos contexto del modelo
        res["resultados"] = [{k: r.get(k) for k in _CAMPOS_BOE if r.get(k) is not None} if isinstance(r, dict) else r
                             for r in res["resultados"]]
    return res


def boe_sumario(ctx: RunContext[Contexto], fecha: str, texto: Optional[str] = None) -> dict:
    """Disposiciones publicadas en el BOE un día (AAAAMMDD), filtradas por palabras del título."""
    return _llamar(ctx, "boe_sumario", {"fecha": fecha, "texto": texto}, ctx.deps.servicios.boe_sumario,
                   fecha, texto, 20, caso=ctx.deps.caso)


def ine_operaciones(ctx: RunContext[Contexto], texto: str) -> dict:
    """Operaciones estadísticas del INE cuyo nombre contiene las palabras dadas (p. ej. «paro», «IPC»)."""
    return _llamar(ctx, "ine_operaciones", {"texto": texto}, ctx.deps.servicios.ine_operaciones, texto, 25)


def ine_tablas(ctx: RunContext[Contexto], operacion: str, texto: Optional[str] = None) -> dict:
    """Tablas de una operación del INE (código de ine_operaciones), filtradas por nombre."""
    return _llamar(ctx, "ine_tablas", {"operacion": operacion, "texto": texto}, ctx.deps.servicios.ine_tablas,
                   operacion, texto, 25)


def ine_datos(ctx: RunContext[Contexto], tabla: str, nult: int = 5, texto: Optional[str] = None) -> dict:
    """Últimos periodos de una tabla del INE. Cada dato queda registrado como «serie | periodo | valor»,
    que es la cita literal que hay que usar en la evidencia (con la URL de la tabla)."""
    return _llamar(ctx, "ine_datos", {"tabla": tabla, "nult": nult, "texto": texto}, ctx.deps.servicios.ine_datos,
                   tabla, nult, texto, 25, caso=ctx.deps.caso)


def wayback(ctx: RunContext[Contexto], url: str, guardar: bool = False) -> dict:
    """Copias de una URL en la Wayback Machine. ``guardar`` solo tiene efecto si el caso pide archivar."""
    guardar = guardar and ctx.deps.config.archivar
    return _llamar(ctx, "wayback", {"url": url}, ctx.deps.servicios.wayback, url, guardar, caso=ctx.deps.caso)


def dominio(ctx: RunContext[Contexto], objetivo: str) -> dict:
    """Datos de registro de un dominio o de la web de una URL (fecha de alta, registrador)."""
    return _llamar(ctx, "dominio", {"objetivo": objetivo}, ctx.deps.servicios.dominio, objetivo, caso=ctx.deps.caso)


def factcheck(ctx: RunContext[Contexto], texto: str) -> dict:
    """Verificaciones previas publicadas (ClaimReview de Google Fact Check Tools, si hay clave)."""
    return _llamar(ctx, "factcheck", {"texto": texto}, ctx.deps.servicios.factcheck, texto, ctx.deps.config.idioma,
                   10, caso=ctx.deps.caso)


def buscar_imagen(ctx: RunContext[Contexto], url: str) -> dict:
    """Búsqueda inversa de una imagen por su URL pública (coincidencias con SerpAPI, si hay clave)."""
    return _llamar(ctx, "buscar_imagen", {"url": url}, ctx.deps.servicios.buscar_imagen, url, 15)


def media(ctx: RunContext[Contexto], archivo: str) -> dict:
    """Análisis técnico de un archivo del caso: metadatos, marcas de IA y C2PA, ELA, fotogramas, audio."""
    try:
        ruta = _dentro_del_caso(ctx, archivo)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    return _llamar(ctx, "media", {"archivo": archivo}, ctx.deps.servicios.analizar_media, ruta)


def ver_imagen(ctx: RunContext[Contexto], archivo: str) -> Any:
    """Muestra una imagen del caso (un fotograma, la hoja de contactos, el ELA…) para examinarla."""
    if not ctx.deps.config.vision:
        return {"error": "este modelo trabaja sin imágenes"}
    try:
        ruta = _dentro_del_caso(ctx, archivo)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    tipo = mimetypes.guess_type(ruta.name)[0] or ""
    if not tipo.startswith("image/") or ruta.stat().st_size > MAX_IMAGEN:
        return {"error": "solo imágenes de menos de 8 MB"}
    return BinaryContent(ruta.read_bytes(), media_type=tipo)


def capturar(ctx: RunContext[Contexto], url: str, nombre: str) -> dict:
    """Captura secundaria (p. ej. un tuit incrustado o el original encontrado), guardada como <nombre>.json."""
    res = _llamar(ctx, "capturar", {"url": url}, ctx.deps.servicios.capturar, url, ctx.deps.caso,
                  archivar=ctx.deps.config.archivar, nombre=nombre)
    return nucleo.resumen_captura(res, 3000) if "error" not in res else res


TODAS = {f.__name__: f for f in (leer, buscar, boe, boe_sumario, ine_operaciones, ine_tablas, ine_datos, wayback,
                                 dominio, factcheck, buscar_imagen, media, ver_imagen, capturar)}

#: Herramientas de cada papel (la metodología de cada agente cita estas capacidades).
POR_PAPEL = {
    "captura": ("leer", "capturar", "wayback", "ver_imagen"),
    "desglose": (),
    "verificador": ("buscar", "leer", "boe", "boe_sumario", "ine_operaciones", "ine_tablas", "ine_datos", "wayback",
                    "factcheck"),
    "multimedia": ("buscar", "leer", "buscar_imagen", "wayback", "media", "ver_imagen"),
    "origen": ("buscar", "leer", "factcheck", "wayback", "dominio"),
    "redactor": (),
    "auditor": ("leer", "buscar"),
}


def nombres_para(papel: str, config: Config) -> list:
    """Herramientas de un papel según la configuración (sin `buscar` si no hay buscador propio)."""
    nombres = list(POR_PAPEL[papel])
    if "buscar" in nombres and config.buscador_local() is None:
        nombres.remove("buscar")
    if not config.vision and "ver_imagen" in nombres:
        nombres.remove("ver_imagen")
    return nombres


def toolset(papel: Optional[str] = None, config: Optional[Config] = None) -> FunctionToolset:
    """Herramientas de un papel (o todas) para usarlas también en agentes propios con ``Contexto``."""
    if papel is None:
        return FunctionToolset(list(TODAS.values()))
    return FunctionToolset([TODAS[n] for n in nombres_para(papel, config or Config())])
