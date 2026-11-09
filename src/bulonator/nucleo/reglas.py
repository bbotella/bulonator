"""Acceso a ``reglas.json``: cifras y listas cerradas de la metodología."""
from __future__ import annotations

import json
from functools import lru_cache

from .datos import metodologia


@lru_cache(maxsize=1)
def reglas() -> dict:
    return json.loads(metodologia().referencia("reglas.json").read_text(encoding="utf-8"))


def calificaciones() -> dict:
    return reglas()["calificaciones"]


def etiqueta(calificacion: str) -> str:
    return calificaciones()[calificacion]["etiqueta"]


def plataformas() -> dict:
    return reglas()["plataformas"]


def modo(nombre: str) -> dict:
    modos = reglas()["modos"]
    if nombre not in modos:
        raise ValueError(f"modo desconocido: {nombre} (válidos: {', '.join(modos)})")
    return modos[nombre]
