# Guía de redacción: informe y textos para redes

Los principios éticos (neutralidad, no amplificar, anonimizar, proteger a las personas y transparencia) están en `metodologia.md`, de [MET-6] a [MET-10]. Esta guía dice cómo se aplican al escribir.

## Principios

- **[RED-1]** **El veredicto, primero.** La primera línea dice la calificación y el hecho real.
- **[RED-2]** **Sándwich de la verdad:** dato cierto, mención breve del bulo y otra vez el dato cierto o el contexto. El bulo nunca aparece solo ni como titular sin su etiqueta.
- **[RED-3]** **Cada razón lleva su fuente.** Cada número, fecha y cita de los textos para redes está en `informe.md` con su `[n]` y su `E-…`. En los textos para redes, las razones van numeradas y con un enlace a la fuente principal de cada una. Si no caben todos los enlaces, la lista completa va en el último mensaje del hilo.
- **[RED-4]** **Lenguaje neutro y preciso.** Sin adjetivos valorativos ("delirante", "manipulador"), sin burla y sin atribuir intención ("mienten a sabiendas") salvo que esté documentada [MET-6]. Se escribe "el contenido afirma", "no consta" o "los datos del INE muestran".
- **No amplificar:** copia archivada en lugar del original [MET-7]; particulares anonimizados [MET-8].
- **Proteger a las personas:** ni víctimas, ni menores, ni datos personales [MET-9].
- **[RED-5]** **Claridad:** frases cortas, cifras redondeadas con su unidad y su fecha ("4,1 millones de personas paradas en el tercer trimestre de 2026, según la EPA"), y siglas explicadas la primera vez.
- **[RED-6]** **Transparencia** [MET-10]: di qué no se ha podido comprobar, la fecha de verificación y que es una verificación asistida por IA.
- **[RED-7]** **Idioma:** español por defecto. Con `--idioma`, catalán, gallego, euskera, inglés u otro. Las citas se mantienen en su idioma original.
- **[RED-8]** **Una sola calificación:** la calificación es la misma en el informe y en todos los textos.

## Límites por plataforma

**[RED-9]** Cada publicación respeta el límite de su plataforma. Los límites de X, Bluesky, Threads y Mastodon, y cómo se cuentan, están en `reglas.json` (`plataformas`). En X la cuenta es ponderada: cada enlace y cada emoji tienen un peso fijo, así que no basta con contar caracteres. Mide cada bloque con el recuento de caracteres del caso antes de entregar.

| Plataforma | Límite | Cómo cuenta |
|---|---|---|
| X | `plataformas.x` | Ponderada: los enlaces y los emojis tienen un peso fijo |
| Bluesky | `plataformas.bluesky` | Caracteres |
| Threads | `plataformas.threads` | Caracteres |
| Mastodon | `plataformas.mastodon` (el habitual; cada instancia puede fijar otro) | Los enlaces tienen un peso fijo |
| Instagram | 2.200 en el pie | Los enlaces no son clicables |
| LinkedIn | 3.000 | |
| WhatsApp / Telegram | Sin límite práctico | Párrafos cortos, `*negrita*` en WhatsApp |

**[RED-10]** Cada publicación va en su propio bloque ` ```text ` dentro de `publicacion.md` para poder contarla y copiarla.

## Fórmulas

**[RED-11]** **Titular o primera línea:** la etiqueta corta de la calificación [CAL-17], dos puntos y una fórmula de sándwich [RED-2]:

| Calificación | Fórmula |
|---|---|
| FALSO | "No, [hecho real]. [El bulo] no es cierto: [razón principal]." o "Es falso que [bulo]: [hecho real]." |
| ALERTA | "No hay pruebas de que [bulo]. [Qué sí consta]." |
| CONTEXTO | "[Afirmación] es cierta solo en parte: [matiz clave]." o "[Afirmación]: qué se sabe y qué falta." |
| VERDADERO | "Sí, [hecho], según [fuente]." |
| NO VERIFICABLE | "Es una opinión: los datos en los que se apoya…" |
| SIN VEREDICTO | "Aún no podemos confirmarlo ni desmentirlo: [qué falta]." |

**[RED-12]** **Cierre:** el hilo y el texto largo terminan con la línea de transparencia de `templates/publicacion.md`: fecha de verificación, asistencia de IA (Bulonator, metodología inspirada en Maldita.es), revisión si aparece información nueva e invitación a señalar errores.

**[RED-13]** Usa como mucho uno o dos *hashtags* (por ejemplo `#Bulo` o el tema) y pocos emojis: solo el de la etiqueta y, si acaso, 👉 para las fuentes.

## Texto alternativo

**[RED-14]** Si se propone compartir una imagen (por ejemplo, una captura del bulo con el sello "FALSO"), incluye su texto alternativo:

> Captura de un mensaje viral que afirma [X], con el sello "FALSO" superpuesto. Los datos personales están difuminados.

## Comprobación final antes de entregar

- [ ] La calificación coincide en el informe y en todos los textos [RED-8].
- [ ] Cada dato de los textos para redes está en `informe.md` con su `[n]` y su `E-…` [RED-3].
- [ ] Los enlaces son URL abiertas en el caso [EV-9], y el bulo solo aparece mediante su copia archivada [MET-7].
- [ ] Las longitudes están medidas [RED-9].
- [ ] Hay una línea de transparencia [RED-6] [RED-12].
