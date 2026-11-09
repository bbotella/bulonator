"""``resultado.json``: el resumen del caso que pueden leer otros programas.

Se monta a partir de ``informe.md``, ``publicacion.md``, ``02-afirmaciones.md``, ``captura.json`` y
``evidencias/``, más los datos del veredicto. Así el plugin de Claude Code y el motor producen el
mismo archivo con el mismo procedimiento. ``comprobar_resultado`` valida su estructura.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

from .caso import normalizar_url
from .documentos import (afirmacion_central, apartados_del_informe, cabecera_del_informe, fuentes_del_informe,
                         leer_evidencias, lista, publicaciones, seccion, sin_comentarios)
from .reglas import calificaciones, reglas
from .util import VERSION

VERSION_RESULTADO = 1


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8") if ruta.is_file() else ""


def _entrada(caso: Path) -> dict:
    archivo = caso / "captura.json"
    if not archivo.is_file():
        return {"valor": None, "tipo": None, "plataforma": None, "copia_archivada": None}
    cap = json.loads(archivo.read_text(encoding="utf-8"))
    plataforma = cap.get("plataforma")
    tipo = {"texto": "texto", "archivo_local": "archivo"}.get(plataforma, "url")
    web = cap.get("archivo_web") or {}
    copia = ((web.get("nueva_copia") or {}).get("url") or (web.get("primera_copia") or {}).get("url")
             or (web.get("copia_mas_reciente") or {}).get("url"))
    return {"valor": cap.get("entrada"), "tipo": tipo, "plataforma": plataforma, "copia_archivada": copia}


def construir_resultado(caso, calificacion: str, confianza: str, dictamen: str, rondas: int,
                        subtipo: Optional[str] = None, idioma: str = "es", generado_por: str = "claude-code",
                        modelos: Optional[dict] = None, cierre: bool = False) -> dict:
    """Monta el diccionario de ``resultado.json`` a partir de los documentos del caso.

    ``cierre`` indica que tras la última ronda no hubo PALANTE y se aplicó la regla de cierre de
    ``flujo.md``. El caso cuenta como aprobado por la auditoría si el último dictamen no es un VETO y no
    hubo cierre (un CAMBIOS que no toca la calificación ni las cifras se aplica y se cierra el caso).
    """
    caso = Path(caso).expanduser().resolve()
    informe = _leer(caso / "informe.md")
    cabecera = cabecera_del_informe(informe)
    evidencias = leer_evidencias(caso)

    def evidencias_de(url: Optional[str]) -> list:
        if not url:
            return []
        clave = normalizar_url(url)
        return sorted({e.id for e in evidencias
                       if clave in {normalizar_url(e.url or ""), normalizar_url(e.copia or "")}})

    fuentes = [{"n": f.n, "referencia": f.referencia, "url": f.url, "copia": f.copia, "tipo": f.tipo,
                "evidencias": evidencias_de(f.url) or evidencias_de(f.copia)}
               for f in fuentes_del_informe(informe)]
    afirmaciones = [{"id": a.id, "texto": a.texto, "calificacion": a.calificacion, "valoracion": a.valoracion,
                     "evidencias": a.evidencias} for a in apartados_del_informe(informe, "A")]
    multimedia = [{"id": m.id, "descripcion": m.texto, "veredicto": m.valoracion, "evidencias": m.evidencias}
                  for m in apartados_del_informe(informe, "M")]
    resumen = sin_comentarios(seccion(informe, "En resumen") or "").strip()
    replica = sin_comentarios(seccion(informe, "Derecho de réplica") or "").strip() or None
    return {
        "version": VERSION_RESULTADO,
        "bulonator": VERSION,
        "caso": caso.name,
        "fecha": dt.date.today().isoformat(),
        "generado_por": generado_por,
        "idioma": idioma,
        "entrada": _entrada(caso),
        "calificacion": calificacion,
        "subtipo": subtipo,
        "confianza": confianza,
        "titular": cabecera.get("titular"),
        "resumen": resumen,
        "afirmacion_central": afirmacion_central(_leer(caso / "02-afirmaciones.md")),
        "afirmaciones": afirmaciones,
        "multimedia": multimedia,
        "fuentes": fuentes,
        "publicaciones": publicaciones(_leer(caso / "publicacion.md")),
        "limitaciones": lista(sin_comentarios(seccion(informe, "Lo que no hemos podido comprobar") or "")),
        "replica": replica,
        "auditoria": {"rondas": rondas, "dictamen": dictamen, "cierre": cierre,
                      "aprobado": dictamen != "VETO" and not cierre},
        "modelos": modelos or {},
        "archivos": {"informe": "informe.md", "publicacion": "publicacion.md", "evidencias": "evidencias/"},
    }


def escribir_resultado(caso, **datos) -> dict:
    res = construir_resultado(caso, **datos)
    destino = Path(caso).expanduser().resolve() / "resultado.json"
    destino.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return res


# ---------------------------------------------------------------------------
# Comprobación de la estructura
# ---------------------------------------------------------------------------

_OBLIGATORIOS = {
    "version": int, "bulonator": str, "caso": str, "fecha": str, "generado_por": str, "idioma": str,
    "entrada": dict, "calificacion": str, "confianza": str, "titular": str, "resumen": str,
    "afirmaciones": list, "multimedia": list, "fuentes": list, "publicaciones": dict, "limitaciones": list,
    "auditoria": dict,
}


def comprobar_resultado(res: dict) -> list:
    """Errores de estructura y de coherencia con ``reglas.json`` (lista vacía si es correcto)."""
    errores = []
    for clave, tipo in _OBLIGATORIOS.items():
        if clave not in res:
            errores.append(f"falta el campo «{clave}»")
        elif not isinstance(res[clave], tipo):
            errores.append(f"«{clave}» debe ser {tipo.__name__}")
    if errores:
        return errores
    r = reglas()
    if res["version"] != VERSION_RESULTADO:
        errores.append(f"versión de resultado desconocida: {res['version']}")
    cal = calificaciones().get(res["calificacion"])
    if cal is None:
        errores.append(f"calificación desconocida: {res['calificacion']}")
    else:
        if res["confianza"] not in cal["confianzas"]:
            errores.append(f"la confianza {res['confianza']} no está permitida con {res['calificacion']}")
        if res.get("subtipo") and res["subtipo"] not in cal["subtipos"]:
            errores.append(f"subtipo «{res['subtipo']}» no válido para {res['calificacion']}")
    if res["confianza"] not in r["confianzas"]:
        errores.append(f"confianza desconocida: {res['confianza']}")
    aud = res["auditoria"]
    if aud.get("dictamen") not in r["auditoria"]["dictamenes"]:
        errores.append(f"dictamen desconocido: {aud.get('dictamen')}")
    if not isinstance(aud.get("rondas"), int) or not 1 <= aud["rondas"] <= r["auditoria"]["rondas_max"]:
        errores.append(f"número de rondas de auditoría no válido: {aud.get('rondas')}")
    desconocidas = set(res["publicaciones"]) - set(r["publicaciones"])
    if desconocidas:
        errores.append(f"publicaciones desconocidas: {', '.join(sorted(desconocidas))}")
    for k, conf in r["publicaciones"].items():
        if k not in res["publicaciones"] and not conf.get("opcional"):
            errores.append(f"falta la publicación «{k}»")
    for a in res["afirmaciones"]:
        if a.get("calificacion") and a["calificacion"] not in calificaciones():
            errores.append(f"{a.get('id')}: calificación desconocida {a['calificacion']}")
    return errores
