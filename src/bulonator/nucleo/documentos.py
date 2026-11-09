"""Lectura de los documentos de un caso: evidencias, informe, publicaciones y desglose.

Los formatos son los de ``references/formato-evidencias.md`` y las plantillas de ``templates/``.
Lo usan ``validar`` y ``resultado`` (y el motor, que escribe esos mismos documentos).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .reglas import calificaciones, reglas
from .texto import BLOQUE_RE

ID_EVIDENCIA_RE = re.compile(r"\bE-(?:A\d+|M\d+|O|C)-\d{2,}\b")
_ID_VALIDO_RE = re.compile(r"^E-(?:A\d+|M\d+|O|C)-\d{2,}$")
_CAMPO_RE = re.compile(r"^\s*[-*]\s+\*\*(?P<campo>[^*:]+?):?\*\*:?\s*(?P<valor>.*)$")
URL_RE = re.compile(r"https?://[^\s<>()\"'«»\]]+")
_CITA_RE = re.compile(r"«([^»]+)»|“([^”]+)”|\"([^\"]+)\"")


def _sin_puntuacion_final(url: str) -> str:
    return url.rstrip(".,;:)»”")


@dataclass
class Evidencia:
    id: str
    archivo: str
    campos: dict = field(default_factory=dict)

    def campo(self, nombre: str) -> str:
        for k, v in self.campos.items():
            if k.lower() == nombre.lower():
                return v
        return ""

    @property
    def url(self) -> Optional[str]:
        m = URL_RE.search(self.campo("URL"))
        return _sin_puntuacion_final(m.group(0)) if m else None

    @property
    def copia(self) -> Optional[str]:
        m = URL_RE.search(self.campo("Copia archivada"))
        return _sin_puntuacion_final(m.group(0)) if m else None

    @property
    def tipo(self) -> str:
        valor = self.campo("Tipo").strip().strip("`").lower()
        for t in sorted(reglas()["tipos_fuente"], key=len, reverse=True):
            if valor.startswith(t):
                return t
        return valor

    @property
    def citas(self) -> list:
        """Fragmentos citados en «Cita literal» (las comillas delimitan cada cita)."""
        valor = self.campo("Cita literal").strip()
        if not valor or valor in {"—", "-", "n/a", "no aplica"}:
            return []
        encontradas = [next(g for g in m.groups() if g) for m in _CITA_RE.finditer(valor)]
        return encontradas or [valor]


def leer_evidencias(caso) -> list:
    """Todas las entradas ``### E-…`` de ``evidencias/*.md`` y de ``01-captura.md`` (las ``E-C-…``)."""
    caso = Path(caso)
    archivos = sorted((caso / "evidencias").glob("*.md"))
    if (caso / "01-captura.md").is_file():
        archivos.insert(0, caso / "01-captura.md")
    salida = []
    for archivo in archivos:
        relativo = archivo.relative_to(caso).as_posix()
        actual: Optional[Evidencia] = None
        ultimo_campo = None
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^#{2,4}\s+(E-\S+)", linea)
            if m:
                actual = Evidencia(m.group(1).strip("`*:"), relativo)
                salida.append(actual)
                ultimo_campo = None
                continue
            if actual is None:
                continue
            if re.match(r"^#{1,3}\s", linea):
                actual = None
                continue
            mc = _CAMPO_RE.match(linea)
            if mc:
                ultimo_campo = mc.group("campo").strip()
                actual.campos[ultimo_campo] = mc.group("valor").strip()
            elif ultimo_campo and linea.startswith("  ") and linea.strip():
                actual.campos[ultimo_campo] += " " + linea.strip()
    return salida


def id_valido(id_evidencia: str) -> bool:
    return bool(_ID_VALIDO_RE.match(id_evidencia))


# ---------------------------------------------------------------------------
# Secciones de Markdown
# ---------------------------------------------------------------------------


def secciones(texto: str, nivel: int = 2) -> list:
    """Lista de (título, cuerpo) de las secciones de un nivel dado."""
    marca = "#" * nivel + " "
    superior = re.compile(r"^#{1,%d} " % (nivel - 1)) if nivel > 1 else None
    partes, titulo, cuerpo = [], None, []
    en_bloque = False
    for linea in texto.splitlines():
        if linea.startswith("```"):
            en_bloque = not en_bloque
        if en_bloque or linea.startswith("```"):
            if titulo is not None:
                cuerpo.append(linea)
            continue
        if linea.startswith(marca):
            if titulo is not None:
                partes.append((titulo, "\n".join(cuerpo).strip("\n")))
            titulo, cuerpo = linea[len(marca):].strip(), []
        elif superior is not None and superior.match(linea):
            if titulo is not None:
                partes.append((titulo, "\n".join(cuerpo).strip("\n")))
            titulo, cuerpo = None, []
        elif titulo is not None:
            cuerpo.append(linea)
    if titulo is not None:
        partes.append((titulo, "\n".join(cuerpo).strip("\n")))
    return partes


def seccion(texto: str, empieza: str, nivel: int = 2) -> Optional[str]:
    for titulo, cuerpo in secciones(texto, nivel):
        if titulo.lower().startswith(empieza.lower()):
            return cuerpo
    return None


