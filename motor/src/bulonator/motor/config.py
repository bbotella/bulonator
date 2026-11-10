"""Configuración del motor: qué modelo hace cada papel, modo, buscador y límites."""
from __future__ import annotations

import os
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Papeles del análisis. ``defecto`` se usa para los que no tienen modelo propio.
PAPELES = ("captura", "desglose", "verificador", "multimedia", "origen", "redactor", "auditor")
#: Proveedores con búsqueda web nativa (Pydantic AI la ofrece como herramienta del propio modelo).
CON_BUSQUEDA_NATIVA = ("anthropic", "openai", "openai-responses", "google", "google-gla", "google-vertex")


def url_ollama() -> str:
    """URL de la API compatible con OpenAI de Ollama.

    Usa ``OLLAMA_BASE_URL`` si está definida. Si no, la deduce de ``OLLAMA_HOST`` (la variable del propio
    Ollama, que puede ser solo ``0.0.0.0`` o ``servidor:puerto``) o usa ``http://localhost:11434/v1``.
    """
    if os.environ.get("OLLAMA_BASE_URL"):
        return os.environ["OLLAMA_BASE_URL"].rstrip("/")
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return "http://localhost:11434/v1"
    # Como el cliente de Ollama: sin esquema, el puerto por defecto es 11434; con http o https, el del esquema
    con_esquema = "://" in host
    partes = urllib.parse.urlsplit(host if con_esquema else "http://" + host)
    puerto = partes.port or ({"http": 80, "https": 443}.get(partes.scheme, 11434) if con_esquema else 11434)
    servidor = partes.hostname or "localhost"
    if servidor in ("0.0.0.0", "::", "[::]"):
        servidor = "localhost"  # 0.0.0.0 es la dirección en la que escucha, no a la que se conecta
    if ":" in servidor:
        servidor = f"[{servidor}]"
    return f"{partes.scheme or 'http'}://{servidor}:{puerto}{partes.path.rstrip('/') or ''}/v1"


class Config(BaseModel):
    """Configuración de un análisis.

    ``modelos`` asigna un modelo a cada papel (``captura``, ``desglose``, ``verificador``,
    ``multimedia``, ``origen``, ``redactor``, ``auditor``) con la sintaxis de Pydantic AI
    (``"ollama:gpt-oss:20b"``, ``"openai:<modelo>"``, ``"google:<modelo>"``, ``"anthropic:<modelo>"``)
    o con un objeto ``Model`` ya construido. La clave ``defecto`` cubre los papeles sin modelo propio.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    modelos: dict[str, Any] = Field(default_factory=lambda: {"defecto": "ollama:gpt-oss:20b"})
    modo: Literal["rapido", "normal", "profundo"] = "normal"
    idioma: str = "es"
    archivar: bool = False
    carpeta_casos: Path = Path("bulonator-casos")
    buscador: Literal["auto", "nativo", "searxng", "brave", "tavily", "ninguno"] = "auto"
    concurrencia: int = Field(2, ge=1, description="agentes trabajando a la vez (con Ollama local, 1 o 2)")
    max_peticiones: int = Field(40, ge=1, description="peticiones al modelo como máximo en cada ejecución de un papel")
    max_tokens_caso: Optional[int] = Field(None, description="tokens totales como máximo en el caso (None: sin límite)")
    reintentos: int = Field(5, ge=0, description="reintentos de la salida cuando no supera la validación")
    salida: Literal["herramienta", "nativa", "texto"] = Field(
        "herramienta", description="cómo entrega cada papel su salida estructurada: llamando a una herramienta "
                                   "(lo habitual), con la salida JSON nativa del proveedor (en Ollama, el modelo queda "
                                   "obligado a seguir el esquema; útil con modelos locales pequeños) o como texto JSON")
    max_texto_herramienta: int = Field(6000, ge=500, description="caracteres de texto que devuelve leer en cada llamada")
    vision: bool = Field(True, description="enviar imágenes a los modelos (desactívalo si el modelo no las admite)")
    max_imagenes: int = Field(6, ge=0)
    temperatura: Optional[float] = 0.2
    max_tokens_respuesta: Optional[int] = Field(
        16384, ge=256, description="tokens como máximo en cada respuesta del modelo, razonamiento incluido: corta los "
                                    "bucles de generación")
    razonamiento: Optional[Literal["minimo", "bajo", "medio", "alto"]] = Field(
        None, description="cuánto razonan los modelos que razonan (gpt-oss, o3, Claude…); None: el del proveedor. "
                          "«bajo» acelera y ahorra contexto con modelos locales")
    timeout_peticion: Optional[float] = Field(
        600, gt=0, description="segundos como máximo por petición al modelo, espera en cola incluida (None: sin "
                                "límite)")
    permitir_red_privada: bool = Field(False, description="permitir URL de la red local (no recomendado en servicios)")
    guardar_conversaciones: bool = Field(
        False, description="guardar en <caso>/motor/ la conversación de cada papel (las que fallan se guardan siempre)")

    @field_validator("modelos")
    @classmethod
    def _papeles_conocidos(cls, v: dict) -> dict:
        desconocidos = set(v) - set(PAPELES) - {"defecto"}
        if desconocidos:
            raise ValueError(f"papeles desconocidos: {', '.join(sorted(desconocidos))} (válidos: {', '.join(PAPELES)})")
        if "defecto" not in v and not set(PAPELES) <= set(v):
            raise ValueError("indica un modelo «defecto» o uno para cada papel")
        return v

    def modelo(self, papel: str) -> Any:
        return self.modelos.get(papel) or self.modelos["defecto"]

    def nombre_modelo(self, papel: str) -> str:
        m = self.modelo(papel)
        if isinstance(m, str):
            return m
        return f"{getattr(m, 'system', '?')}:{getattr(m, 'model_name', type(m).__name__)}"

    def proveedor(self, papel: str) -> str:
        return self.nombre_modelo(papel).split(":", 1)[0]

    def busqueda_nativa(self, papel: str) -> bool:
        """¿Se usa la búsqueda web nativa del modelo en este papel?"""
        if self.buscador == "nativo":
            return True
        return self.buscador == "auto" and self.buscador_local() is None and \
            self.proveedor(papel) in CON_BUSQUEDA_NATIVA

    def buscador_local(self) -> Optional[str]:
        """Buscador propio que se usa para ``buscar`` (o None)."""
        if self.buscador in ("searxng", "brave", "tavily"):
            return self.buscador
        if self.buscador == "auto":
            from ..nucleo import buscador_configurado

            return buscador_configurado()
        return None

    @classmethod
    def desde_toml(cls, ruta) -> "Config":
        """Lee un archivo TOML. Ejemplo en ``docs/motor.md``; ``[modelos]`` es una tabla papel = modelo."""
        datos = tomllib.loads(Path(ruta).expanduser().read_text(encoding="utf-8"))
        for clave, valor in list(datos.items()):
            if isinstance(valor, str) and valor.startswith("$"):
                datos[clave] = os.environ.get(valor[1:], "")
        return cls(**datos)
