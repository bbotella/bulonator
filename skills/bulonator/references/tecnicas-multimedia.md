# Verificación de imágenes, vídeos y audios

Todo se ordena según los cinco pilares de First Draft:

| Pilar | Pregunta |
|---|---|
| **Procedencia** | ¿Es el original o una copia, un recorte o una captura? |
| **Fuente** | ¿Quién lo grabó o creó? |
| **Fecha** | ¿Cuándo se grabó o creó? |
| **Lugar** | ¿Dónde se grabó? |
| **Motivación** | ¿Por qué se grabó y por qué se difunde ahora? |

**[MM-1]** La conclusión de cada elemento es uno de los estados de `reglas.json` (`veredictos_multimedia`):

| Estado | Cuándo |
|---|---|
| `auténtico-en-su-contexto` | Es lo que dice ser: coinciden la fuente, la fecha, el lugar y el hecho |
| `descontextualizado` | Es real, pero de otra fecha, otro lugar u otro hecho. Hay que documentar el contexto original [MM-5] |
| `manipulado` | Está alterado: montaje, zonas clonadas, texto o audio añadidos |
| `generado-con-IA` | Solo con una prueba de origen [CAL-10] |
| `no-determinado` | No se ha podido establecer |

## 1. Análisis técnico automático

`media` sobre el archivo (opcionalmente, con el número de fotogramas y el idioma del audio) genera, en `media/analisis/<nombre>/`:

- `analisis.json`: huella SHA-256, dimensiones, metadatos EXIF, XMP e IPTC, cadenas de generadores de IA o de C2PA encontradas en los metadatos, y etiquetas del contenedor de vídeo (`creation_time`, `encoder`).
- `ela.png`, solo para JPEG: el análisis de nivel de error. Es una señal débil.
- `fotogramas/uniforme_XX.jpg` y `fotogramas/escena_XX.jpg`: fotogramas repartidos a lo largo del vídeo y en los cambios de plano.
- `hoja_de_contactos.jpg`: un resumen visual del vídeo.
- `audio.wav` y, si hay un transcriptor instalado, la transcripción.

Mira las imágenes, los fotogramas, la hoja de contactos y el ELA con `ver_imagen`.

### Cómo interpretar los metadatos

**[MM-2]** Los metadatos se interpretan con prudencia:

- **Las redes sociales y la mensajería borran el EXIF.** Que no haya EXIF no prueba nada.
- Si hay EXIF con fecha, cámara o GPS, es una pista sobre el original, pero se puede editar. Contrástala con otras pruebas.
- `Software` o `CreatorTool` (Photoshop, Canva, Snapseed) indican que el archivo pasó por ese programa, no que se manipulara el contenido.
- **IPTC `DigitalSourceType`** igual a `trainedAlgorithmicMedia` indica que el generador declara que es IA. `compositeWithTrainedAlgorithmicMedia` indica una edición con IA.
- **C2PA (Content Credentials)**: es un manifiesto firmado con el historial del archivo. Compruébalo en <https://contentcredentials.org/verify> (requiere navegador) o con `c2patool` si está instalado.
- En el vídeo, `creation_time` lo reescriben a menudo las plataformas al recodificar. Un `encoder` como `Lavf` (ffmpeg) indica recodificación.

## 2. Observación visual (lo que tú ves)

**[MM-3]** Describe de forma objetiva, sin interpretar ("se ve una multitud frente a un edificio con el rótulo …", no "una manifestación ilegal"):

