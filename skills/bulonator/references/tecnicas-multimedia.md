# Verificación de imágenes, vídeos y audios

Todo se ordena según los cinco pilares de First Draft:

| Pilar | Pregunta |
|---|---|
| **Procedencia** | ¿Es el original o una copia, un recorte o una captura? |
| **Fuente** | ¿Quién lo grabó o creó? |
| **Fecha** | ¿Cuándo se grabó o creó? |
| **Lugar** | ¿Dónde se grabó? |
| **Motivación** | ¿Por qué se grabó y por qué se difunde ahora? |

La conclusión de cada elemento será una de estas: `auténtico-en-su-contexto`, `descontextualizado`, `manipulado`, `generado-con-IA` o `no-determinado`.

## 1. Análisis técnico automático

```bash
python3 <SCRIPT> media <archivo> [--fotogramas 12] [--idioma es]
```

El comando genera, en `media/analisis/<nombre>/`:

- `analisis.json`: huella SHA-256, dimensiones, metadatos EXIF, XMP e IPTC, cadenas de generadores de IA o de C2PA encontradas en los metadatos, y etiquetas del contenedor de vídeo (`creation_time`, `encoder`).
- `ela.png`, solo para JPEG: el análisis de nivel de error. Es una señal débil.
- `fotogramas/uniforme_XX.jpg` y `fotogramas/escena_XX.jpg`: fotogramas repartidos a lo largo del vídeo y en los cambios de plano.
- `hoja_de_contactos.jpg`: un resumen visual del vídeo.
- `audio.wav` y, si hay un transcriptor instalado, la transcripción.

Ábrelos con `Read`, que acepta imágenes. Así ves los fotogramas.

### Cómo interpretar los metadatos

- **Las redes sociales y la mensajería borran el EXIF.** Que no haya EXIF no prueba nada.
- Si hay EXIF con fecha, cámara o GPS, es una pista sobre el original, pero se puede editar. Contrástala con otras pruebas.
- `Software` o `CreatorTool` (Photoshop, Canva, Snapseed) indican que el archivo pasó por ese programa, no que se manipulara el contenido.
- **IPTC `DigitalSourceType`** igual a `trainedAlgorithmicMedia` indica que el generador declara que es IA. `compositeWithTrainedAlgorithmicMedia` indica una edición con IA.
- **C2PA (Content Credentials)**: es un manifiesto firmado con el historial del archivo. Compruébalo en <https://contentcredentials.org/verify> (requiere navegador) o con `c2patool` si está instalado.
- En el vídeo, `creation_time` lo reescriben a menudo las plataformas al recodificar. Un `encoder` como `Lavf` (ffmpeg) indica recodificación.

## 2. Observación visual (lo que tú ves)

Describe de forma objetiva, sin interpretar:

