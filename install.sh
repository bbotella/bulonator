#!/usr/bin/env bash
# Instala las skills y los agentes de Bulonator en Claude Code como componentes de usuario
# (por defecto en ~/.claude). Así quedan disponibles /bulonator, /verificar-dato y
# /verificar-multimedia en cualquier proyecto.
#
# Uso:
#   ./install.sh                 copia los archivos
#   ./install.sh --link          crea enlaces simbólicos al repositorio (para desarrollar)
#   ./install.sh --dest DIR      instala en DIR (por ejemplo ./mi-proyecto/.claude)
#   ./install.sh --uninstall     desinstala
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MODE="copy"
ACTION="install"
SKILLS=(bulonator verificar-dato verificar-multimedia)
AGENTS=(bulonator-captura bulonator-verificador bulonator-multimedia bulonator-origen bulonator-auditor)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link" ;;
    --dest) DEST="$2"; shift ;;
    --uninstall) ACTION="uninstall" ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $1 (usa --help)" >&2; exit 1 ;;
  esac
  shift
done

stamp="$(date +%Y%m%d-%H%M%S)"

# ¿El destino es nuestro (enlace al repositorio o copia de Bulonator)?
is_ours() {
  local target="$1" name="$2"
  if [[ -L "$target" ]]; then
    [[ "$(readlink "$target")" == "$REPO"/* ]] && return 0
    return 1
  fi
  if [[ -d "$target" && -f "$target/SKILL.md" ]]; then
    grep -q "^name: ${name}$" "$target/SKILL.md" && grep -q "bulonator" "$target/SKILL.md" && return 0
  fi
  if [[ -f "$target" ]]; then
    grep -q "^name: ${name}$" "$target" && return 0
  fi
  return 1
}

place() {
  local src="$1" target="$2" name="$3"
  if [[ -e "$target" || -L "$target" ]]; then
    if is_ours "$target" "$name"; then
      rm -rf "$target"
    else
      mv "$target" "$target.bak-$stamp"
      echo "  · ya existía $target: se ha renombrado a $(basename "$target").bak-$stamp"
    fi
  fi
  if [[ "$MODE" == "link" ]]; then
    ln -s "$src" "$target"
  else
    cp -R "$src" "$target"
  fi
}

if [[ "$ACTION" == "uninstall" ]]; then
  for s in "${SKILLS[@]}"; do
    t="$DEST/skills/$s"
    if [[ -e "$t" || -L "$t" ]] && is_ours "$t" "$s"; then rm -rf "$t"; echo "  − $t"; fi
  done
  for a in "${AGENTS[@]}"; do
    t="$DEST/agents/$a.md"
    if [[ -e "$t" || -L "$t" ]] && is_ours "$t" "$a"; then rm -f "$t"; echo "  − $t"; fi
  done
  echo "Bulonator desinstalado de $DEST."
  exit 0
fi

command -v python3 >/dev/null 2>&1 || { echo "Error: hace falta python3 (3.9 o superior)." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "Error: hace falta Python 3.9 o superior." >&2; exit 1; }

mkdir -p "$DEST/skills" "$DEST/agents"
echo "Instalando Bulonator en $DEST ($MODE)…"
for s in "${SKILLS[@]}"; do
  place "$REPO/skills/$s" "$DEST/skills/$s" "$s"
  echo "  + skills/$s"
done
for a in "${AGENTS[@]}"; do
  place "$REPO/agents/$a.md" "$DEST/agents/$a.md" "$a"
  echo "  + agents/$a.md"
done

echo
echo "Herramientas disponibles:"
python3 "$DEST/skills/bulonator/scripts/bulonator.py" deps | python3 -c '
import json, sys
d = json.load(sys.stdin)
for k, v in d["capacidades"].items():
    print("  " + ("ok " if v else "no ") + k)
if d["faltan"]:
    print("\nOpcionales que faltan:")
    for f in d["faltan"]:
        print("  - " + f)
    print("\n" + d["sugerencia_instalacion"])
' || echo "  (no se pudo ejecutar la comprobación de herramientas)"
echo
echo "Listo. Reinicia Claude Code y escribe:  /bulonator <enlace>"
echo "Permisos recomendados: docs/instalacion.md"
