# Guía de redacción: informe y textos para redes

## Principios

1. **El veredicto, primero.** La primera línea dice la calificación y el hecho real.
2. **Sándwich de la verdad:** dato cierto, mención breve del bulo y otra vez el dato cierto o el contexto. El bulo nunca aparece solo ni como titular sin su etiqueta.
3. **Cada razón lleva su fuente.** En los textos para redes, las razones van numeradas y con un enlace a la fuente principal de cada una. Si no caben todos los enlaces, la lista completa va en el último mensaje del hilo.
4. **Lenguaje neutro y preciso.** Sin adjetivos valorativos ("delirante", "manipulador"), sin burla y sin atribuir intención ("mienten a sabiendas") salvo que esté documentada. Se escribe "el contenido afirma", "no consta" o "los datos del INE muestran".
5. **No amplificar:**
   - no enlaces al contenido original: usa la copia archivada;
   - no nombres a usuarios particulares que lo han compartido;
   - no reproduzcas la imagen falsa sin marcarla.
6. **Proteger a las personas:** ni víctimas, ni menores, ni datos personales.
7. **Claridad:** frases cortas, cifras redondeadas con su unidad y su fecha ("4,1 millones de personas paradas en el tercer trimestre de 2026, según la EPA"), y siglas explicadas la primera vez.
8. **Transparencia:** di qué no se ha podido comprobar, la fecha de verificación y que es una verificación asistida por IA.
9. **Idioma:** español por defecto. Con `--idioma`, catalán, gallego, euskera, inglés u otro. Las citas se mantienen en su idioma original.

## Límites por plataforma

| Plataforma | Límite | Cómo cuenta |
|---|---|---|
| X | 280 por publicación | Cada enlace cuenta 23 y los emojis cuentan 2. Compruébalo con `python3 <SCRIPT> contar --bloques publicacion.md` |
| Bluesky | 300 | Caracteres |
| Threads | 500 | Caracteres |
| Mastodon | 500 (habitual) | Cada enlace cuenta 23 |
| Instagram | 2.200 en el pie | Los enlaces no son clicables |
| LinkedIn | 3.000 | |
| WhatsApp / Telegram | Sin límite práctico | Párrafos cortos, `*negrita*` en WhatsApp |

Cada publicación va en su propio bloque ` ```text ` dentro de `publicacion.md` para poder contarla y copiarla.

## Fórmulas

**Titular o primera línea:**

- `❌ FALSO: No, [hecho real]. [El bulo] no es cierto: [razón principal].`
- `⚠️ ALERTA: No hay pruebas de que [bulo]. [Qué sí consta].`
- `🔍 CONTEXTO: [Afirmación] es cierta solo en parte: [matiz clave].`
- `✅ VERDADERO: Sí, [hecho], según [fuente].`

**Cierre:**

> Verificado el DD/MM/AAAA con asistencia de IA (Bulonator, metodología inspirada en Maldita.es). Si aparece información nueva, revisaremos la calificación. ¿Ves un error? Avísanos.

Usa como mucho uno o dos *hashtags* (por ejemplo `#Bulo` o el tema) y pocos emojis: solo el de la etiqueta y, si acaso, 👉 para las fuentes.

## Texto alternativo

Si se propone compartir una imagen (por ejemplo, una captura del bulo con el sello "FALSO"), incluye su texto alternativo:

> Captura de un mensaje viral que afirma [X], con el sello "FALSO" superpuesto. Los datos personales están difuminados.

## Comprobación final antes de entregar

- [ ] La calificación coincide en el informe y en todos los textos.
- [ ] Cada número, fecha y cita de los textos para redes está en `informe.md` con su `[n]` y su `E-…`.
- [ ] Todos los enlaces son URL que se han abierto durante el caso, y el bulo solo aparece enlazado mediante su copia archivada.
- [ ] Las longitudes están verificadas con `contar`.
- [ ] Hay una línea de transparencia (asistencia de IA y fecha).