- **Texto visible:** carteles, rótulos, matrículas (nunca las publiques [MET-9]), escaparates, idioma, prefijos telefónicos y dominios.
- **Marcas de agua y rótulos de televisión:** apuntan al emisor original.
- **Elementos fechables:** modelos de coche, móviles, uniformes, carteles de eventos, obras, la estación del año (vegetación, ropa) y el tiempo atmosférico.
- **Elementos localizables:** edificios singulares, montañas, costa, señales de tráfico, mobiliario urbano, el lado por el que se circula y la vegetación.
- **Sombras:** su dirección y su longitud permiten estimar la hora (con SunCalc, <https://www.suncalc.org>).

## 3. Búsqueda inversa: encontrar la primera aparición

**[MM-4]** La búsqueda inversa es la prueba más potente contra la descontextualización, y va siempre primero:

1. `buscar_imagen` con la URL pública de la imagen devuelve enlaces a Google Lens, Bing, Yandex y TinEye y, si el entorno tiene configurada la API, las coincidencias de Google Lens.
2. Con `navegador`, abre esos buscadores, o súbeles el fotograma, y busca la aparición **más antigua**. TinEye permite ordenar por fecha. Yandex funciona bien con caras y paisajes, y Google Lens con objetos y lugares. Respeta los CAPTCHA [MET-12].
3. Sin navegador, usa `buscar` con la descripción visual más el texto visible más las palabras clave del bulo, en varios idiomas, y prueba fechas candidatas. Busca también en las webs de los verificadores con la descripción de la imagen.
4. Con vídeos, repite la búsqueda con 2 o 3 fotogramas distintivos.
5. Si la búsqueda inversa no se ha podido hacer, dilo como **limitación** y deja los enlaces para que la persona la haga.

**[MM-5]** Una coincidencia anterior a la fecha que alega el bulo, con otro lugar u otro contexto, documenta el contexto original. Registra como evidencia la URL, la fecha y el título de esa primera aparición. Cómo se califica: [CAL-10].

## 4. Señales de manipulación

- Sombras, reflejos o iluminación incoherentes con el resto de la escena.
- Bordes recortados, zonas clonadas (patrones repetidos) o líneas rectas deformadas junto a una zona editada.
- Texto añadido con otra tipografía, o con otro grado de compresión o nitidez.
- En el ELA, una zona mucho más brillante o con una textura distinta del resto (bordes y texto brillan siempre).
- **Vídeo:** cortes bruscos, saltos de audio, cambios en el ruido de fondo, labios que no sincronizan, velocidad alterada o un audio que no es de esa escena.

**[MM-6]** **Capturas de tuits o de titulares:** comprueba que la publicación existe, con una captura secundaria de la URL de la cuenta o del medio, en la Wayback Machine o buscando el titular en la web del medio. Revisa también si el diseño de la interfaz, la tipografía, el formato de fecha y las métricas coinciden con la plataforma en esa época.

## 5. Contenido generado o alterado con IA

**[MM-7]** Las señales visuales son orientativas. Los detectores automáticos fallan a menudo, así que **nunca los uses como prueba única**. Lo que permite concluir es una prueba de origen [CAL-10]. Sin ella, la conclusión es "presenta indicios de haber sido generada con IA", y la calificación, la que indica [CAL-10].

- **Imagen:** manos y dedos, dientes, orejas y pendientes, texto ilegible o inventado, objetos fundidos, simetrías imposibles, piel excesivamente lisa, fondos incoherentes y logotipos deformados.
- **Vídeo:** física imposible, objetos que aparecen o desaparecen, rostros que cambian entre fotogramas y marcas de agua de generadores (Sora, Veo, Kling, Grok, Meta AI…), a veces recortadas o difuminadas.
- **Voz:** prosodia plana, respiración ausente o artificial, pronunciación extraña de nombres propios, e intervenciones que no constan en ninguna grabación original.

Para buscar una prueba de origen sirven los metadatos (apartado 1), la marca de agua del generador, la primera aparición (apartado 3) y el detector SynthID de Google, cuando está disponible (<https://deepmind.google/models/synthid/>).

## 6. Geolocalización y cronolocalización

**[MM-8]** Para situar y fechar una imagen:

- Compárala con Google Maps o Street View, OpenStreetMap (<https://www.openstreetmap.org>) o Google Earth (<https://earth.google.com>) con `navegador`. Si no lo hay, busca fotos del lugar candidato con `buscar`.
- Anota las coordenadas y los elementos coincidentes, al menos tres independientes, como evidencia de tipo `herramienta`.
- Para la fecha, compara con el tiempo que hacía en esa fecha (AEMET o Meteostat, <https://meteostat.net>), con eventos verificables (obras, carteles, fiestas) y con la posición del sol.

## 7. Audio, incluidas las notas de voz de WhatsApp

**[MM-9]** Con un audio:

- Transcríbelo con `media`. Si no hay transcriptor, indícalo y pide al usuario la transcripción, o los subtítulos si es un vídeo de YouTube (la captura los descarga si existen).
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
