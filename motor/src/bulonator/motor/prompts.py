"""Instrucciones de cada papel, construidas con la metodología del repositorio (sin copias propias).

- Los papeles con agente (captura, verificador, multimedia, origen, auditor) usan las secciones
  compartidas de ``agents/bulonator-<papel>.md`` (se descartan «Lo que recibes…» y «Salida», que son
  de Claude Code) y las referencias de su sección «Referencias».
- El desglose y la redacción usan sus secciones de ``references/flujo.md``.
- A todos se añaden los archivos que definen las reglas que citan (``[CAL-9]`` → ``calificaciones.md``)
  y ``reglas.json``.

Lo único propio del motor es el contrato de entrada y salida (qué recibe, qué devuelve y cómo se
valida), que no es metodología.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from ..nucleo.datos import metodologia, referencias_de_agente, seccion_de_referencia, texto_compartido_de_agente
from .config import Config
from .herramientas import POR_PAPEL, TODAS, nombres_para

PREFIJO_ARCHIVO = {"MET": "metodologia.md", "CAL": "calificaciones.md", "EV": "formato-evidencias.md",
                   "RED": "redaccion.md", "PROP": "analisis-propagacion.md", "MM": "tecnicas-multimedia.md",
                   "FUE": "fuentes-oficiales.md", "VER": "verificadores.md", "FLU": "flujo.md"}
_ID_RE = re.compile(r"\[(%s)-\d+\]" % "|".join(PREFIJO_ARCHIVO))
_ARCHIVO_RE = re.compile(r"`((?:templates/)?[\w.-]+\.(?:md|json))`")
_SECCIONES_FLUJO = {"desglose": ("Desglose",), "redactor": ("Deliberación y redacción", "Auditoría y cierre")}
_PLANTILLAS = {"desglose": ("afirmaciones.md",), "redactor": ("informe.md", "publicacion.md")}
_NO_INCLUIR = {"herramientas-claude.md"}

_FUNCION = {
    "captura": "Haces la ficha del contenido ya capturado (el motor ha ejecutado la captura): qué es, quién lo "
               "publica, qué dice literalmente y qué multimedia lleva, con sus evidencias E-C-….",
    "desglose": "Desglosas el contenido en afirmaciones verificables y elementos multimedia, y repartes los encargos.",
    "verificador": "Verificas las afirmaciones que se te encargan contra fuentes oficiales y primarias.",
    "multimedia": "Analizas un elemento multimedia del caso. Las imágenes del análisis técnico van adjuntas.",
    "origen": "Rastreas el origen y la difusión del contenido y buscas verificaciones previas.",
    "redactor": "Deliberas el veredicto y redactas el informe y los textos para redes a partir de las evidencias.",
    "auditor": "Auditas el informe y los textos antes de entregarlos, con derecho a veto.",
}


def _referencias(papel: str, texto: str) -> list:
    archivos = []
    if papel in _SECCIONES_FLUJO:
        archivos += [a for a in _ARCHIVO_RE.findall(texto) if not a.startswith("templates/")]
    else:
        archivos += referencias_de_agente(f"bulonator-{papel}")
    archivos += [PREFIJO_ARCHIVO[p] for p in _ID_RE.findall(texto)]
    archivos.append("reglas.json")
    vistos = []
    for a in archivos:
        if a not in vistos and a not in _NO_INCLUIR and (metodologia().referencias / a).is_file():
            vistos.append(a)
    # Solo un nivel: las referencias citan reglas de otras, pero incluirlas todas daría a cada papel la
    # metodología entera (demasiado para modelos locales). Igual que en Claude Code, cada papel lee lo suyo.
    return vistos


def texto_del_papel(papel: str) -> str:
    """La metodología propia del papel (sin referencias)."""
    if papel in _SECCIONES_FLUJO:
        return "\n\n".join(f"## {s}\n\n{seccion_de_referencia('flujo.md', s)}" for s in _SECCIONES_FLUJO[papel])
    return texto_compartido_de_agente(f"bulonator-{papel}")


def _hoja_de_herramientas(papel: str, config: Config, busqueda_nativa: bool) -> str:
    nombres = nombres_para(papel, config)
    if not nombres and not busqueda_nativa:
        return "En este papel no tienes herramientas: trabajas con lo que se te da."
    lineas = [f"- `{n}`: {(TODAS[n].__doc__ or '').strip().splitlines()[0]}" for n in nombres]
    if busqueda_nativa:
        lineas.append("- `buscar`: usa tu herramienta de búsqueda web nativa. Los extractos no son evidencia.")
    elif "buscar" in POR_PAPEL[papel] and "buscar" not in nombres:
        lineas.append("- `buscar`: no hay buscador configurado; anota en las lagunas las búsquedas que no has podido hacer.")
    if papel in ("verificador", "multimedia", "origen", "captura"):
        lineas.append("- `navegador`: no está disponible en el motor; si una fuente lo necesita, anótalo como laguna.")
    return "\n".join(lineas)


def instrucciones(papel: str, config: Config, busqueda_nativa: bool = False) -> str:
    """Instrucciones completas de un papel: contrato del motor, metodología, herramientas y referencias."""
    m = metodologia()
    texto = texto_del_papel(papel)
    partes = [
        "# Bulonator: " + papel,
        _FUNCION[papel],
        "## Cómo trabajas en el motor\n\n"
        "- Recibes los datos del caso en el mensaje. No escribes archivos: devuelves una salida estructurada con "
        "los campos que se te piden; el motor la convierte en los documentos del caso.\n"
        "- Tu salida se valida automáticamente con las reglas de la metodología. Si no las cumple, se te devuelve "
        "con los problemas para que la corrijas.\n"
        "- Las evidencias solo pueden citar páginas abiertas con `leer` (o registradas por otras herramientas), y su "
        "cita literal tiene que estar en el texto guardado: cópiala, no la reformules.\n"
        f"- Fecha de hoy: {dt.date.today().isoformat()}. Idioma de los textos para redes: {config.idioma}.",
        "## Herramientas\n\n" + _hoja_de_herramientas(papel, config, busqueda_nativa),
        "# Metodología del papel\n\n" + texto,
    ]
    for nombre in _PLANTILLAS.get(papel, ()):
        partes.append(f"# Plantilla: templates/{nombre}\n\n" + m.plantilla(nombre).read_text(encoding="utf-8"))
    for archivo in _referencias(papel, texto):
        contenido = m.referencia(archivo).read_text(encoding="utf-8")
        if archivo.endswith(".json"):  # compacto: ahorra tokens
            contenido = json.dumps(json.loads(contenido), ensure_ascii=False, separators=(",", ":"))
        partes.append(f"# Referencia: {archivo}\n\n" + contenido)
    return "\n\n".join(partes)
