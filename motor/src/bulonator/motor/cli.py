"""``bulonator analizar``: el motor desde la línea de órdenes."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from .config import Config
from .proceso import AnalisisFallido, CapturaVacia, Evento, ModeloNoDisponible, PresupuestoAgotado, analizar


def configuracion(args) -> Config:
    """Configuración del archivo TOML (si se indica) con las opciones de la línea de órdenes encima."""
    base = Config.desde_toml(args.config).model_dump() if args.config else Config().model_dump()
    if args.modelo:
        base["modelos"] = {**{k: v for k, v in base["modelos"].items() if k != "defecto"}, "defecto": args.modelo}
    if args.auditor:
        base["modelos"]["auditor"] = args.auditor
    for clave in ("modo", "idioma", "buscador", "salida", "razonamiento", "concurrencia"):
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

    def fallo(codigo: int, datos: dict) -> int:
        # El JSON va a la salida estándar (que a menudo se redirige a un archivo); el aviso, a la terminal
        if not args.silencioso:
            print(f"Error: {datos['error']}", file=sys.stderr, flush=True)
            if datos.get("siguiente_paso"):
                print(f"Siguiente paso: {datos['siguiente_paso']}", file=sys.stderr, flush=True)
        emit(datos)
        return codigo

    try:
        caso = asyncio.run(analizar(args.entrada, config, al_progresar=progreso))
    except CapturaVacia as e:
        return fallo(4, {"error": str(e), "caso": str(e.caso),
                         "siguiente_paso": "consigue el texto, una captura de pantalla o el archivo y vuelve a analizarlo"})
    except PresupuestoAgotado as e:
        return fallo(5, {"error": f"presupuesto de tokens agotado: {e}"})
    except ModeloNoDisponible as e:
        return fallo(6, {"error": str(e), "siguiente_paso": "revisa la configuración de los modelos (docs/motor.md)"})
    except AnalisisFallido as e:
        consejo = "prueba con un modelo más capaz para ese papel o con menos concurrencia"
        if "output retries" in str(e) and config.salida != "nativa":
            consejo = ("el modelo no ha entregado bien su salida estructurada: prueba con «--salida nativa» "
                       "(con Ollama, obliga al modelo a seguir el esquema) o con un modelo más capaz")
        conversaciones = sorted(str(p) for p in (Path(e.caso) / "motor").glob("*-fallo.json")) if e.caso else []
        return fallo(7, {"error": f"el análisis no ha podido terminar: {e}", "caso": str(e.caso),
                         "siguiente_paso": consejo, "conversaciones": conversaciones})
    emit({"caso": str(caso.ruta), "aprobado": caso.aprobado, "validacion": {k: caso.validacion[k] for k in
                                                                            ("ok", "errores", "avisos")},
          "fallos": caso.fallos, "uso": caso.uso, "resultado": caso.resultado.model_dump()})
    return 0
