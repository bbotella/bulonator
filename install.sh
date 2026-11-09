#!/usr/bin/env bash
# Instala las skills y los agentes de Bulonator en Claude Code como componentes de usuario
# (por defecto en ~/.claude). Así quedan disponibles /bulonator, /verificar-dato y
# /verificar-multimedia en cualquier proyecto. Opcionalmente instala también el motor
# (la orden «bulonator analizar», que funciona con Ollama, OpenAI, Gemini o Anthropic).
#
# Uso:
#   ./install.sh                 copia los archivos para Claude Code
#   ./install.sh --link          crea enlaces simbólicos al repositorio (para desarrollar)
#   ./install.sh --dest DIR      instala en DIR (por ejemplo ./mi-proyecto/.claude)
#   ./install.sh --motor         además, instala la orden «bulonator» con el motor (uv o pipx)
#   ./install.sh --solo-motor    instala solo el motor, sin tocar Claude Code
#   ./install.sh --uninstall     desinstala (con --motor o --solo-motor, también el motor)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MODE="copy"
ACTION="install"
CLAUDE=1
MOTOR=0
SKILLS=(bulonator verificar-dato verificar-multimedia)
AGENTS=(bulonator-captura bulonator-verificador bulonator-multimedia bulonator-origen bulonator-auditor)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link" ;;
    --dest) DEST="$2"; shift ;;
    --motor) MOTOR=1 ;;
    --solo-motor) MOTOR=1; CLAUDE=0 ;;
    --uninstall) ACTION="uninstall" ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

# Copia el paquete junto al lanzador del skill (scripts/_vendor/bulonator). Con --link no hace falta:
# el lanzador sigue el enlace hasta el repositorio y usa src/ directamente.
vendor_core() {
  local vendor="$DEST/skills/bulonator/scripts/_vendor"
  [[ "$MODE" == "link" ]] && return 0
  rm -rf "$vendor"
  mkdir -p "$vendor"
  cp -R "$REPO/src/bulonator" "$vendor/bulonator"
  find "$vendor" -name "__pycache__" -type d -prune -exec rm -rf {} +
  echo "  + skills/bulonator/scripts/_vendor/bulonator (núcleo, sin dependencias)"
}

motor_tool() {
  # Devuelve el instalador disponible: uv (preferido) o pipx
  if command -v uv >/dev/null 2>&1; then echo uv; elif command -v pipx >/dev/null 2>&1; then echo pipx; fi
}

install_motor() {
  local tool
  tool="$(motor_tool)"
  echo
  echo "Instalando el motor (orden «bulonator», Python 3.11 o superior)…"
  case "$tool" in
    uv)
      if [[ "$MODE" == "link" ]]; then
        uv tool install --force --python ">=3.11" --editable "$REPO[motor]"
      else
        uv tool install --force --python ">=3.11" "$REPO[motor]"
      fi ;;
    pipx)
      local py
      py="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || true)"
      [[ -n "$py" ]] || { echo "Error: pipx necesita Python 3.11 o superior (python3.11, 3.12 o 3.13)." >&2; return 1; }
      if [[ "$MODE" == "link" ]]; then
        pipx install --force --python "$py" --editable "$REPO[motor]"
      else
        pipx install --force --python "$py" "$REPO[motor]"
      fi ;;
    *)
      echo "No se ha encontrado uv ni pipx. Instala uno de los dos (https://docs.astral.sh/uv/) o, en tu entorno:"
      echo "  pip install \"$REPO[motor]\""
      return 1 ;;
  esac
  echo "Motor instalado. Prueba:  bulonator analizar --help   (configuración: docs/motor.md)"
}

uninstall_motor() {
  local tool
  tool="$(motor_tool)"
  case "$tool" in
    uv) uv tool uninstall bulonator 2>/dev/null && echo "  − motor (uv tool)" || true ;;
    pipx) pipx uninstall bulonator 2>/dev/null && echo "  − motor (pipx)" || true ;;
  esac
}

if [[ "$ACTION" == "uninstall" ]]; then
  if [[ "$CLAUDE" == 1 ]]; then
    for s in "${SKILLS[@]}"; do
      t="$DEST/skills/$s"
      if [[ -e "$t" || -L "$t" ]] && is_ours "$t" "$s"; then rm -rf "$t"; echo "  − $t"; fi
    done
    for a in "${AGENTS[@]}"; do
      t="$DEST/agents/$a.md"
      if [[ -e "$t" || -L "$t" ]] && is_ours "$t" "$a"; then rm -f "$t"; echo "  − $t"; fi
    done
    echo "Bulonator desinstalado de $DEST."
  fi
  [[ "$MOTOR" == 1 ]] && uninstall_motor
  exit 0
fi

command -v python3 >/dev/null 2>&1 || { echo "Error: hace falta python3 (3.9 o superior)." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "Error: hace falta Python 3.9 o superior." >&2; exit 1; }

if [[ "$CLAUDE" == 1 ]]; then
  mkdir -p "$DEST/skills" "$DEST/agents"
  echo "Instalando Bulonator en $DEST ($MODE)…"
  for s in "${SKILLS[@]}"; do
    place "$REPO/skills/$s" "$DEST/skills/$s" "$s"
    echo "  + skills/$s"
  done
  vendor_core
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
fi

if [[ "$MOTOR" == 1 ]]; then
  install_motor
fi
