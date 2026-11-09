---
name: verificar-dato
description: Verifica una afirmación concreta (una cifra, una estadística, una ley, una ayuda o una cita) contra fuentes oficiales y primarias (BOE, boletines autonómicos, INE, Eurostat, Congreso, agencias sanitarias) y entrega la calificación con fuentes y un texto breve para compartir. Úsala cuando el usuario escriba '/verificar-dato "<afirmación>"' o pregunte si un dato o declaración concreta es cierta ("¿es verdad que el paro juvenil es del 40%?", "¿existe una ley que…?"). Si lo que hay que verificar es una publicación completa con imágenes, vídeos o un enlace, usa /bulonator.
argument-hint: '"<afirmación a verificar>" [--idioma es|ca|gl|eu|en]'
allowed-tools: Bash(python3:*), Bash(curl:*), Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent
---

# Verificar un dato o una afirmación

**Afirmación:** `$ARGUMENTS`

- SCRIPT: `${CLAUDE_SKILL_DIR}/../bulonator/scripts/bulonator.py`
- REFS: `${CLAUDE_SKILL_DIR}/../bulonator/references/`
- Plantillas: `${CLAUDE_SKILL_DIR}/../bulonator/templates/`

Sigue `REFS/flujo.md` con las particularidades de abajo. Te obligan los principios de `REFS/metodologia.md` (apartado 1). Lee `REFS/flujo.md`, `REFS/calificaciones.md` y `REFS/fuentes-oficiales.md`.

Los subagentes se llaman `bulonator-verificador`, `bulonator-origen` y `bulonator-auditor` (con instalación como plugin, `bulonator:bulonator-…`). Pasa en cada prompt CASO y las rutas de SCRIPT y REFS. Si no están disponibles, usa agentes de propósito general indicándoles que sigan las instrucciones de `${CLAUDE_SKILL_DIR}/../../agents/bulonator-verificador.md` (o `~/.claude/agents/`).

## Particularidades

1. **Entrada:** si la afirmación está vacía o es una opinión pura, pide una afirmación comprobable, o explica que no es verificable y señala qué datos la sostienen [CAL-6]. La única opción es `--idioma`.
2. **Sin captura:** ejecuta `python3 SCRIPT caso "<afirmación>"` y toma la ruta del campo `caso`.
3. **Desglose mínimo:** en `CASO/02-afirmaciones.md`, la afirmación literal como `A1`, formulada de forma comprobable [MET-15] y con quién tendría el dato [MET-16].
4. **Investigación:** lanza `bulonator-verificador` con `A1`, la salida `CASO/evidencias/verificador-A1.md` y el prefijo `E-A1-`. Si la afirmación tiene varias partes independientes, lanza uno por parte en el mismo mensaje (como máximo 3). Si es una cita atribuida o un posible bulo ya conocido, lanza también `bulonator-origen`, para los desmentidos previos y el origen.
5. **Textos breves:** `CASO/informe.md` es una versión breve de `templates/informe.md`, y `CASO/publicacion.md` lleva solo la publicación breve, un hilo corto (con el mínimo de publicaciones que fija `REFS/reglas.json`) y la respuesta para WhatsApp. Después ejecuta `python3 SCRIPT contar --bloques CASO/publicacion.md` y `python3 SCRIPT validar CASO`, y corrige todos los errores antes de la auditoría.
6. **Auditoría y cierre:** lanza `bulonator-auditor` (ronda 1) con la salida de `validar` y sigue las rondas de `REFS/flujo.md`. Después de la última, ejecuta `python3 SCRIPT resultado CASO --calificacion "<CAL>" [--subtipo <s>] --confianza <C> --dictamen <D> --rondas <N> [--cierre] [--idioma es]` y `python3 SCRIPT validar CASO`, que tiene que dar `ok: true` antes de entregar.
7. **Entrega en el chat:**
   - la calificación con su emoji y la confianza;
   - el dato correcto con su fuente oficial enlazada;
   - los matices: definición, periodo, comparación;
   - el texto para compartir;
   - las limitaciones.
