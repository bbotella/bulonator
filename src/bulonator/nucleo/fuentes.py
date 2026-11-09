"""Fuentes oficiales y servicios de verificación: dominio, BOE, INE, búsqueda inversa y desmentidos.

Las funciones que reciben ``caso`` registran en ``evidencias/paginas/`` lo que devolvió la fuente,
para que se pueda citar como evidencia y ``validar`` lo compruebe.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
from typing import Optional

from .caso import RegistroPaginas
from .captura import _ts_to_iso
from .red import host_of, http_json, registered_domain
from .util import HttpError, run, tail, texto_plano


def _registrar(caso, origen: str, registros: list) -> None:
    if caso is None:
        return
    reg = RegistroPaginas(caso)
    for url, texto, titulo in registros:
        if url and texto:
            reg.registrar(url, texto, origen, titulo=titulo)


# ---------------------------------------------------------------------------
# dominio
# ---------------------------------------------------------------------------


def dominio(objetivo: str, caso=None) -> dict:
    """Datos de registro de un dominio (RDAP o, si no hay, whois)."""
    dom = registered_domain(host_of(objetivo) if "://" in objetivo else objetivo)
    res: dict = {"dominio": dom}
    fuente_url = f"https://rdap.org/domain/{dom}"
    try:
        j = http_json(fuente_url, timeout=25)
        if j.get("errorCode"):
            raise HttpError(j.get("title", "sin RDAP"))
        res["fuente"] = "RDAP"
        res["eventos"] = {ev.get("eventAction"): ev.get("eventDate") for ev in j.get("events", [])}
        for ent in j.get("entities", []):
            if "registrar" in ent.get("roles", []):
                vc = ent.get("vcardArray", [None, []])[1]
                res["registrador"] = next((x[3] for x in vc if x[0] == "fn"), None)
        res["estado"] = j.get("status")
        res["servidores_nombre"] = [ns.get("ldhName") for ns in j.get("nameservers", [])]
    except (HttpError, ValueError) as e:
        res["rdap_error"] = str(e)
        if dom.endswith(".es"):
            res["nota"] = ("Los .es no tienen RDAP público y el whois de dominios.es suele bloquear consultas "
                           "automáticas: consulta https://www.dominios.es/es/consultar-dominio (navegador).")
        rc, so, se = run(["whois", dom], 20)
        if rc == 0 and so:
            res["fuente"] = "whois"
            fuente_url = f"whois://{dom}"
            pats = {"creado": r"(?im)^\s*(?:creation date|created(?: on)?|registered(?: on)?|registration time|"
                              r"fecha de (?:alta|creaci[oó]n)|domain record activated)\s*[:.]+\s*(.+)$",
                    "expira": r"(?im)^\s*(?:registry expiry date|expir\w* (?:date|on)|paid-till|fecha de expiraci[oó]n)\s*[:.]+\s*(.+)$",
                    "registrador": r"(?im)^\s*(?:registrar|sponsoring registrar)\s*:\s*(.+)$",
                    "pais_titular": r"(?im)^\s*registrant country\s*:\s*(.+)$"}
            for key, pat in pats.items():
                m = re.search(pat, so)
                if m:
                    res[key] = m.group(1).strip()
            if len(res) <= 3:
                res["whois_extracto"] = so[:1500]
        else:
            res["whois_error"] = tail(se, 200) or "whois no disponible"
    if res.get("fuente"):
        res["url_fuente"] = fuente_url
        _registrar(caso, "dominio", [(fuente_url, texto_plano(res), f"Registro del dominio {dom}")])
    return res


# ---------------------------------------------------------------------------
# BOE
# ---------------------------------------------------------------------------

BOE_API = "https://www.boe.es/datosabiertos/api"


def _boe_items(node, out):
    if isinstance(node, list):
        for x in node:
            _boe_items(x, out)
    elif isinstance(node, dict):
        if "identificador" in node and "titulo" in node and ("url_html" in node or "url_pdf" in node):
            pdf = node.get("url_pdf")
            out.append({"identificador": node["identificador"], "titulo": node["titulo"],
                        "url_html": node.get("url_html"),
                        "url_pdf": pdf.get("texto") if isinstance(pdf, dict) else pdf})
            return
        for v in node.values():
            _boe_items(v, out)


def boe_sumario(fecha: str, texto: Optional[str] = None, limite: int = 15, caso=None) -> dict:
    """Disposiciones publicadas en el BOE un día (AAAAMMDD), filtradas por palabras del título."""
    data = http_json(f"{BOE_API}/boe/sumario/{fecha}")
    items: list = []
    _boe_items(data.get("data", {}), items)
    if texto:
        words = [w.lower() for w in texto.split()]
        items = [i for i in items if all(w in i["titulo"].lower() for w in words)]
    res = {"fecha": fecha, "total": len(items), "resultados": items[:limite]}
    _registrar(caso, "boe", [(i.get("url_html") or i.get("url_pdf"),
                              f"{i['identificador']} | {i['titulo']} | BOE del {fecha}", i["titulo"])
                             for i in res["resultados"]])
    return res


def boe(texto: str, desde: Optional[str] = None, hasta: Optional[str] = None, limite: int = 15, caso=None) -> dict:
    """Busca en el título de la legislación consolidada del BOE (sintaxis Lucene: AND, OR, comillas)."""
    if not texto:
        raise ValueError("indica un texto a buscar")
    q = f"titulo:({texto})"
    if desde or hasta:
        q += f" AND fecha_publicacion:[{desde or '18000101'} TO {hasta or '29991231'}]"
    query = {"query": {"query_string": {"query": q}}, "sort": [{"fecha_publicacion": "desc"}]}
    url = f"{BOE_API}/legislacion-consolidada?" + urllib.parse.urlencode(
        {"query": json.dumps(query, ensure_ascii=False), "limit": limite})
    data = http_json(url)
    rows = []
    for x in data.get("data") or []:
        rows.append({"identificador": x.get("identificador"), "titulo": x.get("titulo"),
                     "rango": (x.get("rango") or {}).get("texto"), "ambito": (x.get("ambito") or {}).get("texto"),
                     "departamento": (x.get("departamento") or {}).get("texto"),
                     "fecha_disposicion": x.get("fecha_disposicion"), "fecha_publicacion": x.get("fecha_publicacion"),
                     "vigencia_agotada": x.get("vigencia_agotada"), "url": x.get("url_html_consolidada"),
                     "eli": x.get("url_eli")})
    _registrar(caso, "boe", [(r["url"], " | ".join(str(r.get(k)) for k in (
        "identificador", "titulo", "rango", "departamento", "fecha_disposicion", "fecha_publicacion")
        ) + f" | vigencia agotada: {r.get('vigencia_agotada')}", r["titulo"]) for r in rows])
    return {"consulta": q, "nota": "Busca en el TÍTULO de la legislación consolidada. Para anuncios, nombramientos, "
                                   "convocatorias o el texto completo usa `buscar` restringido a boe.es o el "
                                   "sumario diario (boe_sumario). Para citar el texto de una norma, ábrela con "
                                   "`leer`.", "resultados": rows}


# ---------------------------------------------------------------------------
# INE
# ---------------------------------------------------------------------------

INE_API = "https://servicios.ine.es/wstempus/js/ES"


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _coincide(nombre: str, texto: Optional[str]) -> bool:
    return not texto or all(w in _fold(nombre) for w in _fold(texto).split())


def ine_operaciones(texto: str, limite: int = 25) -> dict:
    """Operaciones estadísticas del INE cuyo nombre contiene las palabras dadas."""
    if not texto:
        raise ValueError("indica un texto a buscar")
    data = http_json(f"{INE_API}/OPERACIONES_DISPONIBLES", timeout=60)
    rows = [{"codigo": o.get("Codigo"), "id": o.get("Id"), "nombre": o.get("Nombre"),
             "url": "https://www.ine.es" + o["Url"] if o.get("Url") else None}
            for o in data if _coincide(o.get("Nombre", ""), texto)]
    return {"operaciones": rows[:limite],
            "siguiente_paso": "ine_tablas con el código de la operación y luego ine_datos con el id de la tabla"}


def ine_tablas(operacion: str, texto: Optional[str] = None, limite: int = 25) -> dict:
    """Tablas de una operación del INE (por ejemplo EPA o IPC), filtradas por nombre."""
    data = http_json(f"{INE_API}/TABLAS_OPERACION/{operacion}", timeout=60)
    rows = [{"id": t.get("Id"), "nombre": t.get("Nombre"),
             "ultima_modificacion": _ts_to_iso((t.get("Ultima_Modificacion") or 0) / 1000),
             "url": f"https://www.ine.es/jaxiT3/Tabla.htm?t={t.get('Id')}"}
            for t in data if _coincide(t.get("Nombre", ""), texto)]
    return {"operacion": operacion, "tablas": rows[:limite], "total": len(rows)}


def ine_datos(tabla: str, nult: int = 5, texto: Optional[str] = None, limite: int = 25, caso=None) -> dict:
    """Últimos periodos de las series de una tabla del INE. Con ``caso``, cada dato queda registrado
    como una línea ``serie | periodo | valor``, que es la cita literal de la evidencia."""
    data = http_json(f"{INE_API}/DATOS_TABLA/{tabla}?nult={nult}&tip=A", timeout=60)
    rows = []
    for serie in data:
        name = serie.get("Nombre", "")
        if not _coincide(name, texto):
            continue
        rows.append({"serie": name, "unidad": (serie.get("Unidad") or {}).get("Nombre"),
                     "datos": [{"periodo": d.get("NombrePeriodo") or f"{d.get('Anyo')}-{d.get('FK_Periodo')}",
                                "valor": d.get("Valor"), "fecha": _ts_to_iso((d.get("Fecha") or 0) / 1000)}
                               for d in serie.get("Data", [])]})
    url_tabla = f"https://www.ine.es/jaxiT3/Tabla.htm?t={tabla}"
    res = {"tabla": tabla, "url_tabla": url_tabla, "series": rows[:limite], "total_series": len(rows)}
    lineas = [f"{s['serie']} | {d['periodo']} | {d['valor']}" + (f" | {s['unidad']}" if s.get("unidad") else "")
              for s in res["series"] for d in s["datos"]]
    _registrar(caso, "ine", [(url_tabla, "\n".join(lineas), f"INE, tabla {tabla}")])
    return res


# ---------------------------------------------------------------------------
# Búsqueda inversa y verificaciones previas
# ---------------------------------------------------------------------------


def buscar_imagen(url: str, limite: int = 15) -> dict:
    """Enlaces de búsqueda inversa de una imagen y, con SERPAPI_API_KEY, coincidencias de Google Lens."""
    u = urllib.parse.quote(url, safe="")
    res: dict = {"imagen": url, "enlaces_manual": {
        "google_lens": f"https://lens.google.com/uploadbyurl?url={u}",
        "bing": f"https://www.bing.com/images/search?view=detailv2&iss=sbi&form=SBIVSP&sbisrc=UrlPaste&q=imgurl:{u}",
        "yandex": f"https://yandex.com/images/search?rpt=imageview&url={u}",
        "tineye": f"https://tineye.com/search?url={u}",
    }, "nota": "Estos buscadores requieren navegador. Ábrelos con un navegador si está disponible o "
               "entrégalos al usuario. TinEye permite ordenar por fecha ('oldest') para encontrar la primera aparición."}
    key = os.environ.get("SERPAPI_API_KEY")
    if key:
        try:
            q = urllib.parse.urlencode({"engine": "google_lens", "url": url, "api_key": key, "hl": "es"})
            data = http_json(f"https://serpapi.com/search.json?{q}", timeout=90)
            res["coincidencias_google_lens"] = [
                {"titulo": m.get("title"), "url": m.get("link"), "fuente": m.get("source"), "fecha": m.get("date")}
                for m in (data.get("visual_matches") or [])[:limite]]
        except (HttpError, ValueError) as e:
            res["serpapi_error"] = str(e)
    else:
        res["api"] = "Define SERPAPI_API_KEY para obtener coincidencias de Google Lens automáticamente."
    return res


def factcheck(texto: str, idioma: str = "es", limite: int = 10, caso=None) -> dict:
    """Verificaciones previas en Google Fact Check Tools (ClaimReview) si hay GOOGLE_FACTCHECK_API_KEY."""
    q = urllib.parse.quote(texto)
    res: dict = {"consulta": texto, "enlaces_manual": {
        "google_fact_check_explorer": f"https://toolbox.google.com/factcheck/explorer/search/{q};hl={idioma}",
    }}
    key = os.environ.get("GOOGLE_FACTCHECK_API_KEY")
    if key:
        try:
            params = urllib.parse.urlencode({"query": texto, "languageCode": idioma, "pageSize": limite,
                                             "key": key})
            data = http_json(f"https://factchecktools.googleapis.com/v1alpha1/claims:search?{params}")
            res["verificaciones"] = [
                {"afirmacion": c.get("text"), "quien": c.get("claimant"), "fecha": c.get("claimDate"),
                 "revisiones": [{"verificador": (r.get("publisher") or {}).get("name"), "url": r.get("url"),
                                 "titulo": r.get("title"), "calificacion": r.get("textualRating"),
                                 "fecha": r.get("reviewDate")} for r in c.get("claimReview", [])]}
                for c in data.get("claims", [])]
            _registrar(caso, "factcheck", [
                (r["url"], f"{r['verificador']} | {r['titulo']} | calificación: {r['calificacion']} | "
                           f"fecha: {r['fecha']} | afirmación revisada: {c['afirmacion']}", r["titulo"])
                for c in res["verificaciones"] for r in c["revisiones"] if r.get("url")])
        except (HttpError, ValueError) as e:
            res["api_error"] = str(e)
    else:
        res["api"] = ("Define GOOGLE_FACTCHECK_API_KEY (gratuita en Google Cloud) para consultar ClaimReview. "
                      "Mientras tanto usa `buscar` restringido a los dominios de verificadores "
                      "(ver references/verificadores.md).")
    return res
