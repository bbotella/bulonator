"""Línea de órdenes de Bulonator. Todos los subcomandos imprimen JSON por la salida estándar.

Subcomandos del núcleo (sin dependencias, Python 3.9 o superior):
  deps            Comprueba qué herramientas externas hay disponibles.
  caso            Crea la carpeta de un caso nuevo y devuelve su ruta.
  capturar        Captura una URL (X/Twitter, Bluesky, Telegram, Mastodon, Reddit, YouTube, TikTok,
                  Instagram, Facebook, webs de noticias...), un archivo o un texto.
  leer            Abre una página o documento, guarda su texto en el caso y lo registra.
  buscar          Búsqueda web con SearXNG, Brave o Tavily (según la configuración).
  media           Analiza una imagen, vídeo o audio: metadatos, marcas de IA/C2PA, ELA,
                  fotogramas clave, hoja de contactos, audio y transcripción.
  wayback         Consulta (y opcionalmente solicita) copias en la Wayback Machine.
  dominio         Datos de registro de un dominio (RDAP o whois).
  boe             Busca legislación consolidada en el BOE o lista el sumario de un día.
  ine             Busca operaciones estadísticas, tablas y datos del INE.
  buscar-imagen   Enlaces de búsqueda inversa de una imagen (y resultados con SerpAPI si hay clave).
  factcheck       Busca verificaciones previas (Google Fact Check Tools si hay clave).
  contar          Longitud de los textos para redes (reglas de X: enlaces = 23, emojis = 2).
  validar         Comprobaciones mecánicas de un caso (evidencias, citas, fuentes, calificación).
  resultado       Monta resultado.json a partir de los documentos del caso.

Con el motor (paquete «bulonator», Python 3.11 o superior):
  analizar        Analiza un enlace, archivo o texto de principio a fin con modelos de lenguaje.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from . import nucleo as n
from .nucleo.util import HttpError


def emit(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _caso(args):
    return getattr(args, "caso", None)


def cmd_deps(args) -> int:
    emit(n.deps())
    return 0


def cmd_caso(args) -> int:
    emit(n.crear_caso(args.entrada, args.base))
    return 0


def cmd_capturar(args) -> int:
    res = n.capturar(args.entrada, args.dir, sin_media=args.sin_media, max_media=args.max_media,
                     sin_archivo=args.sin_archivo, archivar=args.archivar, nombre=args.nombre)
    emit(n.resumen_captura(res, args.max_texto))
    return 0


def cmd_leer(args) -> int:
    emit(n.leer(args.url, args.caso, max_texto=args.max_texto, desde_archivo=args.desde_archivo,
                titulo=args.titulo))
    return 0


def cmd_buscar(args) -> int:
    dominios = [d for d in (args.dominios or "").split(",") if d.strip()]
    emit(n.buscar(args.consulta, dominios, args.max, args.buscador, args.idioma, caso=_caso(args)))
    return 0


def cmd_media(args) -> int:
    try:
        emit(n.analizar_media(args.archivo, args.dir, args.fotogramas, args.idioma))
    except FileNotFoundError as e:
        emit({"error": str(e)})
        return 1
    return 0


def cmd_wayback(args) -> int:
    emit(n.wayback(args.url, args.guardar, caso=_caso(args)))
    return 0


def cmd_dominio(args) -> int:
    emit(n.dominio(args.dominio, caso=_caso(args)))
    return 0


def cmd_boe(args) -> int:
    if args.sumario:
        emit(n.boe_sumario(args.sumario, args.texto, args.limite, caso=_caso(args)))
        return 0
    if not args.texto:
        emit({"error": "indica un texto a buscar o --sumario AAAAMMDD"})
        return 1
    emit(n.boe(args.texto, args.desde, args.hasta, args.limite, caso=_caso(args)))
    return 0


def cmd_ine(args) -> int:
    if args.datos:
        emit(n.ine_datos(args.datos, args.nult, args.texto, args.limite, caso=_caso(args)))
    elif args.tablas:
        emit(n.ine_tablas(args.tablas, args.texto, args.limite))
    elif args.texto:
        emit(n.ine_operaciones(args.texto, args.limite))
    else:
        emit({"error": "indica un texto, --tablas CODIGO_OPERACION o --datos ID_TABLA"})
        return 1
    return 0


def cmd_buscar_imagen(args) -> int:
    emit(n.buscar_imagen(args.url, args.limite))
    return 0


def cmd_factcheck(args) -> int:
    emit(n.factcheck(args.texto, args.idioma, args.limite, caso=_caso(args)))
    return 0


def cmd_contar(args) -> int:
    texto = Path(args.archivo).read_text(encoding="utf-8") if args.archivo else sys.stdin.read()
    emit(n.contar(texto, args.bloques))
    return 0


def cmd_validar(args) -> int:
    res = n.validar(args.caso)
    emit(res)
    return 0 if res["ok"] else 1


def cmd_resultado(args) -> int:
    res = n.escribir_resultado(args.caso, calificacion=args.calificacion, subtipo=args.subtipo,
                               confianza=args.confianza, dictamen=args.dictamen, rondas=args.rondas,
                               idioma=args.idioma, cierre=args.cierre)
    problemas = n.comprobar_resultado(res)
    emit({"archivo": str(Path(args.caso).expanduser().resolve() / "resultado.json"), "problemas": problemas,
          "resultado": res})
    return 0 if not problemas else 1


def cmd_analizar(args) -> int:
    try:
        from .motor.cli import ejecutar
    except ImportError as e:
        emit({"error": "el motor no está instalado o necesita Python 3.11 o superior",
              "detalle": str(e), "instalacion": "pip install bulonator  (o ./install.sh --motor)"})
        return 3
    return ejecutar(args, emit)


def _con_caso(s, obligatorio=False):
    s.add_argument("--caso", required=obligatorio,
                   help="carpeta del caso: registra lo que devuelve la herramienta para poder citarlo")


def build_parser() -> argparse.ArgumentParser:
    prog = os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else "bulonator"
    p = argparse.ArgumentParser(prog=prog, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("deps", help="comprueba herramientas externas")
    s.set_defaults(func=cmd_deps)

    s = sub.add_parser("caso", help="crea la carpeta de un caso")
    s.add_argument("entrada", help="URL, ruta o texto (se usa para nombrar la carpeta)")
    s.add_argument("--base", default="bulonator-casos", help="carpeta base (por defecto ./bulonator-casos)")
    s.set_defaults(func=cmd_caso)

    s = sub.add_parser("capturar", help="captura una URL, archivo local o texto")
    s.add_argument("entrada")
    s.add_argument("--dir", required=True, help="carpeta del caso")
    s.add_argument("--sin-media", action="store_true", help="no descargar imágenes ni vídeos")
    s.add_argument("--max-media", type=int, default=8, help="máximo de imágenes de una página web")
    s.add_argument("--sin-archivo", action="store_true", help="no consultar la Wayback Machine")
    s.add_argument("--archivar", action="store_true", help="solicitar una copia nueva en la Wayback Machine")
    s.add_argument("--max-texto", type=int, default=6000, help="caracteres de texto a mostrar en la salida")
    s.add_argument("--nombre", help="nombre para una captura secundaria (p. ej. 'tuit-incrustado'): "
                                    "se guarda en <nombre>.json sin sobrescribir captura.json")
    s.set_defaults(func=cmd_capturar)

    s = sub.add_parser("leer", help="abre una página o documento y guarda su texto en el caso")
    s.add_argument("url")
    _con_caso(s, obligatorio=True)
    s.add_argument("--max-texto", type=int, default=4000, help="caracteres de texto a mostrar en la salida")
    s.add_argument("--desde-archivo", help="registra el texto de este archivo como obtenido de la URL "
                                           "(navegador, PDF leído a mano)")
    s.add_argument("--titulo", help="título del documento (opcional)")
    s.set_defaults(func=cmd_leer)

    s = sub.add_parser("buscar", help="búsqueda web (SearXNG, Brave o Tavily)")
    s.add_argument("consulta")
    s.add_argument("--dominios", help="dominios separados por comas (p. ej. boe.es,ine.es)")
    s.add_argument("--max", type=int, default=10, help="número máximo de resultados")
    s.add_argument("--buscador", choices=["searxng", "brave", "tavily"], help="buscador (por defecto, el configurado)")
    s.add_argument("--idioma", default="es")
    _con_caso(s)
    s.set_defaults(func=cmd_buscar)

    s = sub.add_parser("media", help="analiza una imagen, vídeo o audio")
    s.add_argument("archivo")
    s.add_argument("--dir", help="carpeta de salida (por defecto <carpeta del archivo>/analisis/<nombre>)")
    s.add_argument("--fotogramas", type=int, default=12, help="número de fotogramas uniformes y de escena")
    s.add_argument("--idioma", help="idioma del audio para la transcripción (es, en, ca...)")
    s.set_defaults(func=cmd_media)

    s = sub.add_parser("wayback", help="consulta copias en la Wayback Machine")
    s.add_argument("url")
    s.add_argument("--guardar", action="store_true", help="solicitar una copia nueva")
    _con_caso(s)
    s.set_defaults(func=cmd_wayback)

    s = sub.add_parser("dominio", help="datos de registro de un dominio")
    s.add_argument("dominio", help="dominio o URL")
    _con_caso(s)
    s.set_defaults(func=cmd_dominio)

    s = sub.add_parser("boe", help="busca en el BOE")
    s.add_argument("texto", nargs="?", help="palabras del título (sintaxis Lucene: AND, OR, comillas)")
    s.add_argument("--desde", help="AAAAMMDD")
    s.add_argument("--hasta", help="AAAAMMDD")
    s.add_argument("--sumario", help="AAAAMMDD: lista las disposiciones publicadas ese día")
    s.add_argument("--limite", type=int, default=15)
    _con_caso(s)
    s.set_defaults(func=cmd_boe)

    s = sub.add_parser("ine", help="busca operaciones, tablas y datos del INE")
    s.add_argument("texto", nargs="?", help="palabras a buscar en el nombre")
    s.add_argument("--tablas", metavar="CODIGO_OPERACION", help="lista las tablas de una operación (p. ej. EPA, IPC)")
    s.add_argument("--datos", metavar="ID_TABLA", help="descarga los últimos datos de una tabla")
    s.add_argument("--nult", type=int, default=5, help="número de periodos más recientes")
    s.add_argument("--limite", type=int, default=25)
    _con_caso(s)
    s.set_defaults(func=cmd_ine)

    s = sub.add_parser("buscar-imagen", help="búsqueda inversa de imagen")
    s.add_argument("url", help="URL pública de la imagen")
    s.add_argument("--limite", type=int, default=15)
    s.set_defaults(func=cmd_buscar_imagen)

    s = sub.add_parser("contar", help="longitud de textos para redes (reglas de X)")
    s.add_argument("archivo", nargs="?", help="archivo de texto (por defecto, la entrada estándar)")
    s.add_argument("--bloques", action="store_true",
                   help="cuenta por separado cada bloque ```text ... ``` del archivo (p. ej. publicacion.md)")
    s.set_defaults(func=cmd_contar)

    s = sub.add_parser("factcheck", help="busca verificaciones previas")
    s.add_argument("texto")
    s.add_argument("--idioma", default="es")
    s.add_argument("--limite", type=int, default=10)
    _con_caso(s)
    s.set_defaults(func=cmd_factcheck)

    s = sub.add_parser("validar", help="comprobaciones mecánicas de un caso")
    s.add_argument("caso", help="carpeta del caso")
    s.set_defaults(func=cmd_validar)

    s = sub.add_parser("resultado", help="monta resultado.json a partir de los documentos del caso")
    s.add_argument("caso", help="carpeta del caso")
    s.add_argument("--calificacion", required=True, help="FALSO, ALERTA, CONTEXTO, VERDADERO, NO VERIFICABLE o SIN VEREDICTO")
    s.add_argument("--subtipo")
    s.add_argument("--confianza", required=True, choices=["ALTA", "MEDIA", "BAJA"])
    s.add_argument("--dictamen", required=True, choices=["PALANTE", "CAMBIOS", "VETO"],
                   help="dictamen de la última ronda de auditoría")
    s.add_argument("--rondas", type=int, required=True, help="rondas de auditoría realizadas")
    s.add_argument("--cierre", action="store_true",
                   help="se aplicó la regla de cierre (sin PALANTE tras la última ronda, flujo.md)")
    s.add_argument("--idioma", default="es")
    s.set_defaults(func=cmd_resultado)

    s = sub.add_parser("analizar", help="análisis completo con modelos de lenguaje (paquete bulonator)")
    s.add_argument("entrada", help="URL, ruta a imagen/vídeo/audio o texto entre comillas")
    s.add_argument("--config", help="archivo TOML de configuración (ver docs/motor.md)")
    s.add_argument("--modelo", help="modelo por defecto para todos los papeles (p. ej. ollama:gpt-oss:20b)")
    s.add_argument("--auditor", help="modelo del auditor (recomendado: de otro proveedor)")
    s.add_argument("--modo", choices=["rapido", "normal", "profundo"])
    s.add_argument("--idioma", help="idioma de los textos para redes (es, ca, gl, eu, en)")
    s.add_argument("--archivar", action="store_true", help="solicitar copias nuevas en la Wayback Machine")
    s.add_argument("--casos", help="carpeta donde se crean los casos (por defecto ./bulonator-casos)")
    s.add_argument("--buscador", choices=["searxng", "brave", "tavily", "nativo"])
    s.add_argument("--silencioso", action="store_true", help="no mostrar el progreso por la salida de errores")
    s.set_defaults(func=cmd_analizar)
    return p


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HttpError as e:
        emit({"error": str(e)})
        return 2
    except (ValueError, FileNotFoundError) as e:
        emit({"error": str(e)})
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
