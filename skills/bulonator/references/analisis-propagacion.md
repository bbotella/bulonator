# Origen, fuente y propagación

Esta guía combina la lectura lateral (SIFT) con el análisis de propagación que hacen observatorios como **Pandemia Digital**: identificar quién publica, quién amplifica, cuándo y con qué patrones. El objetivo es contexto, no señalar a nadie. Todo indicio se presenta como tal, con sus límites.

## 1. ¿Ya está desmentido?

**[PROP-1]** Busca verificaciones previas como indica [VER-1], en español y en otros idiomas: los bulos se traducen y se reciclan. Si encuentras un desmentido, registra su URL, su fecha y su calificación, y si el contenido actual es la misma pieza o una variante.

## 2. Primera aparición y evolución

**[PROP-2]** Reconstruye de dónde sale el contenido y cómo ha cambiado:

- Busca **frases literales** del contenido entre comillas con `buscar`, en varias redes y webs.
- Consulta la copia más antigua en la Wayback Machine: `wayback` devuelve `primera_copia`. Usa también `https://archive.ph/newest/<URL>`.
- Detecta si quien publica es el origen o solo lo reenvía: retuits o citas, "vía", marcas de agua de otra cuenta, "Reenviado muchas veces" en WhatsApp, o el texto que acompaña ("me lo han pasado…").
- Reconstruye una **cronología**: primera aparición conocida, saltos de plataforma (Telegram, X, TikTok, WhatsApp) y momento en que lo difunden cuentas o figuras con mucho alcance.
- Comprueba si es un bulo reciclado: el mismo texto con otra fecha, otra ciudad u otro colectivo.

## 3. ¿Quién lo publica?

### Cuentas en redes

**[PROP-3]** La captura devuelve, cuando la plataforma lo permite: fecha de alta, seguidores, seguidos, número de publicaciones, biografía, verificación y ubicación declarada. Valóralos así:

- **Antigüedad:** una cuenta creada hace días o semanas que publica contenido viral es una señal de alerta, no una prueba.
- **Identidad:** ¿es quien dice ser? Busca cuentas oficiales enlazadas desde la web del organismo o la persona. Fíjate en marcas de parodia y en nombres de usuario casi idénticos al real (`policia_nacionaI` con I mayúscula).
- **Verificación de pago:** la marca azul de X se compra. No acredita identidad ni fiabilidad.
- **Historial:** si es posible, mira de qué temas publicaba antes y si cambia bruscamente de idioma o de temática (una señal común en cuentas compradas o reconvertidas).

### Webs

**[PROP-4]** Comprueba quién está detrás de una web:

- `dominio` da la fecha de registro, el registrador y el estado del dominio. Los dominios `.es` no tienen RDAP público: usa la consulta web de dominios.es.
- **Aviso legal:** en España la LSSI obliga a identificar al titular de la web. Su ausencia es una señal de alerta.
- **Sátira:** busca el aviso en la página "Quiénes somos" y consulta la lista de `verificadores.md`.
- **Dominios clonados** de medios reales: comprueba que el dominio es exactamente el del medio (por ejemplo, el de El País es `elpais.com`). Las campañas como Doppelgänger usan dominios parecidos con el diseño copiado.
- **Señales de granja de contenidos:** autores sin rastro, imágenes de bancos de fotos, mucha publicidad, titulares sensacionalistas y cero fuentes enlazadas.

## 4. Propagación y señales de coordinación

**[PROP-5]** Con `buscar` y, si lo hay, `navegador`, observa:

- **Mensajes idénticos o casi idénticos** (*copypasta*) publicados por muchas cuentas en poco tiempo, incluidas las mismas faltas de ortografía en el texto o en los *hashtags*.
- **Cuentas recién creadas**, sin foto o con foto genérica, con nombres de usuario con muchos números y que solo publican sobre un tema.
- **Volumen y horarios anómalos:** publicaciones 24 horas al día, o ráfagas sincronizadas.
- **Hashtags fabricados** que se convierten en tendencia en minutos.
- **Amplificadores:** qué figuras públicas, medios o canales con mucho alcance lo han difundido, y cuándo.
- **Promoción pagada:** la Biblioteca de Anuncios de Meta (<https://www.facebook.com/ads/library/>) y el Centro de Transparencia de Anuncios de Google (<https://adstransparency.google.com>), ambos con navegador.

**[PROP-6]** **Prudencia:** afirmar que hay una "campaña coordinada" o "bots" exige pruebas sólidas (muchas cuentas, patrones medibles y documentados). Si solo hay indicios, escribe "se observan indicios de difusión coordinada (…)", explica cuáles son y sus límites, y no atribuyas la autoría sin pruebas.

## 5. Motivación (hipótesis, solo con indicios)

| Tipo | Indicios |
|---|---|
| Económica | Enlaces a webs con mucha publicidad, tiendas, timos o recogida de datos ("rellena el formulario para recibir tu ayuda") |
| Política o ideológica | Coincidencia con campañas, *hashtags* de partido o momentos electorales |
| Sátira o humor mal entendido | Origen en una web satírica |
| Error | Un contenido real malinterpretado o una traducción errónea |
| Desinformación de Estado | Coincidencia con narrativas documentadas en EUvsDisinfo |

**[PROP-7]** La motivación casi nunca se puede probar. Si se menciona, debe ir apoyada en evidencias concretas y formulada como hipótesis.

## 6. Ética

- No nombres a los particulares que solo lo han difundido [MET-8].
- No publiques datos personales [MET-9].
- No enlaces al original para no darle tráfico: usa la copia archivada [MET-7].