def calificacion_en(texto: str) -> Optional[str]:
    """Primera calificación de la escala que aparece en un texto (o None)."""
    if not texto:
        return None
    candidatas = []
    for nombre, conf in calificaciones().items():
        for forma in {nombre, conf["etiqueta"].split(" ", 1)[-1].upper()}:
            # En mayúsculas, como en las etiquetas: «lo verdadero» en la prosa no es una calificación
            m = re.search(r"(?<![\wÁÉÍÓÚÑ])" + re.escape(forma) + r"(?![\wÁÉÍÓÚÑ])", texto)
            if m:
                candidatas.append((m.start(), -len(forma), nombre))
    return min(candidatas)[2] if candidatas else None


def sin_comentarios(texto: str) -> str:
    return re.sub(r"<!--.*?-->", "", texto, flags=re.S)


# ---------------------------------------------------------------------------
# informe.md
# ---------------------------------------------------------------------------


@dataclass
class Fuente:
    n: int
    referencia: str
    url: Optional[str]
    copia: Optional[str]
    tipo: Optional[str]


def fuentes_del_informe(informe: str) -> list:
    cuerpo = seccion(informe, "Fuentes") or ""
    fuentes = []
    for linea in cuerpo.splitlines():
        m = re.match(r"^\s*(?:[-*]\s*)?\[(\d+)\]\s*(.+)$", linea)
        if not m:
            continue
        resto = m.group(2).strip()
        urls = [_sin_puntuacion_final(u) for u in URL_RE.findall(resto)]
        copia = None
        mc = re.search(r"copia:\s*<?(https?://[^\s<>)]+)", resto)
        if mc:
            copia = _sin_puntuacion_final(mc.group(1))
        principal = next((u for u in urls if u != copia), copia)
        tipo = None
        for t in sorted(reglas()["tipos_fuente"], key=len, reverse=True):
            if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", resto.lower()):
                tipo = t
                break
        fuentes.append(Fuente(int(m.group(1)), resto, principal, copia, tipo))
    return fuentes


@dataclass
class Apartado:
    id: str
    texto: str
    calificacion: Optional[str]
    valoracion: str
    evidencias: list


def apartados_del_informe(informe: str, prefijo: str) -> list:
    """Apartados ``### A1: afirmación → calificación`` (o ``M1``) con sus evidencias."""
    salida = []
    for titulo, cuerpo in secciones(informe, 3):
        m = re.match(rf"^({prefijo}\d+)\s*[:.]\s*(.+?)\s*(?:→|->)\s*(.+)$", titulo)
        if not m:
            continue
        valoracion = m.group(3).strip()
        salida.append(Apartado(m.group(1), m.group(2).strip(), calificacion_en(valoracion), valoracion,
                               sorted(set(ID_EVIDENCIA_RE.findall(cuerpo)))))
    return salida


def cabecera_del_informe(informe: str) -> dict:
    """Calificación, subtipo y confianza de la cabecera (y el titular)."""
    titulo = next((ln[2:].strip() for ln in informe.splitlines() if ln.startswith("# ")), "")
    datos = {"titulo": titulo, "calificacion": calificacion_en(titulo), "subtipo": None, "confianza": None}
    m = re.search(r"\*\*Calificación:\*\*\s*([^·\n]+)", informe)
    if m:
        datos["calificacion_cabecera"] = calificacion_en(m.group(1))
        ms = re.search(r"\(([^)]+)\)", m.group(1))
        if ms:
            datos["subtipo"] = ms.group(1).strip().strip("`")
    m = re.search(r"\*\*Confianza:\*\*\s*(ALTA|MEDIA|BAJA)", informe, re.I)
    if m:
        datos["confianza"] = m.group(1).upper()
    titular = re.sub(r"^\W*\s*[A-ZÁÉÍÓÚÑ ]+:\s*", "", titulo).strip()
    datos["titular"] = titular or titulo
    return datos


def lista(cuerpo: Optional[str]) -> list:
    if not cuerpo:
        return []
    return [re.sub(r"^\s*[-*]\s+", "", ln).strip() for ln in cuerpo.splitlines()
            if re.match(r"^\s*[-*]\s+\S", ln)]


# ---------------------------------------------------------------------------
# publicacion.md
# ---------------------------------------------------------------------------


def publicaciones(publicacion: str) -> dict:
    """Bloques ```text de cada sección de ``publicacion.md``, por clave de ``reglas.json``."""
    tipos = reglas()["publicaciones"]
    salida: dict = {}
    for titulo, cuerpo in secciones(publicacion, 2):
        limpio = re.sub(r"^\d+\.\s*", "", titulo).lower()
        clave = next((k for k, conf in tipos.items() if limpio.startswith(conf["titulo"].lower())), None)
        if clave is None:
            continue
        bloques = [b.strip("\n") for b in BLOQUE_RE.findall(cuerpo)]
        if clave == "hilo_x":
            salida[clave] = bloques
        elif bloques:
            salida[clave] = bloques[0]
    return salida


# ---------------------------------------------------------------------------
# 02-afirmaciones.md
# ---------------------------------------------------------------------------


def afirmacion_central(desglose: str) -> Optional[str]:
    cuerpo = seccion(desglose, "Afirmación central") or ""
    m = re.search(r"\b(A\d+)\b", cuerpo)
    return m.group(1) if m else None
