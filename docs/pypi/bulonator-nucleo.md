# bulonator-nucleo

El **núcleo de [Bulonator](https://github.com/bbotella/bulonator)**: las herramientas que no usan modelos de lenguaje. Funciona con Python 3.9 o superior y **sin dependencias**.

- **Captura de contenido:** X/Twitter, Bluesky, Telegram, Mastodon, Reddit, vídeo (con yt-dlp) y webs, con el texto literal, los metadatos y la multimedia con su SHA-256. Hace copias en la Wayback Machine.
- **Fuentes oficiales:** BOE (legislación consolidada y sumario diario), INE (operaciones, tablas y datos), RDAP y whois, y verificaciones previas (Google Fact Check Tools).
- **Registro de fuentes:** `leer` abre una página o un documento y guarda su texto en el caso. `buscar` hace búsquedas con SearXNG, Brave o Tavily.
- **Análisis multimedia:** EXIF, XMP, IPTC, C2PA, indicios de IA en los metadatos, ELA, fotogramas, hoja de contactos y transcripción (con ffmpeg y whisper, si están instalados).
- **Validación de casos:** `validar` comprueba que cada URL citada se abrió, que cada cita literal está en la fuente guardada, que cada `[n]` remite a una evidencia y que la calificación es coherente en todos los textos. `resultado` genera `resultado.json`.

```bash
pip install bulonator-nucleo
bulonator capturar https://x.com/usuario/status/123 --dir caso --archivar
bulonator boe "ingreso mínimo vital"
bulonator validar caso
```

```python
from bulonator.nucleo import crear_caso, leer, ine_datos, validar

caso = crear_caso("paro juvenil")["caso"]
ine_datos("65334", nult=4, caso=caso)       # cada dato queda registrado y se puede citar
validar(caso)
```

**¿Quieres el análisis completo con modelos de lenguaje?** Instala [`bulonator`](https://pypi.org/project/bulonator/), que incluye este paquete y el motor (Python 3.11 o superior).

Licencia MIT. La documentación completa está en <https://github.com/bbotella/bulonator>.
