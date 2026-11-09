"""Escritura de los documentos del caso a partir de las salidas estructuradas.

Los formatos son los de ``formato-evidencias.md`` y las plantillas: así ``validar`` y ``resultado``
(los mismos del plugin) leen los casos del motor sin diferencias.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Optional

from .. import __version__
from ..nucleo.datos import metodologia
from ..nucleo.reglas import calificaciones, reglas
from ..nucleo.texto import contar
from .esquemas import Desglose, Evidencia, Ficha, InformeAgente, Redaccion


def _linea(texto: Optional[str]) -> str:
    return re.sub(r"\s*\n\s*", " ", (texto or "").strip()) or "—"


def _cita(texto: str) -> str:
    t = _linea(texto)
    if re.search(r"«[^»]+»|“[^”]+”|\"[^\"]+\"", t):
        return t
    return f"«{t}»"


def evidencia_md(ev: Evidencia, consultada: str) -> str:
    filas = [
        ("Afirmación", ev.afirmacion), ("Fuente", ev.fuente), ("URL", ev.url or "—"), ("Tipo", ev.tipo),
        ("Fecha del documento", ev.fecha_documento), ("Consultada", consultada), ("Cita literal", _cita(ev.cita_literal)),
        ("Ubicación", ev.ubicacion), ("Qué demuestra", ev.que_demuestra), ("Qué NO demuestra", ev.que_no_demuestra),
    ]
    if ev.copia_archivada:
        filas.append(("Copia archivada", ev.copia_archivada))
    return f"### {ev.id}\n" + "\n".join(f"- **{k}:** {_linea(v)}" for k, v in filas) + "\n"


def tabla_busquedas(llamadas: list, extra: list) -> str:
    filas = [(str(ll.get("consulta")), ll["herramienta"], ll["resultado"]) for ll in llamadas]
    filas += [(b.consulta, b.herramienta, b.resultado) for b in extra]
    if not filas:
        filas = [("—", "—", "no se hicieron búsquedas")]
    cuerpo = "\n".join(f"| {_linea(a).replace('|', '/')} | {b} | {_linea(c).replace('|', '/')} |" for a, b, c in filas)
    return "| Consulta / fuente | Herramienta | Resultado |\n|---|---|---|\n" + cuerpo


def informe_agente_md(titulo: str, inf: InformeAgente, llamadas: list, consultada: str) -> str:
    cal = inf.calificacion + (f" ({inf.subtipo})" if inf.subtipo else "")
    partes = [f"# Evidencias: {titulo}", "## Afirmación / elemento analizado", _linea(inf.elemento),
              "## Conclusión propuesta",
              f"- **Calificación propuesta:** {cal}\n- **Confianza:** {inf.confianza}\n"
              + (f"- **Veredicto multimedia:** {inf.veredicto_multimedia}\n" if inf.veredicto_multimedia else "")
              + f"- **Razonamiento:** {_linea(inf.razonamiento)}",
              "## Registro de evidencias", "\n".join(evidencia_md(e, consultada) for e in inf.evidencias) or "—",
              "## Búsquedas realizadas", tabla_busquedas(llamadas, inf.busquedas),
              "## Lagunas y limitaciones", "\n".join(f"- {_linea(x)}" for x in inf.lagunas) or "- Ninguna declarada."]
    return "\n\n".join(partes) + "\n"


def ficha_md(f: Ficha, consultada: str) -> str:
    partes = ["# Ficha del contenido capturado", "## Resumen", _linea(f.resumen),
              "## Datos",
              f"- **Plataforma:** {f.plataforma}\n- **Autor:** {f.autor}"
              f"{' (figura pública)' if f.autor_es_publico else ''}\n- **Fecha de publicación:** {f.fecha_publicacion or '—'}",
              "## Texto literal", "```text\n" + f.texto_literal.strip() + "\n```",
              "## Multimedia",
              "\n".join(f"- {m.archivo or m.url or '—'}: {_linea(m.descripcion)}"
                        + (f" (se dice que muestra: {_linea(m.que_se_dice_que_muestra)})" if m.que_se_dice_que_muestra else "")
                        for m in f.multimedia) or "- Ninguna.",
              "## Contenido incrustado", "\n".join(f"- {_linea(x)}" for x in f.contenido_incrustado) or "- Ninguno.",
              "## Señales", "\n".join(f"- {_linea(x)}" for x in f.senales) or "- Ninguna.",
              "## Registro de evidencias", "\n".join(evidencia_md(e, consultada) for e in f.evidencias) or "—",
              "## Limitaciones", "\n".join(f"- {_linea(x)}" for x in f.limitaciones) or "- Ninguna."]
    return "\n\n".join(partes) + "\n"


def desglose_md(d: Desglose, caso: str, entrada: str, copia: Optional[str]) -> str:
    central = next((a for a in d.afirmaciones if a.id == d.afirmacion_central), None)
    filas = "\n".join(f"| {a.id} | {_linea(a.texto)} | {a.tipo} | {_linea(a.quien_tendria_el_dato)} | {a.prioridad} |"
                      for a in d.afirmaciones) or "| — | — | — | — | — |"
    multimedia = "\n".join(f"| {m.id} | {m.archivo or m.url or '—'} | {_linea(m.que_se_dice_que_muestra)} | "
                           f"{_linea(m.que_comprobar)} |" for m in d.multimedia) or "| — | — | — | — |"
    encargos = "\n".join(f"- `bulonator-{e.papel}` → {', '.join(e.ids)}" for e in d.encargos) or "- —"
    partes = [f"# Desglose del caso: {caso}",
              f"## Contenido analizado\n- **Entrada:** {entrada}\n- **Copia archivada:** {copia or 'no disponible'}",
              "## Cómo se está entendiendo", _linea(d.como_se_entiende),
              "## Afirmación central",
              f"**{central.id}**: {_linea(central.texto)}" if central else "No hay afirmaciones verificables (opinión).",
              "## Afirmaciones verificables",
              "| ID | Afirmación (comprobable) | Tipo | ¿Quién tendría el dato? | Prioridad |\n|---|---|---|---|---|\n" + filas,
              "## Elementos multimedia",
              "| ID | Archivo | Qué se dice que muestra | Qué hay que comprobar |\n|---|---|---|---|\n" + multimedia,
              "## No verificable (opiniones y predicciones)",
              "\n".join(f"- {_linea(x)}" for x in d.no_verificable) or "- Nada.",
              f"## Viralidad y peligrosidad\n- **Viralidad:** {_linea(d.viralidad)}\n- **Peligrosidad:** {_linea(d.peligrosidad)}",
              "## Encargos de investigación", encargos]
    return "\n\n".join(partes) + "\n"


def _fecha_es(d: dt.date) -> str:
    return d.strftime("%d/%m/%Y")


def informe_md(r: Redaccion, caso: str, copia: Optional[str], modelos: str, rondas: str,
               herramientas: list, hoy: Optional[dt.date] = None) -> str:
    hoy = hoy or dt.date.today()
    etiqueta = calificaciones()[r.calificacion]["etiqueta"]
    cal = r.calificacion + (f" ({r.subtipo})" if r.subtipo else "")
    que_circula = [f"- {_linea(x)}" for x in r.que_circula]
    que_circula.append(f"- **Copia archivada:** {copia or 'no disponible'} (no enlazamos el original para no amplificarlo).")
    if r.afirmacion_central_cita:
        que_circula.append(f"- **Afirmación central:** «{_linea(r.afirmacion_central_cita).strip('«»')}»")
    apartados = []
    for a in r.apartados:
        bloque = f"### {a.id}: {_linea(a.titulo)} → {_linea(a.valoracion)}\n\n{a.explicacion.strip()}"
        if a.evidencias:
            bloque += f"\n<!-- Evidencias: {', '.join(a.evidencias)} -->"
        apartados.append(bloque)
    if r.origen_y_difusion:
        apartados.append("### Origen y difusión\n\n" + r.origen_y_difusion.strip())
    fuentes = []
    for f in r.fuentes:
        consultado = f"consultado el {hoy.isoformat()}; copia: {f.copia or '—'}"
        fecha = f", {f.fecha}" if f.fecha else ""
        fuentes.append(f"[{f.n}] {_linea(f.autor)}, «{_linea(f.titulo)}»{fecha}. {f.url} ({consultado}). {f.tipo}.")
    partes = [
        f"# {etiqueta}: {_linea(r.titular)}",
        f"> **Caso:** {caso} · **Verificado el:** {_fecha_es(hoy)} · **Calificación:** {cal} · **Confianza:** {r.confianza}\n"
        f"> **Metodología:** Bulonator {__version__}, inspirada en Maldita.es y en el código de la IFCN. "
        f"Verificación asistida por IA y auditada por un agente editor.",
        "## En resumen", r.resumen.strip(),
        "## Qué circula", "\n".join(que_circula),
        "## Qué hemos comprobado", "\n\n".join(apartados) or "No hay afirmaciones verificables.",
        f"## Por qué lo calificamos como {r.calificacion}", r.por_que.strip(),
        "## Lo que no hemos podido comprobar", "\n".join(f"- {_linea(x)}" for x in r.limitaciones) or "- Nada relevante.",
        "## Derecho de réplica", r.replica.strip() or "No procede.",
        "## Fuentes", "\n".join(fuentes),
        "## Metodología y transparencia",
        "- **Proceso:** captura y preservación → desglose en afirmaciones → verificación con fuentes oficiales y "
        f"primarias → análisis multimedia → rastreo del origen y la difusión → auditoría editorial ({rondas}).\n"
        f"- **Herramientas:** {', '.join(herramientas) or '—'}.\n"
        f"- **Asistencia de IA:** este informe lo ha elaborado el motor de Bulonator con modelos de lenguaje ({modelos}). "
        "Una persona debe revisarlo antes de publicarlo. Los errores se corrigen de forma visible.\n"
        "- **Calificaciones:** FALSO, ALERTA, CONTEXTO y VERDADERO siguen las definiciones públicas de Maldita.es "
        "(<https://maldita.es/metodologia-maldita/>). Bulonator no está afiliado a Maldita.es.",
    ]
    return "\n\n".join(partes) + "\n"


def _titulos_de_publicacion() -> dict:
    """Encabezados de ``templates/publicacion.md`` por clave de ``reglas.json`` → ``publicaciones``."""
    plantilla = metodologia().plantilla("publicacion.md").read_text(encoding="utf-8")
    titulos = re.findall(r"^## (.+)$", plantilla, re.M)
    salida = {}
    for clave, conf in reglas()["publicaciones"].items():
        for t in titulos:
            if re.sub(r"^\d+\.\s*", "", t).lower().startswith(conf["titulo"].lower()):
                salida[clave] = t
    return salida


def publicacion_md(r: Redaccion, caso: str, hoy: Optional[dt.date] = None) -> str:
    hoy = hoy or dt.date.today()
    etiqueta = calificaciones()[r.calificacion]["etiqueta"]
    titulos = _titulos_de_publicacion()
    p = r.publicaciones
    bloques = {"breve": [p.breve], "hilo_x": p.hilo_x, "largo": [p.largo] if p.largo else [],
               "mensajeria": [p.mensajeria], "texto_alternativo": [p.texto_alternativo] if p.texto_alternativo else []}
    partes = [f"# Textos para compartir: {caso}",
              f"> Calificación: {etiqueta} · Confianza: {r.confianza} · Verificado el {_fecha_es(hoy)}\n"
              "> Cada dato de estos textos procede de `informe.md`, donde tiene su fuente [n] y su evidencia E-…."]
    for clave, titulo in titulos.items():
        if bloques.get(clave):
            partes.append(f"## {titulo}\n\n" + "\n\n".join(f"```text\n{b.strip()}\n```" for b in bloques[clave]))
    cuerpo = "\n\n".join(partes) + "\n"
    medidas = contar(cuerpo, por_bloques=True)["bloques"]
    tabla = "\n".join(f"| {m['bloque']} | {m['x_ponderado']} | {m['caracteres']} | {', '.join(m['cabe_en']) or '—'} |"
                      for m in medidas)
    return cuerpo + "\n## Control de calidad\n\n| Bloque | Ponderado X | Caracteres | ¿Cabe? |\n|---|---|---|---|\n" + tabla + "\n"


def auditoria_md(previo: str, ronda: int, dictamenes: list, enfoques: list) -> str:
    partes = [previo.rstrip() if previo.strip() else "# Auditoría"]
    for d, enfoque in zip(dictamenes, enfoques):
        sufijo = f" ({enfoque})" if enfoque else ""
        bloque = [f"## Ronda {ronda}{sufijo}", f"**Dictamen: {d.dictamen}**. {_linea(d.resumen)}"]
        if d.motivo_veto:
            bloque.append(f"**Motivo del veto:** {_linea(d.motivo_veto)}")
        if d.fuentes_reabiertas:
            bloque.append("### Fuentes reabiertas\n" + "\n".join(f"- {_linea(x)}" for x in d.fuentes_reabiertas))
        if d.trazabilidad:
            bloque.append("### Trazabilidad\n| Frase | [n] / E | Estado |\n|---|---|---|\n" + "\n".join(
                f"| {_linea(t.frase).replace('|', '/')} | {t.referencia} | {t.estado} |" for t in d.trazabilidad))
        if d.cambios_obligatorios:
            bloque.append("### Cambios obligatorios\n" + "\n".join(
                f"{i}. **{_linea(c.ubicacion)}:** {_linea(c.problema)} → {_linea(c.correccion)}"
                for i, c in enumerate(d.cambios_obligatorios, 1)))
        if d.recomendados:
            bloque.append("### Recomendados\n" + "\n".join(f"- {_linea(x)}" for x in d.recomendados))
        partes.append("\n\n".join(bloque))
    return "\n\n".join(partes) + "\n"


def escribir(ruta: Path, texto: str) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta
