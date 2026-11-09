# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). El proyecto sigue [SemVer](https://semver.org/lang/es/).

## [1.1.0] - 2026-11-09

### Añadido

- **Dos paquetes de Python** que se importan como `bulonator` (la orden se llama igual):
  - `bulonator-nucleo` (`pyproject.toml`), sin dependencias y con Python 3.9 o superior: las herramientas del antiguo script, ahora como funciones de librería (`bulonator.nucleo`), y la metodología;
  - `bulonator` (`motor/pyproject.toml`), Python 3.11 o superior, que depende del anterior (`pip install bulonator` lo trae todo). Es el motor, `bulonator.motor`: el análisis completo con Pydantic AI y cualquier modelo (Ollama, OpenAI, Gemini, Anthropic…). Admite un modelo por papel, `bulonator analizar`, `analizar()` y `analizar_sync()`, eventos de progreso, presupuesto de tokens y herramientas reutilizables. Ver `docs/motor.md`.
- `leer`: abre una fuente, guarda su texto en `evidencias/paginas/` y la registra. `buscar`: búsqueda web con SearXNG, Brave o Tavily, anotada en `evidencias/busquedas.jsonl`.
- `validar`: comprobaciones mecánicas del caso. Cada URL citada se abrió, cada cita literal está en la fuente guardada, `[n]` ↔ `E-…`, la calificación es coherente, la confianza está permitida y los textos caben en X.
- `resultado`: `resultado.json`, el resumen del caso para otros programas, igual en Claude Code y en el motor.
- `--caso` en `boe`, `ine`, `wayback`, `dominio` y `factcheck`, para registrar lo que devuelven y poder citarlo.
- `references/reglas.json` (cifras y listas cerradas), `references/flujo.md` (fases comunes) y `references/herramientas-claude.md` (capacidades en Claude Code).
- `install.sh --motor` y `--solo-motor`.

### Cambiado

- **Metodología sin repeticiones.** Cada regla tiene un identificador (`[EV-4]`, `[CAL-9]`…) y se define en un solo archivo. Los agentes y las skills la citan.
- **Agentes neutros.** Sus secciones compartidas nombran capacidades, no herramientas de Claude Code.
- `skills/bulonator/scripts/bulonator.py` es ahora un lanzador del paquete, con los mismos subcomandos. `install.sh` copia el núcleo junto a él: la instalación y el uso en Claude Code no cambian.
- Se bloquean por defecto las URL de la red local y de la propia máquina, incluidas las redirecciones, y los esquemas que no son http(s).

## [1.0.0] - 2026-11-06

### Añadido

- Skill `/bulonator <enlace|archivo|texto>`. Orquesta las fases de preparación, captura, desglose, investigación en paralelo, deliberación, auditoría y entrega. Opciones: `--rapido`, `--profundo`, `--archivar` e `--idioma`.
- Skills `/verificar-dato` y `/verificar-multimedia`.
- Agentes `bulonator-captura`, `bulonator-verificador`, `bulonator-multimedia`, `bulonator-origen` y `bulonator-auditor`.
- Script `bulonator.py`, solo con la biblioteca estándar:
  - captura de X/Twitter, Bluesky, Telegram, Mastodon, Reddit, plataformas de vídeo (con yt-dlp) y webs;
  - análisis multimedia: EXIF, XMP, IPTC, C2PA, indicios de IA en metadatos, ELA, fotogramas, hoja de contactos, audio y transcripción;
  - Wayback Machine, RDAP y whois;
  - BOE: legislación consolidada y sumario diario;
  - INE: operaciones, tablas y datos;
  - búsqueda inversa (SerpAPI opcional) y Google Fact Check Tools (opcional);
  - recuento de caracteres según las reglas de X.
- Referencias metodológicas basadas en Maldita.es, IFCN, EFCSN, First Draft, SIFT y el análisis de propagación al estilo de Pandemia Digital.
- Catálogos de fuentes oficiales: España (estatal y autonómica), UE, organismos internacionales y América Latina.
- Plantillas de informe, textos para redes y desglose.
- Instalación como plugin o marketplace, `install.sh`, pruebas, CI y plantillas de issues.
