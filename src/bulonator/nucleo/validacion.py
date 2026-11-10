"""``validar``: comprobaciones mecánicas de un caso antes de la auditoría y de la entrega.

Lo que hoy depende de la disciplina del modelo se comprueba aquí con código:

- cada evidencia tiene los campos obligatorios, un identificador válido y un tipo de fuente conocido;
- su URL se abrió en el caso (está en ``evidencias/paginas/``) y su cita literal aparece en el texto
  guardado;
- cada ``[n]`` del informe existe en la lista de fuentes y cada fuente procede de una evidencia;
- la calificación es la misma en el informe, los textos para redes y ``resultado.json``, y la
  confianza está permitida para esa calificación;
- los textos para X caben en el límite y no quedan marcadores de plantilla sin rellenar.

Devuelve ``{"ok": bool, "errores": [...], "avisos": [...], "resumen": {...}}``.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .caso import RegistroPaginas, busquedas, normalizar_url
from .documentos import (ID_EVIDENCIA_RE, URL_RE, apartados_del_informe, cabecera_del_informe, calificacion_en,
                         fuentes_del_informe,
                         id_valido, leer_evidencias, publicaciones, sin_comentarios)
from .reglas import calificaciones, plataformas, reglas
from .resultado import comprobar_resultado
from .texto import longitud

_CAMPOS_OBLIGATORIOS = ("Fuente", "URL", "Tipo", "Cita literal")
_SIN_URL = {"herramienta"}
#: Calificaciones que afirman algo sobre los hechos y, por tanto, necesitan fuentes citadas
_CON_FUENTES = {"FALSO", "VERDADERO", "CONTEXTO"}
_CORTE = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\(\s*(?:\.\.\.|…)\s*\)|…|\.\.\.")


# ---------------------------------------------------------------------------
# Comparación de citas
# ---------------------------------------------------------------------------


def _normalizar(texto: str, estricto: bool = True) -> str:
    t = unicodedata.normalize("NFKC", texto or "")
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)  # palabras partidas a final de línea (PDF)
    t = t.casefold()
    t = re.sub(r"[«»“”„\"'‘’`*_]", " ", t)
    t = re.sub(r"[‐‑‒–—―]", "-", t)
    if not estricto:
        t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def fragmentos(cita: str) -> list:
    """Trozos comprobables de una cita: se corta por las elipsis y se quitan las traducciones entre corchetes."""
    marcada = _CORTE.sub("␞", cita)
    marcada = re.sub(r"\[[^\]]*\]", " ", marcada)
    return [f.strip() for f in marcada.split("␞") if f.strip()]


def cita_en_texto(cita: str, texto: str, min_palabras: int = 3) -> str:
    """``exacta``, ``puntuacion`` (coincide salvo puntuación), ``no`` o ``corta`` (nada comprobable)."""
    trozos = [f for f in fragmentos(cita) if len(_normalizar(f, False).split()) >= min_palabras]
    if not trozos:
        return "corta"
    exacto, flojo = _normalizar(texto), _normalizar(texto, False)
    if all(_normalizar(f) in exacto for f in trozos):
        return "exacta"
    if all(_normalizar(f, False) in flojo for f in trozos):
        return "puntuacion"
    return "no"


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------


class _Informe:
    def __init__(self):
        self.errores: list = []
        self.avisos: list = []

    def error(self, codigo, archivo, detalle, ubicacion=None):
        self.errores.append({"codigo": codigo, "archivo": archivo, "ubicacion": ubicacion, "detalle": detalle})

    def aviso(self, codigo, archivo, detalle, ubicacion=None):
        self.avisos.append({"codigo": codigo, "archivo": archivo, "ubicacion": ubicacion, "detalle": detalle})


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8") if ruta.is_file() else ""


def problemas_de_evidencia(ev, reg: RegistroPaginas, capturas: list) -> list:
    """Problemas de una evidencia: lista de ``(nivel, código, detalle)`` con nivel ``error`` o ``aviso``.

    La usan ``validar`` (sobre los archivos del caso) y el motor (sobre la salida de cada agente,
    antes de aceptarla). Una cita comprobada aparece como ``("ok", "cita_comprobada", …)``.
    """
    tipos = set(reglas()["tipos_fuente"])
    conf_ev = reglas()["evidencias"]
    salida = []
    if not id_valido(ev.id):
        salida.append(("error", "id_invalido", f"identificador de evidencia no válido: {ev.id}"))
    tipo = ev.tipo
    es_captura = ev.id.startswith("E-C-")
    # Las herramientas no tienen URL ni cita; las evidencias de la captura de un texto o un archivo, tampoco URL
    faltan = [c for c in _CAMPOS_OBLIGATORIOS if not ev.campo(c).strip("—- ")
              and not (tipo in _SIN_URL and c in {"URL", "Cita literal"}) and not (es_captura and c == "URL")]
    if faltan:
        salida.append(("error", "campo_ausente", f"faltan campos: {', '.join(faltan)}"))
    if tipo and tipo not in tipos:
        salida.append(("error", "tipo_desconocido", f"tipo de fuente desconocido: {ev.campo('Tipo')}"))
    if tipo in _SIN_URL:
        return salida
    textos = reg.textos_de(ev.url) if ev.url else []
    if es_captura and not textos:
        textos = capturas
    if not ev.url and not es_captura:
        return salida + [("error", "url_ausente", "la evidencia no tiene una URL http(s)")]
    if ev.copia and not reg.de(ev.copia):
        salida.append(("error", "copia_no_registrada",
                       f"la copia archivada {ev.copia} no está registrada en el caso: búscala con wayback --caso "
                       "(o ábrela con leer) antes de citarla"))
    if not textos:
        return salida + [("error", "url_no_abierta",
                          f"{ev.url} no está registrada en el caso: ábrela con leer (o regístrala) antes de citarla")]
    for cita in ev.citas:
        palabras = len(cita.split())
        if palabras > conf_ev["cita_max_palabras"]:
            salida.append(("aviso", "cita_larga", f"cita de {palabras} palabras (máximo {conf_ev['cita_max_palabras']})"))
        estados = [(e, cita_en_texto(cita, t, conf_ev["cita_min_palabras_comprobables"])) for e, t in textos]
        entrada, estado = next((x for x in estados if x[1] == "exacta"), None) or \
            next((x for x in estados if x[1] == "puntuacion"), None) or estados[0]
        if estado == "no":
            salida.append(("error", "cita_no_encontrada",
                           f"la cita no aparece en el texto guardado de {ev.url or 'la captura'}: «{cita[:120]}»"))
        elif estado == "corta":
            salida.append(("aviso", "cita_corta", f"cita demasiado corta para comprobarla: «{cita[:80]}»"))
        else:
            salida.append(("ok", "cita_comprobada", cita[:80]))
            if estado == "puntuacion":
                salida.append(("aviso", "cita_con_otra_puntuacion",
                               "la cita coincide salvo en la puntuación: cópiala tal cual"))
            if entrada.get("origen") == "manual":
                salida.append(("aviso", "cita_de_texto_manual",
                               "la cita se ha comprobado contra un texto registrado a mano"))
    return salida


def capturas_registradas(reg: RegistroPaginas) -> list:
    return [(e, reg.texto(e)) for e in reg.entradas() if e.get("origen") == "captura"]


def _validar_evidencias(caso: Path, inf: _Informe) -> tuple:
    reg = RegistroPaginas(caso)
    capturas = capturas_registradas(reg)
    evidencias = leer_evidencias(caso)
    vistos: dict = {}
    citas_ok = 0
    for ev in evidencias:
        donde = ev.archivo
        if ev.id in vistos:
            inf.error("id_duplicado", donde, f"{ev.id} ya está en {vistos[ev.id]}", ev.id)
        vistos.setdefault(ev.id, ev.archivo)
        for nivel, codigo, detalle in problemas_de_evidencia(ev, reg, capturas):
            if nivel == "error":
                inf.error(codigo, donde, detalle, ev.id)
            elif nivel == "aviso":
                inf.aviso(codigo, donde, detalle, ev.id)
            else:
                citas_ok += 1
    return evidencias, citas_ok


def _validar_informe(caso: Path, evidencias: list, inf: _Informe) -> dict:
    texto = _leer(caso / "informe.md")
    if not texto:
        inf.error("falta_informe", "informe.md", "no existe informe.md")
        return {}
    ids = {e.id for e in evidencias}
    urls_ev = {normalizar_url(u) for e in evidencias for u in (e.url, e.copia) if u}
    if "{{" in texto:
        inf.error("plantilla_sin_rellenar", "informe.md", "quedan marcadores {{…}} de la plantilla")
    cab = cabecera_del_informe(texto)
    cal = cab.get("calificacion")
    if not cal:
        inf.error("sin_calificacion", "informe.md", "el título no contiene una calificación de la escala")
    elif cab.get("calificacion_cabecera") and cab["calificacion_cabecera"] != cal:
        inf.error("calificacion_incoherente", "informe.md",
                  f"el título dice {cal} y la cabecera {cab['calificacion_cabecera']}")
    if cal and cab.get("confianza") and cab["confianza"] not in calificaciones()[cal]["confianzas"]:
        inf.error("confianza_no_permitida", "informe.md",
                  f"la confianza {cab['confianza']} no está permitida con {cal} (reglas.json)")
    fuentes = fuentes_del_informe(texto)
    numeros = [f.n for f in fuentes]
    if not fuentes:
        if cal in _CON_FUENTES:
            inf.error("sin_fuentes", "informe.md",
                      f"un {cal} necesita fuentes y la sección Fuentes está vacía: si no hay ninguna evidencia que "
                      "citar, la calificación tiene que ser otra (ver la regla de la ausencia de pruebas en "
                      "calificaciones.md); no te inventes fuentes")
        else:
            inf.aviso("sin_fuentes", "informe.md", "la sección Fuentes está vacía (no hay ninguna evidencia que citar)")
    if len(set(numeros)) != len(numeros):
        inf.error("fuente_duplicada", "informe.md", "hay números de fuente repetidos")
    if numeros and sorted(numeros) != list(range(1, len(numeros) + 1)):
        inf.aviso("numeracion_fuentes", "informe.md", "las fuentes no están numeradas de 1 en adelante sin huecos")
    for f in fuentes:
        if not f.url:
            inf.error("fuente_sin_url", "informe.md", f"la fuente [{f.n}] no tiene URL", f"[{f.n}]")
        elif normalizar_url(f.url) not in urls_ev and (not f.copia or normalizar_url(f.copia) not in urls_ev):
            inf.error("fuente_sin_evidencia", "informe.md",
                      f"la fuente [{f.n}] ({f.url}) no corresponde a ninguna evidencia E-…", f"[{f.n}]")
    cuerpo = texto.split("\n## Fuentes", 1)[0]
    for n in sorted({int(x) for x in re.findall(r"\[(\d+)\]", sin_comentarios(cuerpo))}):
        if n not in numeros:
            inf.error("referencia_inexistente", "informe.md", f"se cita [{n}] pero no está en Fuentes", f"[{n}]")
    con_apartado = {a.id for a in apartados_del_informe(texto, "A")}
    for aid in dict.fromkeys(re.findall(r"^\|\s*(A\d+)\s*\|", _leer(caso / "02-afirmaciones.md"), re.M)):
        if aid not in con_apartado:
            inf.aviso("afirmacion_sin_apartado", "informe.md",
                      f"{aid} está en el desglose pero no tiene su apartado «### {aid}: … → …» en el informe", aid)
    for eid in sorted(set(ID_EVIDENCIA_RE.findall(texto)) - ids):
        inf.error("evidencia_inexistente", "informe.md", f"se menciona {eid} pero no existe en evidencias/", eid)
    return {"calificacion": cal, "numeros": numeros, "confianza": cab.get("confianza")}


def _validar_publicacion(caso: Path, cal, numeros: list, inf: _Informe) -> dict:
    texto = _leer(caso / "publicacion.md")
    if not texto:
        inf.error("falta_publicacion", "publicacion.md", "no existe publicacion.md")
        return {}
    if "{{" in texto:
        inf.error("plantilla_sin_rellenar", "publicacion.md", "quedan marcadores {{…}} de la plantilla")
    pubs = publicaciones(texto)
    conf = reglas()["publicaciones"]
    for clave, c in conf.items():
        valor = pubs.get(clave)
        vacio = not valor or (isinstance(valor, list) and not any(x.strip() for x in valor)) or \
            (isinstance(valor, str) and not valor.strip())
        if clave not in pubs and not c.get("opcional"):
            inf.error("falta_publicacion", "publicacion.md", f"falta el bloque «{c['titulo']}»", clave)
        elif clave in pubs and vacio and not c.get("opcional"):
            inf.error("publicacion_vacia", "publicacion.md", f"el bloque «{c['titulo']}» está vacío", clave)
    hilo = pubs.get("hilo_x", [])
    if hilo and not conf["hilo_x"]["min"] <= len(hilo) <= conf["hilo_x"]["max"]:
        inf.aviso("hilo_longitud", "publicacion.md",
                  f"el hilo tiene {len(hilo)} publicaciones ({conf['hilo_x']['min']}-{conf['hilo_x']['max']})")
    medibles = [("breve", pubs.get("breve"))] + [(f"hilo_x[{i}]", b) for i, b in enumerate(hilo, 1)]
    limite_x = plataformas()["x"]["limite"]
    for nombre, bloque in medibles:
        if bloque and longitud(bloque, "x") > limite_x:
            inf.error("excede_limite", "publicacion.md",
                      f"{nombre} pesa {longitud(bloque, 'x')} en X (límite {limite_x})", nombre)
    if pubs.get("breve"):
        for plat in conf["breve"]["plataformas"]:
            lim = plataformas()[plat]["limite"]
            if longitud(pubs["breve"], plat) > lim:
                inf.aviso("excede_limite_plataforma", "publicacion.md",
                          f"la publicación breve no cabe en {plat} ({longitud(pubs['breve'], plat)}/{lim})", "breve")
    if cal:
        etiqueta = calificaciones()[cal]["etiqueta"]
        for clave in ("breve", "largo", "mensajeria"):
            bloque = pubs.get(clave)
            if not bloque:
                continue
            otra = calificacion_en(bloque)
            if otra and otra != cal:
                inf.error("calificacion_incoherente", "publicacion.md",
                          f"«{conf[clave]['titulo']}» dice {otra} y el informe {cal}", clave)
            elif otra is None:
                inf.aviso("sin_etiqueta", "publicacion.md", f"«{conf[clave]['titulo']}» no lleva «{etiqueta}»", clave)
        if hilo:
            otra = calificacion_en(hilo[0])
            if otra and otra != cal:
                inf.error("calificacion_incoherente", "publicacion.md",
                          f"el hilo dice {otra} y el informe {cal}", "hilo_x[1]")
    if "asistencia de ia" not in texto.lower():
        inf.aviso("sin_transparencia", "publicacion.md", "no aparece la línea de transparencia (asistencia de IA)")
    for n in sorted({int(x) for x in re.findall(r"\[(\d+)\]", "\n".join(hilo + [pubs.get("largo") or ""]))}):
        if numeros and n not in numeros:
            inf.aviso("referencia_inexistente", "publicacion.md", f"se cita [{n}] y el informe no tiene esa fuente")
    return pubs


def _enlaces_al_original(caso: Path, inf: _Informe) -> None:
    cap = caso / "captura.json"
    if not cap.is_file():
        return
    entrada = json.loads(cap.read_text(encoding="utf-8")).get("entrada") or ""
    if not entrada.startswith("http"):
        return
    clave = normalizar_url(entrada)
    for nombre in ("informe.md", "publicacion.md"):
        for url in URL_RE.findall(_leer(caso / nombre)):
            if normalizar_url(url.rstrip(".,;:)»”")) == clave:
                inf.aviso("enlace_al_original", nombre,
                          "se enlaza el contenido original: enlaza su copia archivada para no amplificarlo")
                break


def validar(caso) -> dict:
    caso = Path(caso).expanduser().resolve()
    inf = _Informe()
    if not caso.is_dir():
        inf.error("sin_caso", str(caso), "la carpeta del caso no existe")
        return {"ok": False, "caso": str(caso), "errores": inf.errores, "avisos": inf.avisos, "resumen": {}}
    evidencias, citas_ok = _validar_evidencias(caso, inf)
    datos = _validar_informe(caso, evidencias, inf)
    cal = datos.get("calificacion")
    _validar_publicacion(caso, cal, datos.get("numeros", []), inf)
    _enlaces_al_original(caso, inf)
    res_path = caso / "resultado.json"
    if res_path.is_file():
        try:
            res = json.loads(res_path.read_text(encoding="utf-8"))
        except ValueError as e:
            inf.error("resultado_ilegible", "resultado.json", f"JSON no válido: {e}")
        else:
            for problema in comprobar_resultado(res):
                inf.error("resultado_no_valido", "resultado.json", problema)
            if cal and res.get("calificacion") and res["calificacion"] != cal:
                inf.error("calificacion_incoherente", "resultado.json",
                          f"resultado.json dice {res['calificacion']} y el informe {cal}")
            if datos.get("confianza") and res.get("confianza") and res["confianza"] != datos["confianza"]:
                inf.error("confianza_incoherente", "resultado.json",
                          f"resultado.json dice {res['confianza']} y el informe {datos['confianza']}")
    else:
        inf.aviso("sin_resultado", "resultado.json", "aún no existe resultado.json (se genera tras la auditoría)")
    if cal == "FALSO":
        fuentes = fuentes_del_informe(_leer(caso / "informe.md"))
        primarias = [f for f in fuentes if (f.tipo or "").startswith("primaria")]
        dominios = {normalizar_url(f.url).split("/")[0] for f in fuentes if f.url}
        if len(dominios) < reglas()["falso"]["fuentes_independientes_min"] and not primarias:
            inf.aviso("falso_con_pocas_fuentes", "informe.md",
                      "un FALSO necesita fuentes independientes o una primaria definitiva (calificaciones.md)")
    reg = RegistroPaginas(caso)
    return {"ok": not inf.errores, "caso": str(caso), "errores": inf.errores, "avisos": inf.avisos,
            "resumen": {"evidencias": len(evidencias), "citas_comprobadas": citas_ok,
                        "paginas_registradas": len(reg.entradas()), "busquedas_registradas": len(busquedas(caso)),
                        "errores": len(inf.errores), "avisos": len(inf.avisos)}}