- **Texto visible:** carteles, rótulos, matrículas (nunca las publiques), escaparates, idioma, prefijos telefónicos y dominios.
- **Marcas de agua y rótulos de televisión:** apuntan al emisor original.
- **Elementos fechables:** modelos de coche, móviles, uniformes, carteles de eventos, obras, la estación del año (vegetación, ropa) y el tiempo atmosférico.
- **Elementos localizables:** edificios singulares, montañas, costa, señales de tráfico, mobiliario urbano, el lado por el que se circula y la vegetación.
- **Sombras:** su dirección y su longitud permiten estimar la hora (con SunCalc, <https://www.suncalc.org>).

## 3. Búsqueda inversa: encontrar la primera aparición

La búsqueda inversa es la prueba más potente contra la descontextualización.

1. Con la URL pública de la imagen ejecuta `python3 <SCRIPT> buscar-imagen "<url>"`, que devuelve enlaces a Google Lens, Bing, Yandex y TinEye. Con `SERPAPI_API_KEY` definida, devuelve además las coincidencias de Google Lens.
2. Si hay un navegador disponible (herramientas MCP de navegador como Claude in Chrome o Playwright), abre esos buscadores, o súbeles el fotograma, y busca la aparición **más antigua**. TinEye permite ordenar por fecha. Yandex funciona bien con caras y paisajes, y Google Lens con objetos y lugares. Respeta los CAPTCHA: no intentes saltarlos.
3. Si no hay navegador, haz búsquedas con `WebSearch` usando la descripción visual más el texto visible más las palabras clave del bulo, en varios idiomas, y prueba fechas candidatas. Busca también en las webs de los verificadores con la descripción de la imagen.
4. Con vídeos, repite la búsqueda con 2 o 3 fotogramas distintivos.
5. Si la búsqueda inversa no se ha podido hacer, dilo como **limitación** y deja los enlaces para que la persona la haga.

Una coincidencia anterior a la fecha que alega el bulo, con otro lugar u otro contexto, documenta que es FALSO (`descontextualizado`). Registra la URL, la fecha y el título de esa primera aparición como evidencia.

## 4. Señales de manipulación

- Sombras, reflejos o iluminación incoherentes con el resto de la escena.
- Bordes recortados, zonas clonadas (patrones repetidos) o líneas rectas deformadas junto a una zona editada.
- Texto añadido con otra tipografía, o con otro grado de compresión o nitidez.
- En el ELA, una zona mucho más brillante o con una textura distinta del resto (bordes y texto brillan siempre).
- **Capturas de tuits o de titulares falsos:** comprueba que la publicación existe (con `capturar` sobre la URL de la cuenta o del medio, en la Wayback Machine o buscando el titular en la web del medio). Revisa también si el diseño de la interfaz, la tipografía, el formato de fecha y las métricas coinciden con la plataforma en esa época.
- **Vídeo:** cortes bruscos, saltos de audio, cambios en el ruido de fondo, labios que no sincronizan, velocidad alterada o un audio que no es de esa escena.

## 5. Contenido generado o alterado con IA

Las señales visuales son orientativas. Los detectores automáticos fallan a menudo, así que **nunca los uses como prueba única**.

- **Imagen:** manos y dedos, dientes, orejas y pendientes, texto ilegible o inventado, objetos fundidos, simetrías imposibles, piel excesivamente lisa, fondos incoherentes y logotipos deformados.
- **Vídeo:** física imposible, objetos que aparecen o desaparecen, rostros que cambian entre fotogramas y marcas de agua de generadores (Sora, Veo, Kling, Grok, Meta AI…), a veces recortadas o difuminadas.
- **Voz:** prosodia plana, respiración ausente o artificial, pronunciación extraña de nombres propios, e intervenciones que no constan en ninguna grabación original.
- **Pruebas de origen que sí permiten concluir:**
  - metadatos IPTC o C2PA de IA;
  - la marca de agua del generador;
  - la primera aparición en una cuenta que publica imágenes de IA, o en la web de un generador;
  - el autor reconoce que lo hizo con IA;
  - la persona supuestamente grabada no estuvo allí según fuentes fiables;
  - el detector SynthID de Google, cuando está disponible (<https://deepmind.google/models/synthid/>).

Sin una prueba de origen, la conclusión es "presenta indicios de haber sido generada con IA" y la calificación ALERTA (ver `calificaciones.md`).

## 6. Geolocalización y cronolocalización

- Compara la imagen con Google Maps o Street View, OpenStreetMap (<https://www.openstreetmap.org>) o Google Earth (<https://earth.google.com>). Si el usuario tiene navegador, úsalo. Si no, busca fotos del lugar candidato con `WebSearch`.
- Anota las coordenadas y los elementos coincidentes, al menos tres independientes, como evidencia de tipo `herramienta`.
- Para la fecha, compara con el tiempo que hacía en esa fecha (AEMET o Meteostat, <https://meteostat.net>), con eventos verificables (obras, carteles, fiestas) y con la posición del sol.

## 7. Audio, incluidas las notas de voz de WhatsApp

- Transcribe con `media`. Si no hay transcriptor, indícalo y pide al usuario la transcripción, o los subtítulos si es un vídeo de YouTube (`capturar` los descarga si existen).
- Identifica quién dice ser la persona que habla, de qué fuente dice tener la información y qué afirmaciones verificables hace. Esas afirmaciones van al verificador.
- Busca frases literales de la transcripción entre comillas: los audios virales suelen estar ya desmentidos.

## 8. Herramientas externas útiles (manuales)

| Herramienta | Uso |
|---|---|
| InVID-WeVerify, extensión de navegador <https://www.invid-project.eu/tools-and-services/invid-verification-plugin/> | Fotogramas, búsqueda inversa y metadatos de vídeo |
| Forensically <https://29a.ch/photo-forensics/> | ELA, clonado, ruido |
| FotoForensics <https://fotoforensics.com> | ELA y metadatos |
| Content Credentials <https://contentcredentials.org/verify> | C2PA |
| SunCalc <https://www.suncalc.org> | Posición del sol |
| Kit OSINT de Bellingcat <https://bellingcat.gitbook.io/toolkit> | Catálogo de herramientas |
