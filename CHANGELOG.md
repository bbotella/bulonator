# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). El proyecto sigue [SemVer](https://semver.org/lang/es/).

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
