# Herramientas en Claude Code

Las instrucciones compartidas de Bulonator (las referencias y las secciones comunes de los agentes) nombran **capacidades**: `buscar`, `leer`, `boe`… Esta hoja dice cómo se usa cada una en Claude Code. Es el único sitio donde se hace esa correspondencia.

## Rutas

- **SCRIPT** es la ruta de `bulonator.py` y **CASO**, la ruta absoluta de la carpeta del caso. Las dos llegan en el prompt.
- Pasa siempre `--caso CASO` a las órdenes que lo admiten. Así la herramienta registra en el caso lo que ha devuelto y se puede citar como evidencia [EV-9].

## Capacidades

| Capacidad | En Claude Code |
|---|---|
| `buscar` | `WebSearch` (con `allowed_domains` para restringir dominios). Alternativa si hay buscador configurado: `python3 SCRIPT buscar "<consulta>" [--dominios boe.es,ine.es] [--max 10] --caso CASO`. Los resultados (extractos) nunca son evidencia [EV-4]. |
| `leer` | `python3 SCRIPT leer "<url>" --caso CASO`. Guarda el texto de la página en `CASO/evidencias/paginas/` y lo registra. **Es obligatorio abrir con `leer` toda página que se cite en una evidencia**, porque `validar` comprueba que la URL se abrió y que la cita literal aparece en el texto guardado. `WebFetch` solo sirve para orientarse. Si es un PDF y `leer` no puede extraer el texto, léelo con `Read` y registra el pasaje con `python3 SCRIPT leer "<url>" --caso CASO --desde-archivo <archivo.txt>`. Lo mismo con el texto obtenido con un navegador. |
| `boe` | `python3 SCRIPT boe "<palabras del título>" [--desde AAAAMMDD] [--hasta AAAAMMDD] --caso CASO` |
| `boe_sumario` | `python3 SCRIPT boe --sumario AAAAMMDD [palabras] --caso CASO` |
| `ine_operaciones` / `ine_tablas` / `ine_datos` | `python3 SCRIPT ine "<tema>"`, luego `ine --tablas <COD> "<filtro>"`, luego `ine --datos <ID_TABLA> --nult 5 --caso CASO`. Con `--caso`, cada dato queda registrado como una línea `serie \| periodo \| valor`, y esa línea es la cita literal. |
| `wayback` | `python3 SCRIPT wayback "<url>" [--guardar] --caso CASO` |
| `dominio` | `python3 SCRIPT dominio "<url o dominio>" --caso CASO` |
| `factcheck` | `python3 SCRIPT factcheck "<palabras>" --caso CASO` |
| `buscar_imagen` | `python3 SCRIPT buscar-imagen "<url de la imagen>"` |
| `media` | `python3 SCRIPT media <archivo> [--idioma es]` |
| `ver_imagen` | `Read` sobre el archivo de imagen (también los fotogramas, la hoja de contactos y el ELA) |
| `navegador` | Un MCP de navegador, si lo hay: solo páginas públicas, sin iniciar sesión |
| Datos de API (Eurostat, Banco Mundial…) | `curl -s` y `python3 -c` para leer el JSON; registra el resultado con `leer --desde-archivo` si lo vas a citar |

## Otras órdenes del script

No son capacidades: las usan la captura, el análisis multimedia y la auditoría.

| Orden | Para qué |
|---|---|
| `python3 SCRIPT capturar "<entrada>" --dir CASO [--archivar] [--nombre <nombre>]` | Captura automática de una URL, un archivo local o un texto. Con `--nombre`, es una captura secundaria y se guarda en `CASO/<nombre>.json` |
| `python3 SCRIPT contar --bloques CASO/publicacion.md` | Recuento de caracteres de cada bloque `text` con las reglas de cada plataforma [RED-9] |
| `python3 SCRIPT validar CASO` | Validación mecánica del caso. Imprime un JSON `{ok, errores, avisos}` y sale con 1 si hay errores |

## Notas

- `WebFetch` devuelve un resumen hecho por un modelo, no el texto original: no copies de ahí una cita [EV-6].
- Para confirmar una cifra o una frase, búscala con `Grep` en el texto guardado en `CASO/evidencias/paginas/`.
- Los PDF y documentos oficiales se descargan a `CASO/evidencias/docs/`.
- `wayback --guardar` solo cuando el caso pide archivar (`--archivar`).
- `media` admite también `--fotogramas N` (por defecto, 12).
- `buscar_imagen` devuelve además las coincidencias de Google Lens si `SERPAPI_API_KEY` está definida.
- `factcheck` consulta la base ClaimReview de Google si `GOOGLE_FACTCHECK_API_KEY` está definida.
- `navegador`: herramientas MCP como Claude in Chrome o Playwright. Respeta [MET-12].
