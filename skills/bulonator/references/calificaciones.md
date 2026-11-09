# Escala de calificaciones y reglas de decisión

Las cuatro primeras categorías siguen la metodología de Maldita.es vigente desde junio de 2025 (<https://maldita.es/metodologia-maldita/>). Las dos últimas son propias de Bulonator y sirven para indicar sus límites.

La lista cerrada de categorías, con sus subtipos y las confianzas que admite cada una, está en `reglas.json` (`calificaciones`). Aquí se explica qué significa cada categoría y cuándo se aplica.

## Categorías

### ❌ FALSO / BULO

**[CAL-1]** Contenido que se ha podido verificar de forma independiente que es falso. El informe indica siempre su subtipo, de la lista de `reglas.json` (`calificaciones.FALSO.subtipos`):

| Subtipo | Ejemplo típico |
|---|---|
| `inventado` | El hecho no ha ocurrido o el documento no existe |
| `manipulado` | Imagen, vídeo o audio alterado. Incluye el contenido generado con IA que se presenta como real |
| `descontextualizado` | Contenido real con un lugar, fecha o autoría falsos (vídeo de otro país, foto de hace años) |
| `fuente-no-lo-dice` | La fuente en la que se apoya el contenido no sostiene lo que se le atribuye |
| `contradice-datos` | Contradice estadísticas, documentos o fuentes fiables |
| `suplantación` | Se hace pasar por una persona, medio, empresa u organismo, y hay pruebas suficientes de ello |
| `sátira-como-real` | Contenido satírico que circula como si fuera real, cuando hay pruebas de que lo que cuenta es falso |
| `timo` | Fraude o phishing (falsas ayudas, sorteos, mensajes de la DGT o de Hacienda) |

**[CAL-2]** **Requisitos mínimos de un FALSO:**

1. Hay pruebas positivas de la falsedad. No basta con no encontrar nada [CAL-9].
2. Hay al menos tantas fuentes independientes como fija `reglas.json` (`falso.fuentes_independientes_min`), o una sola fuente primaria y definitiva cuando es la única relevante (por ejemplo, el autor original de la foto, o el BOE más la confirmación del organismo).
3. Ninguna fuente es anónima [MET-5].
4. La confianza es una de las que `reglas.json` admite para FALSO.

### ⚠️ ALERTA

**[CAL-3]** No hay pruebas de que el contenido sea cierto, pero tampoco fuentes independientes suficientes para decir que es falso. También aplica cuando el lenguaje es ambiguo o se mezcla con elementos verdaderos. Casos típicos:

- Narrativas que mezclan bulos ya desmentidos con afirmaciones inverificables (algunas teorías de la conspiración).
- Contenidos que contradicen el consenso o la evidencia científica disponible.
- Mezcla de elementos que se demuestran falsos con otros que no se pueden verificar, como futuribles o intenciones.
- Afirmaciones falsas junto con inexactitudes, o un uso del lenguaje que lleva a entender algo distinto de la realidad.
- Varios argumentos ponen en duda el contenido, pero no hay pruebas suficientes para decir que es falso.
- Sátira que circula como real sin pruebas suficientes de que lo que describe no ocurrió.
- Hechos sin ninguna evidencia, testigo o rastro material o digital, cuya falsedad tampoco se puede certificar.
- Citas atribuidas a personas públicas que no se pueden rastrear más allá del propio contenido.
- Imágenes con indicios visuales de IA sin una prueba de origen que lo confirme.

### 🔍 CONTEXTO

**[CAL-4]** Asuntos con varias aristas en los que hace falta explicar, o que dependen de una investigación, un trámite o un proceso todavía abierto. Casos típicos:

- Versiones contradictorias de las partes implicadas.
- Preguntas sin una respuesta única, que exigen explicar todos los casos posibles.
- Sentencias que no son firmes.
- Contenido real mezclado con elementos falsos o inverificables de menor peso.
- Declaraciones recortadas que, en su contexto, admiten otras lecturas.
- Declaraciones que omiten información y dan una visión parcial.
- Asuntos sin consenso científico.
- Contenidos reales que pueden confundirse con timos.

### ✅ VERDADERO

**[CAL-5]** Se pone en duda un hecho o contenido, pero hay evidencias suficientes para probar que es cierto. Requiere al menos una fuente primaria y una de las confianzas que `reglas.json` admite para VERDADERO.

### 💬 NO VERIFICABLE (propia de Bulonator)

**[CAL-6]** Opiniones, valoraciones, predicciones o juicios morales. No se califican. Sí se verifican los datos en los que se apoyan, como afirmaciones separadas.

### ⏸️ SIN VEREDICTO (propia de Bulonator)

**[CAL-7]** La investigación no ha podido llegar a una conclusión por sus propias limitaciones: no se pudo acceder al contenido, una fuente clave requiere navegador o inicio de sesión, el audio no se pudo transcribir, el resultado es demasiado reciente… El informe explica qué falta y cómo podría completarlo una persona.

## Reglas de decisión

- **[CAL-8]** **El veredicto global es el de la afirmación central,** la que da sentido al contenido y lo hace compartible. No es una media de todas. Por ejemplo, si la afirmación central es falsa y los detalles accesorios son ciertos, el veredicto es FALSO. Si la central es cierta pero hay detalles falsos de menor peso, es CONTEXTO.
- **[CAL-9]** **Que no haya pruebas no significa que sea falso.** Si no se encuentra nada, la calificación es ALERTA. La ausencia de pruebas solo puede sostener un FALSO si el hecho tendría que constar necesariamente en una fuente que se ha revisado a fondo (por ejemplo, una ayuda estatal que tendría que estar en el BOE y no aparece), y además existe una segunda fuente positiva: un desmentido del organismo, una verificación previa o la norma real que dice otra cosa. En cualquier otro caso es ALERTA. Anota siempre las búsquedas con resultado negativo [EV-11].
- **[CAL-10]** **Multimedia:**
  - Imagen real con el contexto cambiado y el contexto original documentado (primera aparición con fecha y lugar): FALSO (`descontextualizado`).
  - IA con una prueba de origen: FALSO (`manipulado`). Son pruebas de origen:
    - los metadatos IPTC (`DigitalSourceType` igual a `trainedAlgorithmicMedia`) o C2PA que declaran IA;
    - la marca de agua del generador;
    - la primera aparición en una cuenta que publica imágenes de IA, o en la web de un generador;
    - que el autor reconozca que lo hizo con IA;
    - que la persona supuestamente grabada no estuviera allí, según fuentes fiables;
    - el detector SynthID de Google, cuando está disponible.
  - Solo artefactos visuales: ALERTA.
- **[CAL-11]** **Citas:**
  - No hay rastro en fuentes originales: ALERTA.
  - Consta que es inventada (la transcripción original dice otra cosa o la persona la desmiente y no hay registro): FALSO.
  - Es real pero está recortada: CONTEXTO.
- **[CAL-12]** **Ciencia y salud:**
  - Va contra el consenso: ALERTA, con una advertencia de riesgo clara.
  - Es una afirmación factual concreta que se demuestra falsa con análisis o con documentación regulatoria: FALSO.
- **[CAL-13]** **Judicial:** una resolución que no es firme da CONTEXTO, nunca VERDADERO ni FALSO definitivo sobre el fondo.
- **[CAL-14]** **Sátira:** identifica la fuente satírica (ver `verificadores.md`). Si circula como real y hay pruebas de falsedad es FALSO (`sátira-como-real`). Si no las hay, ALERTA.
- **[CAL-15]** **Por qué esa categoría y no la vecina.** Explica siempre por qué es esa categoría y no la vecina (por ejemplo, por qué FALSO y no ALERTA). Si hay dudas entre dos, elige la más prudente, que es la que afirma menos (ALERTA antes que FALSO, CONTEXTO antes que VERDADERO), y explica por qué.

## Confianza

**[CAL-16]** Cada calificación lleva uno de estos niveles de confianza, siempre entre los que `reglas.json` admite para esa categoría:

| Nivel | Cuándo |
|---|---|
| **ALTA** | Fuentes primarias definitivas que coinciden, ninguna evidencia en contra y, para multimedia, origen localizado |
| **MEDIA** | Fuentes sólidas, pero alguna secundaria o con lagunas menores que no cambiarían el veredicto |
| **BAJA** | Evidencia indirecta o limitaciones relevantes. Las categorías que exigen pruebas firmes no la admiten |

## Etiquetas para los textos

**[CAL-17]** Los textos usan la etiqueta corta de cada calificación. Las fórmulas de titular están en [RED-11].

| Calificación | Etiqueta corta |
|---|---|
| FALSO | ❌ FALSO |
| ALERTA | ⚠️ ALERTA |
| CONTEXTO | 🔍 CONTEXTO |
| VERDADERO | ✅ VERDADERO |
| NO VERIFICABLE | 💬 OPINIÓN |
| SIN VEREDICTO | ⏸️ SIN VEREDICTO |
