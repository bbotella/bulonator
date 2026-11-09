"""Bulonator: verificación de bulos con la metodología del periodismo de verificación.

Se distribuye en dos paquetes que comparten este espacio de nombres:

- ``bulonator-nucleo``: este paquete (``bulonator`` y ``bulonator.nucleo``). Herramientas sin
  dependencias externas, con Python 3.9 o superior: captura, fuentes oficiales, análisis multimedia,
  lectura y registro de páginas, y validación de casos. Es lo que usa el plugin de Claude Code.
- ``bulonator``: el motor de análisis con modelos de lenguaje (``bulonator.motor``, Pydantic AI). Depende
  de ``bulonator-nucleo`` y necesita Python 3.11 o superior. ``pip install bulonator`` instala los dos.

``analizar``, ``analizar_sync`` y ``Config`` se importan bajo demanda desde el motor, para que el
núcleo funcione sin él.
"""
from pathlib import Path as _Path
from pkgutil import extend_path as _extend_path

__version__ = "1.1.0"

# El motor vive en otro paquete de distribución que se instala en este mismo espacio de nombres.
__path__ = _extend_path(__path__, __name__)
# En un clon del repositorio, el motor está en motor/src/bulonator (pruebas y desarrollo sin instalar).
_MOTOR_EN_EL_REPOSITORIO = _Path(__file__).resolve().parent.parent.parent / "motor" / "src" / "bulonator"
if (_MOTOR_EN_EL_REPOSITORIO / "motor" / "__init__.py").is_file() and str(_MOTOR_EN_EL_REPOSITORIO) not in __path__:
    __path__.append(str(_MOTOR_EN_EL_REPOSITORIO))

_DEL_MOTOR = {"analizar", "analizar_sync", "Config", "Caso"}

__all__ = ["__version__", *sorted(_DEL_MOTOR)]


def __getattr__(nombre):
    if nombre in _DEL_MOTOR:
        try:
            from . import motor
        except ImportError as e:
            raise ImportError(f"bulonator.{nombre} necesita el motor: pip install bulonator "
                              "(Python 3.11 o superior)") from e
        return getattr(motor, nombre)
    raise AttributeError(f"module 'bulonator' has no attribute {nombre!r}")
