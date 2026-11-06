# Textos para compartir: {{ID_CASO}}

> Calificación: {{EMOJI}} {{CALIFICACIÓN}} · Confianza: {{…}} · Verificado el {{DD/MM/AAAA}}
> Cada publicación va en su propio bloque `text` para poder copiarla y medirla (`python3 <SCRIPT> contar --bloques publicacion.md`).
> Cada dato de estos textos procede de `informe.md`, donde tiene su fuente [n] y su evidencia E-….

## 1. Publicación breve (X, Bluesky, Threads, Mastodon): 280 como máximo, ponderado para X

```text
{{EMOJI}} {{CALIFICACIÓN}}: {{hecho real + mención breve del bulo}}.

{{razón principal en una frase}} 👉 {{URL de la fuente principal}}

#Bulo
```

## 2. Hilo para X (de 4 a 8 publicaciones de 280 como máximo cada una)

```text
1/ {{EMOJI}} {{CALIFICACIÓN}}: {{titular sándwich}}. Os explicamos por qué 🧵
```

```text
2/ Qué circula: {{descripción breve, sin nombrar a particulares}}. Copia archivada: {{URL archivada}}
```

```text
3/ {{Razón 1 con dato y fuente}} {{URL}}
```

```text
4/ {{Razón 2…}} {{URL}}
```

```text
5/ {{Lo que no se ha podido comprobar, si es relevante, o el contexto}}
```

```text
6/ Fuentes: [1] {{…}} [2] {{…}}. Verificado el {{DD/MM/AAAA}} con asistencia de IA (metodología inspirada en Maldita.es). ¿Ves un error? Avísanos.
```

## 3. Texto largo (Facebook, Instagram, LinkedIn, Telegram)

```text
{{EMOJI}} {{CALIFICACIÓN}}: {{titular sándwich}}

Circula {{qué, dónde y desde cuándo}}. {{Afirmación central en una frase}}.

Por qué es {{calificación}}:
1️⃣ {{razón con fuente [1]}}
2️⃣ {{razón con fuente [2]}}
3️⃣ {{razón con fuente [3]}}

Lo que no hemos podido comprobar: {{…, o eliminar este párrafo}}

Fuentes:
[1] {{Organismo, título, fecha}}: {{URL}}
[2] …

Verificado el {{DD/MM/AAAA}} con asistencia de IA (Bulonator, metodología inspirada en Maldita.es). Si aparece información nueva revisaremos la calificación.
```

## 4. Respuesta para grupos de WhatsApp o Telegram

```text
*{{EMOJI}} {{CALIFICACIÓN}}*: {{hecho real}}.

{{Razón principal en 1-2 frases}}.
Fuente: {{URL}}

Antes de reenviar, comprueba la fuente 🙏
```

## 5. Texto alternativo (si se comparte una imagen)

```text
{{Descripción de la imagen compartida, indicando la etiqueta superpuesta y que los datos personales están ocultos}}
```

## Control de calidad

| Bloque | Ponderado X | Caracteres | ¿Cabe? |
|---|---|---|---|
| {{salida de contar}} | | | |
