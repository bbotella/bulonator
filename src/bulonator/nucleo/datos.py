"""Localiza los archivos de metodología: referencias, plantillas y definiciones de agentes.

La metodología tiene una sola copia en el repositorio (``skills/bulonator/references``,
``skills/bulonator/templates`` y ``agents``). Según cómo se use Bulonator, se encuentra en:

1. Las variables ``BULONATOR_REFS``, ``BULONATOR_PLANTILLAS`` y ``BULONATOR_AGENTES``. El lanzador
   del plugin de Claude Code fija las dos primeras.
2. El paquete instalado con pip o uv: ``bulonator/_datos/`` (se copia al construir la rueda).
3. Un clon del repositorio (instalación editable o ejecución desde ``src/``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

_PAQUETE = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Metodologia:
    referencias: Path
    plantillas: Path
    agentes: Optional[Path]

    def referencia(self, nombre: str) -> Path:
        return self.referencias / nombre

    def plantilla(self, nombre: str) -> Path:
        return self.plantillas / nombre

    def agente(self, nombre: str) -> Path:
        if self.agentes is None:
            raise FileNotFoundError("no se han encontrado las definiciones de los agentes "
                                    "(define BULONATOR_AGENTES)")
        return self.agentes / f"{nombre}.md"


def _desde_entorno() -> Optional[Metodologia]:
    refs = os.environ.get("BULONATOR_REFS")
    if not refs:
        return None
    refs_p = Path(refs).expanduser()
    plantillas = Path(os.environ.get("BULONATOR_PLANTILLAS") or refs_p.parent / "templates").expanduser()
    agentes = os.environ.get("BULONATOR_AGENTES")
    return Metodologia(refs_p, plantillas, Path(agentes).expanduser() if agentes else None)


def _candidatos():
    instalado = _PAQUETE / "_datos"
    yield Metodologia(instalado / "references", instalado / "templates", instalado / "agents")
    raiz = _PAQUETE.parent.parent
    yield Metodologia(raiz / "skills" / "bulonator" / "references",
                      raiz / "skills" / "bulonator" / "templates", raiz / "agents")


@lru_cache(maxsize=1)
def metodologia() -> Metodologia:
    """Devuelve las rutas de la metodología o lanza FileNotFoundError si no se encuentran."""
    entorno = _desde_entorno()
    if entorno is not None:
        if not (entorno.referencias / "reglas.json").is_file():
            raise FileNotFoundError(f"BULONATOR_REFS no contiene reglas.json: {entorno.referencias}")
        return entorno
    for m in _candidatos():
        if (m.referencias / "reglas.json").is_file():
            agentes = m.agentes if m.agentes and m.agentes.is_dir() else None
            return Metodologia(m.referencias, m.plantillas, agentes)
    raise FileNotFoundError("no se encuentra la metodología de Bulonator (references/reglas.json); "
                            "define BULONATOR_REFS")


# ---------------------------------------------------------------------------
# Textos de los agentes y de las referencias
# ---------------------------------------------------------------------------

#: Secciones de los agentes que solo valen para Claude Code (el motor las descarta).
SECCIONES_DE_CLAUDE = ("Lo que recibes", "Salida")


def _sin_frontmatter(texto: str) -> str:
    if texto.startswith("---\n"):
        fin = texto.find("\n---\n", 4)
        if fin > 0:
            return texto[fin + 5:]
    return texto


def partes_de_agente(nombre: str) -> tuple:
    """(introducción, [(título, cuerpo), …]) del cuerpo de un agente, sin el frontmatter."""
    from .documentos import secciones

    texto = _sin_frontmatter(metodologia().agente(nombre).read_text(encoding="utf-8"))
    corte = texto.find("\n## ")
    intro = texto if corte < 0 else texto[:corte]
    return intro.strip(), secciones(texto, 2)


def es_seccion_de_claude(titulo: str) -> bool:
    return any(titulo.startswith(s) for s in SECCIONES_DE_CLAUDE)


def texto_compartido_de_agente(nombre: str) -> str:
    """Cuerpo de un agente sin las secciones propias de Claude Code: lo que usa el motor."""
    intro, partes = partes_de_agente(nombre)
    bloques = [intro] + [f"## {t}\n\n{c}" for t, c in partes if not es_seccion_de_claude(t)]
    return "\n\n".join(b for b in bloques if b).strip() + "\n"


def referencias_de_agente(nombre: str) -> list:
    """Archivos de la sección «Referencias» de un agente."""
    import re

    _, partes = partes_de_agente(nombre)
    cuerpo = next((c for t, c in partes if t == "Referencias"), "")
    return re.findall(r"^\s*[-*]\s+`([^`]+)`", cuerpo, flags=re.M)


def seccion_de_referencia(archivo: str, titulo: str) -> str:
    """Cuerpo de la sección ``## titulo`` de una referencia (por ejemplo, ``flujo.md`` → ``Desglose``)."""
    from .documentos import seccion

    texto = metodologia().referencia(archivo).read_text(encoding="utf-8")
    cuerpo = seccion(texto, titulo)
    if cuerpo is None:
        raise KeyError(f"{archivo} no tiene la sección «{titulo}»")
    return cuerpo
