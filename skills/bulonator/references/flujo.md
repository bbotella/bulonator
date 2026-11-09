# Flujo de un caso

Recorrido de un caso de principio a fin, igual en cualquier entorno: qué fases hay, quién hace cada una y qué deja en la carpeta del caso (estructura en `formato-evidencias.md`). La metodología que se aplica en cada fase está en `metodologia.md`, y las cifras, en `reglas.json`.

## Fases

**[FLU-1]** Las fases van en este orden. La auditoría editorial nunca se omite, en ningún modo. Las capacidades que no estén disponibles (descarga de vídeo, transcripción, búsqueda inversa…) se anotan al preparar el caso y se declaran como limitación [MET-10].

| Fase | Quién | Qué deja en la carpeta del caso |
|---|---|---|
| 0. Preparación | orquestador | la carpeta del caso y la lista de capacidades disponibles |
| 1. Captura y preservación | `bulonator-captura` | `captura.json`, `01-captura.md`, la multimedia descargada en `media/` y las copias archivadas |
| 2. Desglose | orquestador | `02-afirmaciones.md` |
| 3. Investigación en paralelo | `bulonator-verificador` (uno por afirmación o grupo), `bulonator-multimedia` (uno por elemento), `bulonator-origen` (siempre uno) | `evidencias/*.md`, con los textos abiertos en `evidencias/paginas/` y las búsquedas en `evidencias/busquedas.jsonl` |
| 4. Deliberación y redacción | orquestador | `informe.md` y `publicacion.md`, ya validados |
| 5. Auditoría editorial | `bulonator-auditor`, con derecho a veto | `03-auditoria.md`, con una sección por ronda: PALANTE, CAMBIOS o VETO |
| 6. Cierre y entrega | orquestador | `resultado.json`; el veredicto y los textos se entregan al usuario |

**[FLU-2]** Si la captura está vacía o falta el contenido esencial (el texto, la imagen o el vídeo), no se sigue hacia un veredicto. Se explica qué ha fallado y se pide al usuario el texto, una captura de pantalla o el archivo. Con lo que dé, se vuelve a capturar.

**[FLU-3]** Al terminar la investigación se leen todas las evidencias. Si una afirmación central queda sin resolver o las evidencias se contradicen, se lanza una ronda dirigida de investigación, pero solo en modo profundo o si sin ella el veredicto sería SIN VEREDICTO. Se explica qué falta.

## Modos

**[FLU-4]** El modo fija cuántos agentes se lanzan como máximo en la investigación y en la auditoría. Las cifras de cada modo están en `reglas.json` → `modos`; un valor `null` significa que no hay límite.

| Modo | Opción | Qué cambia |
|---|---|---|
| normal | *(ninguna)* | El equilibrio por defecto entre profundidad y tiempo |
| rápido | `--rapido` | Menos verificadores y análisis multimedia, y el rastreo de origen se centra en los desmentidos previos. La auditoría se mantiene [FLU-1] |
| profundo | `--profundo` | Más verificadores, todos los elementos multimedia, una segunda ronda de investigación si hay lagunas [FLU-3] y auditores independientes con enfoques distintos: "fuentes y datos" y "metodología, ética y redacción" |

**[FLU-5]** Con `--archivar` se solicitan copias nuevas en la Wayback Machine del contenido y de las fuentes clave. Sin esta opción, solo se consultan las copias que ya existen.

`--idioma X` elige el idioma de los textos para redes; por defecto, español [RED-7].

## Desglose

Lo hace el orquestador, con el método de `metodologia.md` (apartado 3) y la plantilla `templates/afirmaciones.md`.

**[FLU-6]** `02-afirmaciones.md` recoge:

- cómo se está entendiendo el contenido y cuál es la **afirmación central** [MET-14];
- las afirmaciones verificables `A1…An`, con su tipo [MET-15] y con quién tendría el dato [MET-16];
- los elementos multimedia `M1…Mn` y lo que se dice que muestran;
- lo que es opinión o predicción, que no se califica [CAL-6];
- la viralidad y la peligrosidad [MET-13];
- los encargos de investigación [FLU-7].

**[FLU-7]** Encargos: cada afirmación o grupo de afirmaciones va a un verificador; cada elemento multimedia relevante, a un análisis multimedia, y el contenido completo, al rastreo de origen. Agrupa las afirmaciones menores para respetar los límites del modo [FLU-4].

## Deliberación y redacción

Lo hace el orquestador cuando ya tiene todas las evidencias.

**[FLU-8]** Aplica `calificaciones.md` a cada afirmación. Después decide el **veredicto global** a partir de la afirmación central [CAL-8], con su subtipo [CAL-1] y su confianza [CAL-16], y escribe por qué es esa categoría y no la vecina [CAL-15].

**[FLU-9]** Construye la lista de fuentes `[n]` **solo** a partir de las entradas `E-…` que uses [EV-12]. Escribe `informe.md` con `templates/informe.md` y pon los ID de las evidencias en comentarios junto a cada párrafo [EV-14].

**[FLU-10]** Escribe `publicacion.md` con `templates/publicacion.md` y `redaccion.md`, en el idioma pedido. Mide cada publicación y ajusta las que pasen del límite de su plataforma [RED-9].

**[FLU-11]** Con los dos textos escritos, pasa la validación mecánica del caso y corrige todos sus errores antes de la auditoría. El auditor recibe el resultado de esa validación.

## Auditoría y cierre

**[FLU-12]** Cada ronda la hace un auditor que no ha investigado el caso [MET-18]. En modo profundo, los auditores trabajan a la vez, cada uno con su enfoque [FLU-4].

**[FLU-13]** Según el dictamen:

- **PALANTE:** se cierra el caso y se entrega [FLU-15].
- **CAMBIOS:** se aplican todos. Si alguno afecta a la calificación o a una cifra, hay otra ronda.
- **VETO:** se corrige el fondo (más investigación, otra calificación o menos confianza) y hay otra ronda.

Después de aplicar cambios, la validación mecánica tiene que volver a pasar sin errores.

**[FLU-14]** El número máximo de rondas está en `reglas.json` (`auditoria.rondas_max`). Si después de la última sigue sin haber PALANTE, se baja la calificación a la más prudente que sí se sostenga (o a SIN VEREDICTO) [CAL-15] y se explica la discrepancia en el informe.

**[FLU-15]** Al cerrar el caso se genera `resultado.json` (calificación, subtipo, confianza, dictamen, número de rondas e idioma) y la validación mecánica pasa sin errores. Hasta entonces no se entrega nada al usuario.
