"""Bulonator: verificación de bulos con la metodología del periodismo de verificación.

El paquete tiene dos partes:

- ``bulonator.nucleo``: herramientas sin dependencias externas (captura, fuentes oficiales,
  análisis multimedia, lectura y registro de páginas, validación de casos).
- ``bulonator.motor``: el motor de análisis con modelos de lenguaje (Pydantic AI). Necesita
  el extra ``[motor]`` y Python 3.11 o superior.

``analizar``, ``analizar_sync`` y ``Config`` se importan bajo demanda desde el motor, para que
el núcleo funcione sin dependencias.
"""

__version__ = "1.1.0"

_DEL_MOTOR = {"analizar", "analizar_sync", "Config", "Caso"}

__all__ = ["__version__", *sorted(_DEL_MOTOR)]


def __getattr__(nombre):
    if nombre in _DEL_MOTOR:
        from . import motor

        return getattr(motor, nombre)
    raise AttributeError(f"module 'bulonator' has no attribute {nombre!r}")
