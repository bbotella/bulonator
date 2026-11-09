# Limitaciones, privacidad y uso responsable

## Lo que Bulonator no puede hacer

- **Contactar con las personas implicadas.** Las redacciones de verificación piden su versión a las partes. Maldita.es, por ejemplo, da 12 horas laborables a los cargos públicos antes de publicar. Bulonator solo puede buscar las respuestas públicas que ya existen y, cuando procede, recomienda a la persona usuaria pedir réplica.
- **Ver lo que exige sesión:** contenidos privados, grupos de WhatsApp o Telegram privados, gran parte de Instagram y Facebook, o búsquedas en X. En esos casos pide el texto, una captura o el archivo.
- **Hacer búsqueda inversa de imágenes sin navegador.** Google Lens, Bing, Yandex y TinEye requieren un navegador. Sin un navegador MCP o una clave de SerpAPI, Bulonator genera los enlaces para que una persona los abra y lo declara como limitación.
- **Escuchar audio sin transcriptor.** El modelo no oye: necesita una transcripción (whisper, o los subtítulos de la plataforma).
- **Detectar IA con certeza.** Los detectores automáticos y las señales visuales fallan. Bulonator solo concluye "generado con IA" si hay una prueba de origen (metadatos IPTC o C2PA, marca de agua, primera aparición, declaración del autor). En los demás casos califica ALERTA.
- **Medir la difusión con precisión.** Sin acceso a las API de las plataformas, el análisis de propagación se basa en búsquedas públicas. Por eso habla de **indicios**.
- **Saber lo que aún no se ha publicado.** Las estadísticas tienen calendarios y las sentencias tardan. En esos casos la calificación será CONTEXTO o SIN VEREDICTO.

## La IA se equivoca

El diseño busca reducir los errores: registro de evidencias con citas literales, búsquedas documentadas, reapertura de las fuentes por un auditor independiente y reglas que obligan a elegir la categoría más prudente cuando hay dudas. Aun así, un modelo de lenguaje puede leer mal una tabla, confundir dos normas o pasar por alto una fuente.

- **Revisa siempre `informe.md` y las fuentes antes de publicar.** Comprueba al menos las fuentes que sostienen la calificación.
- La línea de transparencia de los textos ("Verificado con asistencia de IA…") no debe eliminarse.
- Si detectas un error en una verificación ya publicada, corrígela de forma visible.

## Privacidad: qué sale de tu equipo

Todo el material del caso se guarda **solo en local**, en `./bulonator-casos/`, que está excluido de git en este repositorio. Para hacer su trabajo, Bulonator envía información a estos servicios:

| Servicio | Qué se envía | Cuándo |
|---|---|---|
| La web o red de origen (x.com, bsky.app, t.me…) | La URL analizada | Siempre que se captura |
| `api.fxtwitter.com`, `cdn.syndication.twimg.com` | El ID del tuit | Captura de X/Twitter |
| `archive.org` (Wayback Machine) | La URL analizada y las URL de las fuentes | Consulta de copias. Con `--archivar`, además se solicita una copia pública nueva |
| `rdap.org` o `whois` | El dominio | Análisis de la fuente |
| `www.boe.es`, `servicios.ine.es` y otras API oficiales | Los términos de búsqueda | Verificación |
| El buscador y el lector web de Claude Code (WebSearch y WebFetch) | Las consultas y las URL | Verificación |
| SerpAPI y Google Fact Check Tools | La URL de la imagen y las palabras clave | Solo si has configurado sus claves |
| Anthropic | El contenido del caso, como en cualquier conversación de Claude Code | Siempre, con el plugin |
| El proveedor de cada modelo del motor (OpenAI, Google, Anthropic…) | El contenido del caso que recibe cada papel | Con el motor y modelos en la nube. Con Ollama en local, el contenido no sale de tu equipo salvo para las consultas de las fuentes |
| Tu buscador (SearXNG, Brave o Tavily) | Las consultas | Con `buscar` |

**No uses Bulonator con enlaces privados, documentos confidenciales ni datos personales de terceros** que no deban salir de tu equipo. Con `--archivar`, la copia en la Wayback Machine es **pública**.

## El motor con otros modelos

- **Los modelos locales o pequeños se equivocan más.** La validación mecánica impide citar URL que no se han abierto o citas que no están en la fuente, pero no evita que se lea mal una fuente real. Usa un auditor de otro proveedor y revisa los casos.
- **No hay navegador.** Las webs que necesitan JavaScript o iniciar sesión, y la búsqueda inversa sin SerpAPI, quedan como laguna.
- **Un VETO no lanza una investigación nueva.** El redactor corrige con las evidencias que hay. La única ronda de investigación adicional es la dirigida sobre la afirmación central.
- **Publicar es decisión de quien usa la librería.** `caso.aprobado` es un requisito mínimo, no un permiso para publicar sin revisión humana.

## Uso responsable

- **Neutralidad.** La metodología se aplica igual sea quien sea el afectado. Las contribuciones al proyecto que introduzcan sesgos partidistas (listas de "fuentes enemigas", criterios distintos según quién publica) no se aceptan.
- **No exponer a personas.** No uses los informes para señalar a usuarios particulares. Los textos generados ya los anonimizan; mantenlo así.
- **Citas breves.** Las evidencias citan fragmentos breves, de unas 50 palabras como máximo, para respetar los derechos de autor.
- **Condiciones de uso.** Respeta las de cada plataforma y la normativa de protección de datos (RGPD y LOPDGDD).
- **Sin afiliación.** Bulonator no es Maldita.es ni Pandemia Digital, ni habla en nombre de ningún verificador. No presentes sus resultados como si fueran de ellos.
