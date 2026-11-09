"""``bulonator analizar``: el motor desde la línea de órdenes."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from .config import Config
from .proceso import CapturaVacia, Evento, PresupuestoAgotado, analizar


def configuracion(args) -> Config:
    """Configuración del archivo TOML (si se indica) con las opciones de la línea de órdenes encima."""
    base = Config.desde_toml(args.config).model_dump() if args.config else Config().model_dump()
    if args.modelo:
        base["modelos"] = {**{k: v for k, v in base["modelos"].items() if k != "defecto"}, "defecto": args.modelo}
    if args.auditor:
        base["modelos"]["auditor"] = args.auditor
    for clave in ("modo", "idioma", "buscador"):
        if getattr(args, clave, None):
            base[clave] = getattr(args, clave)
    if args.archivar:
        base["archivar"] = True
    if args.casos:
        base["carpeta_casos"] = Path(args.casos)
    return Config(**base)


def ejecutar(args, emit) -> int:
    config = configuracion(args)

    def progreso(e: Evento) -> None:
        if not args.silencioso:
            print(f"[{e.fase}] {e.mensaje}", file=sys.stderr, flush=True)

    try:
        caso = asyncio.run(analizar(args.entrada, config, al_progresar=progreso))
    except CapturaVacia as e:
        emit({"error": str(e), "caso": str(e.caso),
              "siguiente_paso": "consigue el texto, una captura de pantalla o el archivo y vuelve a analizarlo"})
        return 4
    except PresupuestoAgotado as e:
        emit({"error": f"presupuesto de tokens agotado: {e}"})
        return 5
    emit({"caso": str(caso.ruta), "aprobado": caso.aprobado, "validacion": {k: caso.validacion[k] for k in
                                                                            ("ok", "errores", "avisos")},
          "fallos": caso.fallos, "uso": caso.uso, "resultado": caso.resultado.model_dump()})
    return 0
