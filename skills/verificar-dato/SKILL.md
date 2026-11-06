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

Se aplican los principios innegociables de `/bulonator`: nada sin evidencia abierta en este caso, primero las fuentes primarias, la falta de pruebas no equivale a falsedad y las opiniones no se verifican. Lee `REFS/calificaciones.md` y `REFS/fuentes-oficiales.md`.

## Pasos

1. Si la afirmación está vacía o es una opinión pura, pide una afirmación comprobable o explica que no es verificable y señala qué datos la sostienen.
2. **Caso:** `python3 SCRIPT caso "<afirmación>"`. Toma la ruta del campo `caso` y guarda la afirmación literal en `CASO/02-afirmaciones.md`, formulada de forma comprobable (quién, qué, cuándo, dónde, cuánto, con qué definición) y con "quién tendría el dato".
3. Lanza **`bulonator-verificador`** con la afirmación (`A1`), CASO, la salida `evidencias/verificador-A1.md`, el prefijo `E-A1-` y las rutas de SCRIPT y REFS. Si la afirmación tiene varias partes independientes, lanza uno por parte en el mismo mensaje (como máximo 3). Si es una cita atribuida o un posible bulo ya conocido, lanza también **`bulonator-origen`** para buscar desmentidos previos y el origen.
4. Delibera con `REFS/calificaciones.md`. Escribe `CASO/informe.md` (versión breve de `templates/informe.md`) y `CASO/publicacion.md` (publicación breve, hilo corto de 3 o 4 publicaciones y respuesta para WhatsApp). Mide las publicaciones con `python3 SCRIPT contar --bloques CASO/publicacion.md`.
5. Lanza **`bulonator-auditor`** (ronda 1). Aplica los cambios y haz una segunda ronda si hay un VETO o si cambian la calificación o las cifras.
6. Entrega en el chat:
   - la calificación con su emoji y la confianza;
   - el dato correcto con su fuente oficial enlazada;
   - los matices: definición, periodo, comparación;
   - el texto para compartir;
   - las limitaciones.

Si no están disponibles los agentes `bulonator-*`, usa agentes de propósito general indicándoles que sigan las instrucciones de `${CLAUDE_SKILL_DIR}/../../agents/bulonator-verificador.md` (o `~/.claude/agents/`).
