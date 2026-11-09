"""Motor de Bulonator: el análisis completo con modelos de lenguaje (Pydantic AI).

Uso básico::

    from bulonator import analizar, Config

    config = Config(modelos={"defecto": "ollama:gpt-oss:20b", "auditor": "openai:<modelo>"})
    caso = await analizar("https://…", config, al_progresar=print)
    caso.resultado.calificacion      # "FALSO"
    caso.resultado.publicaciones     # textos para redes
    caso.aprobado                    # auditoría superada y validación sin errores

Es el paquete ``bulonator`` de PyPI (``pip install bulonator``, Python 3.11 o superior), que depende
de ``bulonator-nucleo``. La librería no publica nada: quien la usa decide qué hacer con el caso, y la
recomendación es que una persona lo revise antes de publicarlo.
"""
import os

__version__ = "1.1.0"

# El aviso de bienvenida de Pydantic AI saldría por la salida estándar, que la CLI usa para el JSON
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from .config import PAPELES, Config  # noqa: E402
from .esquemas import (Desglose, Dictamen, Evidencia, Ficha, InformeAgente, Redaccion,  # noqa: E402
                       Resultado)
from .herramientas import Contexto, Servicios, toolset  # noqa: E402
from .proceso import Analisis, CapturaVacia, Caso, Evento, PresupuestoAgotado, analizar, analizar_sync  # noqa: E402

__all__ = [
    "PAPELES", "Analisis", "CapturaVacia", "Caso", "Config", "Contexto", "Desglose", "Dictamen", "Evento",
    "Evidencia", "Ficha", "InformeAgente", "PresupuestoAgotado", "Redaccion", "Resultado", "Servicios",
    "analizar", "analizar_sync", "toolset",
]
