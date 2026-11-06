# Instalación y configuración

## 1. Requisitos

| Herramienta | ¿Obligatoria? | Para qué | Instalación |
|---|---|---|---|
| Claude Code | Sí | Ejecuta las skills y los agentes | <https://docs.claude.com/en/docs/claude-code/overview> |
| Python 3.9+ | Sí | `bulonator.py` (solo biblioteca estándar) | Incluido en macOS y Linux |
| yt-dlp | Muy recomendable | Vídeos de YouTube, X, TikTok, Instagram, Facebook… | `brew install yt-dlp` · `pipx install yt-dlp` |
| ffmpeg / ffprobe | Muy recomendable | Fotogramas, audio, ELA, metadatos de vídeo | `brew install ffmpeg` · `apt install ffmpeg` |
| exiftool | Opcional | Metadatos EXIF, XMP e IPTC completos (el script incluye un lector básico) | `brew install exiftool` · `apt install libimage-exiftool-perl` |
| whisper / mlx_whisper / whisper-cli | Opcional | Transcribir audios y notas de voz | `pipx install openai-whisper` · `pipx install mlx-whisper` (Apple Silicon) |
| c2patool | Opcional | Leer las credenciales de contenido C2PA | <https://github.com/contentauth/c2pa-rs> |
| Navegador MCP | Opcional | Búsqueda inversa de imágenes, webs con JavaScript, consultas en redes | Claude in Chrome, o un servidor MCP de Playwright |

Comprueba qué tienes disponible:

```bash
python3 skills/bulonator/scripts/bulonator.py deps
```

## 2. Instalar

### Como plugin (recomendado)

En Claude Code:

```text
/plugin marketplace add TU-USUARIO/bulonator
/plugin install bulonator@bulonator
```

Para actualizar: `/plugin marketplace update bulonator` y reinicia Claude Code.

### Con `install.sh` (skills y agentes de usuario)

```bash
./install.sh                    # copia a ~/.claude/skills y ~/.claude/agents
./install.sh --link             # enlaces simbólicos al repositorio (los cambios se aplican al instante)
./install.sh --dest ./mi-proyecto/.claude   # instalar solo en un proyecto (para compartirlo con un equipo vía git)
./install.sh --uninstall
```

Si ya existe una carpeta con el mismo nombre, el instalador la renombra con el sufijo `.bak-<fecha>` antes de instalar.

### Sin instalar (para probar o desarrollar)

```bash
claude --plugin-dir /ruta/a/bulonator
```

## 3. Permisos recomendados

Los agentes ejecutan `python3`, `yt-dlp`, `ffmpeg` y `curl`, y consultan la web. Para no tener que aprobar cada paso, añade estas reglas a `~/.claude/settings.json` (para todos tus proyectos) o a `.claude/settings.json` (solo para un proyecto):

```json
{
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(yt-dlp:*)",
      "Bash(ffmpeg:*)",
      "Bash(ffprobe:*)",
      "Bash(exiftool:*)",
      "Bash(curl:*)",
      "WebSearch",
      "WebFetch"
    ]
  }
}
```

- `Bash(python3:*)` y `Bash(curl:*)` son permisos amplios. Si prefieres aprobar a mano, omítelos: Bulonator funciona igual, solo que pedirá confirmación.
- El campo `allowed-tools` de las skills solo aplica a la conversación principal. Los subagentes usan las reglas de `settings.json`.
- No uses `--dangerously-skip-permissions`.

## 4. Variables de entorno opcionales

| Variable | Efecto |
|---|---|
| `GOOGLE_FACTCHECK_API_KEY` | `factcheck` consulta la [Fact Check Tools API](https://developers.google.com/fact-check/tools/api) (gratuita, requiere un proyecto de Google Cloud) |
| `SERPAPI_API_KEY` | `buscar-imagen` obtiene las coincidencias de Google Lens mediante [SerpAPI](https://serpapi.com) (de pago) |
| `BULONATOR_TRANSCRIBE_CMD` | Un comando de transcripción propio, por ejemplo `"whisper-ctranslate2 {audio} --output_dir {outdir} --output_format txt"` |
| `BULONATOR_WHISPER_SIZE` | El tamaño del modelo de `whisper` (por defecto `small`; `base` es más rápido) |
| `BULONATOR_WHISPER_MODEL` | La ruta del modelo `.bin` para `whisper-cli` (whisper.cpp) |

## 5. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` | Python de python.org en macOS: ejecuta `Install Certificates.command` en `/Applications/Python 3.x/` |
| `yt-dlp` falla con una plataforma | Actualízalo con `yt-dlp -U`, `brew upgrade yt-dlp` o `pipx upgrade yt-dlp`. Las plataformas cambian a menudo |
| No se lee un tuit | Los servicios sin sesión (fxtwitter, syndication) pueden fallar o la cuenta puede ser privada. Pega el texto o una captura de pantalla |
| Instagram o Facebook sin contenido | Exigen sesión. Aporta una captura de pantalla o el archivo |
| "Sin transcriptor" | Instala whisper o define `BULONATOR_TRANSCRIBE_CMD`. Mientras tanto, el audio queda como limitación |
| Los textos para X se pasan de 280 | El orquestador los mide con `contar`. Revisa que los enlaces no lleven espacios (cada URL cuenta 23) |
| No aparecen `/bulonator` ni los agentes | Reinicia Claude Code después de instalar. Con `install.sh`, comprueba que existen `~/.claude/skills/bulonator/SKILL.md` y `~/.claude/agents/bulonator-*.md` |
