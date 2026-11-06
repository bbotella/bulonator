# Escala de calificaciones y reglas de decisión

Las cuatro primeras categorías siguen la metodología de Maldita.es vigente desde junio de 2025 (<https://maldita.es/metodologia-maldita/>). Las dos últimas son propias de Bulonator y sirven para indicar sus límites.

## Categorías

### ❌ FALSO / BULO

Contenido que se ha podido verificar de forma independiente que es falso. Incluye estos subtipos, que el informe debe indicar:

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

**Requisitos mínimos:**

1. Hay pruebas positivas de la falsedad. No basta con no encontrar nada.
2. Hay al menos dos fuentes independientes, o una sola fuente primaria y definitiva cuando es la única relevante (por ejemplo, el autor original de la foto, o el BOE más la confirmación del organismo).
3. Ninguna fuente es anónima.
4. La confianza es MEDIA o ALTA.

### ⚠️ ALERTA

No hay pruebas de que el contenido sea cierto, pero tampoco fuentes independientes suficientes para decir que es falso. También aplica cuando el lenguaje es ambiguo o se mezcla con elementos verdaderos. Casos típicos:

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

Asuntos con varias aristas en los que hace falta explicar, o que dependen de una investigación, un trámite o un proceso todavía abierto. Casos típicos:

- Versiones contradictorias de las partes implicadas.
- Preguntas sin una respuesta única, que exigen explicar todos los casos posibles.
- Sentencias que no son firmes.
- Contenido real mezclado con elementos falsos o inverificables de menor peso.
- Declaraciones recortadas que, en su contexto, admiten otras lecturas.
- Declaraciones que omiten información y dan una visión parcial.
- Asuntos sin consenso científico.
- Contenidos reales que pueden confundirse con timos.

### ✅ VERDADERO

Se pone en duda un hecho o contenido, pero hay evidencias suficientes para probar que es cierto. Requiere confianza MEDIA o ALTA y al menos una fuente primaria.

### 💬 NO VERIFICABLE (propia de Bulonator)

Opiniones, valoraciones, predicciones o juicios morales. No se califican. Sí se verifican los datos en los que se apoyan, como afirmaciones separadas.

### ⏸️ SIN VEREDICTO (propia de Bulonator)

La investigación no ha podido llegar a una conclusión por sus propias limitaciones: no se pudo acceder al contenido, una fuente clave requiere navegador o inicio de sesión, el audio no se pudo transcribir, el resultado es demasiado reciente… El informe explica qué falta y cómo podría completarlo una persona.

## Reglas de decisión

1. **El veredicto global es el de la afirmación central,** la que da sentido al contenido y lo hace compartible. No es una media de todas. Por ejemplo, si la afirmación central es falsa y los detalles accesorios son ciertos, el veredicto es FALSO. Si la central es cierta pero hay detalles falsos de menor peso, es CONTEXTO.
2. **Cuándo la ausencia de pruebas es concluyente.** Puede sostener un FALSO solo si el hecho tendría que constar necesariamente en una fuente que se ha revisado a fondo (por ejemplo, una ayuda estatal que tendría que estar en el BOE y no aparece), y además existe una segunda fuente positiva: un desmentido del organismo, una verificación previa o la norma real que dice otra cosa. En cualquier otro caso es ALERTA. Anota siempre las búsquedas con resultado negativo.
3. **Multimedia:**
   - Imagen real con el contexto cambiado y el contexto original documentado (primera aparición con fecha y lugar): FALSO (`descontextualizado`).
   - IA con una prueba de origen (marca de agua del generador, C2PA, el autor lo reconoce, primera aparición en una cuenta de imágenes de IA, IPTC `trainedAlgorithmicMedia`): FALSO (`manipulado`).
   - Solo artefactos visuales: ALERTA.
4. **Citas:**
   - No hay rastro en fuentes originales: ALERTA.
   - Consta que es inventada (la transcripción original dice otra cosa o la persona la desmiente y no hay registro): FALSO.
   - Es real pero está recortada: CONTEXTO.
5. **Ciencia y salud:**
   - Va contra el consenso: ALERTA, con una advertencia de riesgo clara.
   - Es una afirmación factual concreta que se demuestra falsa con análisis o con documentación regulatoria: FALSO.
6. **Judicial:** una resolución que no es firme da CONTEXTO, nunca VERDADERO ni FALSO definitivo sobre el fondo.
7. **Sátira:** identifica la fuente satírica. Si circula como real y hay pruebas de falsedad es FALSO (`sátira-como-real`). Si no las hay, ALERTA.
8. **Si hay dudas entre dos categorías,** elige la más prudente, que es la que afirma menos (ALERTA antes que FALSO, CONTEXTO antes que VERDADERO), y explica por qué.

## Confianza

| Nivel | Cuándo |
|---|---|
| **ALTA** | Fuentes primarias definitivas que coinciden, ninguna evidencia en contra y, para multimedia, origen localizado |
| **MEDIA** | Fuentes sólidas, pero alguna secundaria o con lagunas menores que no cambiarían el veredicto |
| **BAJA** | Evidencia indirecta o limitaciones relevantes. Con confianza BAJA solo caben ALERTA, CONTEXTO o SIN VEREDICTO |

## Etiquetas para los textos

| Calificación | Etiqueta corta | Fórmula de titular (sándwich de la verdad) |
|---|---|---|
| FALSO | ❌ FALSO | "No, [hecho real]: [el bulo] es falso" o "Es falso que [bulo]: [hecho real]" |
| ALERTA | ⚠️ ALERTA | "No hay pruebas de que [bulo]: [lo que sí consta]" |
| CONTEXTO | 🔍 CONTEXTO | "[Afirmación]: qué se sabe y qué falta" |
| VERDADERO | ✅ VERDADERO | "Sí, [hecho]: lo confirma [fuente]" |
| NO VERIFICABLE | 💬 OPINIÓN | "Es una opinión: los datos en los que se apoya…" |
| SIN VEREDICTO | ⏸️ SIN VEREDICTO | "Aún no podemos confirmarlo ni desmentirlo: [qué falta]" |
