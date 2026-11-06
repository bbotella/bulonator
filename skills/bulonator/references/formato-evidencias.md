# Registro de evidencias y estructura del caso

El registro de evidencias garantiza que **cada afirmación del informe y de los textos para redes se pueda rastrear hasta una fuente concreta que se ha abierto durante el caso**. El auditor rechaza cualquier frase factual que no remita a una entrada `E-…`.

## Carpeta del caso

```text
bulonator-casos/AAAAMMDD-HHMMSS-<slug>/
├── captura.json            # datos estructurados de la captura (script)
├── <nombre>.json           # capturas secundarias (tuit incrustado, original encontrado…)
├── captura_raw/            # respuestas brutas de las API y HTML original
├── 01-captura.md           # ficha del contenido (agente de captura)
├── 02-afirmaciones.md      # desglose en afirmaciones (orquestador)
├── media/                  # imágenes, vídeos y audios descargados
│   └── analisis/<nombre>/  # metadatos, ELA, fotogramas, transcripción
├── evidencias/
│   ├── verificador-A1.md   # una por afirmación o grupo
│   ├── multimedia-M1.md    # una por elemento multimedia
│   ├── origen.md
│   └── docs/               # PDF y documentos oficiales descargados
├── informe.md              # informe completo (orquestador)
├── publicacion.md          # textos para compartir (orquestador)
└── 03-auditoria.md         # dictamen del auditor (una sección por ronda)
```

## Identificadores

| Prefijo | Origen |
|---|---|
| `A1`, `A2`… | Afirmaciones de `02-afirmaciones.md` |
| `M1`, `M2`… | Elementos multimedia de `02-afirmaciones.md` |
| `E-A1-01`, `E-A1-02`… | Evidencias del verificador de la afirmación A1 |
| `E-M1-01`… | Evidencias del análisis multimedia de M1 |
| `E-O-01`… | Evidencias del rastreo de origen y propagación |
| `E-C-01`… | Evidencias de la captura (qué dice exactamente el contenido, cuándo y quién lo publicó) |

## Formato de cada entrada

```markdown
### E-A1-03
- **Afirmación:** A1
- **Fuente:** Instituto Nacional de Estadística (INE). "Estadística Continua de Población. 1 de julio de 2026"
- **URL:** https://www.ine.es/...
- **Tipo:** primaria-oficial
- **Fecha del documento:** 2026-08-12
- **Consultada:** 2026-11-06, con WebFetch (o curl/script/navegador/Read)
- **Cita literal:** "…fragmento exacto, como máximo unas 50 palabras…"
- **Ubicación:** tabla 1, fila "Total nacional" (o artículo 3.2, página 14, minuto 02:13)
- **Qué demuestra:** que la población extranjera a 1 de julio de 2026 era X.
- **Qué NO demuestra:** el número de personas en situación irregular (no lo mide esta estadística).
- **Copia archivada:** https://web.archive.org/web/… (si se archivó o ya existía)
```

### Tipos de fuente

| Tipo | Qué es | Peso |
|---|---|---|
| `primaria-oficial` | Boletines oficiales, estadísticas oficiales, resoluciones judiciales, registros, comunicados oficiales sobre hechos propios | Máximo |
| `primaria-documental` | El documento, vídeo o audio original completo, el autor original de una foto, el diario de sesiones | Máximo |
| `experta` | Una persona experta identificada (nombre, cargo, institución y posibles conflictos de interés), siempre con su publicación o declaración pública | Alto |
| `verificador` | Un desmentido previo de un verificador de la IFCN o la EFCSN | Alto, pero no sustituye a la fuente primaria |
| `medio` | Una noticia de un medio de comunicación | Medio: secundaria |
| `declaración-de-parte` | La versión de una parte implicada (partido, empresa, persona afectada). Hay que indicar qué no se puede verificar de forma independiente | Bajo para el fondo, necesario para la réplica |
| `herramienta` | El resultado técnico de un análisis (metadatos, búsqueda inversa, geolocalización, ELA), con la ruta del archivo local | Según la técnica: ver `tecnicas-multimedia.md` |
| `archivo` | Una copia en la Wayback Machine o archive.today | Prueba de existencia y de fecha |

Las fuentes anónimas no se registran como evidencia. Tampoco lo son:

- **Los fragmentos de un buscador** (los resultados de `WebSearch`). Solo sirven para encontrar la página. La evidencia es la página abierta con `WebFetch`, `curl` o un navegador. Si no se puede abrir, no hay evidencia: anótalo en "Lagunas".
- **Wikipedia y otras enciclopedias o agregadores.** Úsalos para localizar las fuentes que citan (la nota al pie, el documento oficial, la noticia original) y registra esas fuentes. Solo si no hay otra cosa se cita la enciclopedia, como `medio` terciario, y eso obliga a bajar la confianza.

### Reglas de las citas

- Deben ser **literales** y copiadas del documento, no reformuladas. Cuando las obtengas con WebFetch, pide expresamente "la cita literal exacta". Para cifras y frases críticas, confírmalas sobre el original con `curl … | grep` o con `Read` del PDF descargado.
- Deben ser **breves**, de unas 50 palabras como máximo, para respetar los derechos de autor. Para el resto, parafrasea indicando la ubicación.
- Si el documento está en otro idioma, pon la cita original y una traducción entre corchetes.
- Nunca registres una URL que no hayas abierto en este caso, ni una que hayas reconstruido de memoria.

## Archivos de evidencias: estructura

```markdown
# Evidencias: <agente> <ID>

## Afirmación / elemento analizado
<texto exacto de la afirmación o descripción del elemento>

## Conclusión propuesta
- **Calificación propuesta:** FALSO (descontextualizado) | ALERTA | CONTEXTO | VERDADERO | NO VERIFICABLE | SIN VEREDICTO
- **Confianza:** ALTA | MEDIA | BAJA
- **Razonamiento (3-6 frases, cada una con su E-…):** …

## Registro de evidencias
### E-…
…

## Búsquedas realizadas
| Consulta / fuente | Herramienta | Resultado |
|---|---|---|
| "paga 2000 euros inmigrantes" en boe.es | WebSearch allowed_domains | 0 resultados relevantes |

## Lagunas y limitaciones
- …
```

La tabla de **búsquedas realizadas** es obligatoria: documenta las búsquedas con resultado negativo, que son las que permiten sostener las conclusiones basadas en la ausencia de pruebas.

## Lista de fuentes en los textos finales

- Numera las fuentes `[1]`, `[2]`… en el orden en que aparecen en `informe.md`, a partir de las entradas `E-…` que se usan. Una misma URL lleva un solo número.
- En el formato de cada fuente: `[n] Organismo o autor, «Título», fecha del documento. URL (consultado el AAAA-MM-DD; copia: URL archivada). Tipo de fuente.`
- En `informe.md`, cada afirmación lleva su número entre corchetes y, al final de la sección o en un comentario HTML, el ID de la evidencia: `<!-- E-A1-03 -->`. Así el auditor puede seguir la pista.
