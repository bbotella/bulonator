#!/usr/bin/env python3
"""Lanzador de Bulonator para el plugin de Claude Code.

Ejecuta la línea de órdenes del paquete ``bulonator`` (mismos subcomandos y salida JSON). Busca el
paquete en este orden:

1. ``scripts/_vendor/``: la copia que deja ``install.sh`` junto a este archivo;
2. ``src/`` del repositorio: instalación como plugin o con ``install.sh --link``;
3. un paquete ``bulonator`` instalado con pip o uv.

Las referencias y plantillas que usa el paquete son las de este skill.
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent

for candidato in (AQUI / "_vendor", SKILL.parent.parent / "src"):
    if (candidato / "bulonator" / "cli.py").is_file():
        sys.path.insert(0, str(candidato))
        break

os.environ.setdefault("BULONATOR_REFS", str(SKILL / "references"))
os.environ.setdefault("BULONATOR_PLANTILLAS", str(SKILL / "templates"))
if (SKILL.parent.parent / "agents").is_dir():
    os.environ.setdefault("BULONATOR_AGENTES", str(SKILL.parent.parent / "agents"))

if sys.version_info < (3, 9):
    sys.exit("Bulonator necesita Python 3.9 o superior.")

try:
    from bulonator.cli import main
except ImportError as e:  # pragma: no cover - instalación incompleta
    sys.exit(f"No se encuentra el paquete bulonator ({e}). Reinstala con ./install.sh o instala el plugin.")

if __name__ == "__main__":
    sys.exit(main())
