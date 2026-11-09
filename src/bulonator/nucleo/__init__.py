"""Núcleo de Bulonator: herramientas sin dependencias externas (Python 3.9 o superior).

Todas las funciones devuelven diccionarios serializables en JSON. Las que reciben ``caso`` registran
en la carpeta del caso lo que han abierto, para que ``validar`` pueda comprobar las evidencias.
"""
from .archivo_web import wayback, wayback_info, wayback_save
from .busqueda import buscador_configurado, buscar
from .captura import capturar, detect_platform, resumen_captura, texto_de_captura
from .caso import RegistroPaginas, busquedas, crear_caso, normalizar_url, registrar_busqueda
from .datos import Metodologia, metodologia
from .entorno import deps
from .fuentes import boe, boe_sumario, buscar_imagen, dominio, factcheck, ine_datos, ine_operaciones, ine_tablas
from .lectura import leer
from .multimedia import analizar_media
from .red import comprobar_destino, permitir_red_privada
from .reglas import reglas
from .resultado import comprobar_resultado, construir_resultado, escribir_resultado
from .texto import contar, longitud, x_weight
from .util import HttpError
from .validacion import validar

__all__ = [
    "HttpError", "Metodologia", "RegistroPaginas", "analizar_media", "boe", "boe_sumario", "buscador_configurado",
    "buscar", "buscar_imagen", "busquedas", "capturar", "comprobar_destino", "comprobar_resultado",
    "construir_resultado", "contar", "crear_caso", "deps", "detect_platform", "dominio", "escribir_resultado",
    "factcheck", "ine_datos", "ine_operaciones", "ine_tablas", "leer", "longitud", "metodologia",
    "normalizar_url", "permitir_red_privada", "registrar_busqueda", "reglas", "resumen_captura",
    "texto_de_captura", "validar", "wayback", "wayback_info", "wayback_save", "x_weight",
]
