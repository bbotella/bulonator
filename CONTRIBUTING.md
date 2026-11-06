# Cómo contribuir a Bulonator

Gracias por ayudar a combatir la desinformación. Este proyecto tiene dos partes que se revisan con criterios distintos: el **código**, que es el script y el instalador, y la **metodología**, que incluye las skills, los agentes y las referencias.

## Reglas de oro

1. **Neutralidad.** No se aceptan cambios que traten de forma distinta los contenidos según quién los difunde o a quién afectan, ni listas de "fuentes enemigas". Las fuentes se valoran por criterios verificables: si son oficiales, si son primarias y si tienen desmentidos documentados.
2. **Toda fuente nueva lleva su URL comprobada.** Ejecuta `python3 tests/check_links.py` antes de abrir el PR.
3. **El script solo usa la biblioteca estándar de Python 3.9 o superior.** Las herramientas externas (ffmpeg, yt-dlp…) son opcionales y se detectan con `deps`. Si faltan, se declaran como limitación; el script no debe fallar.
4. **Sin pruebas no hay fusión.** Todo cambio en `bulonator.py` incluye pruebas en `tests/` que funcionan sin red.
5. **No se debilita la cadena de evidencias.** Ningún cambio puede permitir que un texto final contenga afirmaciones sin una entrada `E-…`, ni saltarse la auditoría.

## Tipos de contribución

| Quiero… | Qué hacer |
|---|---|
| Informar de un veredicto erróneo | Abre un issue con la plantilla **Error de verificación**. Adjunta `informe.md` y `03-auditoria.md` sin datos personales |
| Añadir una fuente oficial | Edita `skills/bulonator/references/fuentes-oficiales.md` (o `verificadores.md`) y comprueba los enlaces |
| Soportar una plataforma nueva | Añade una función `capture_<plataforma>()` y la detección en `detect_platform()`, con pruebas en `tests/test_bulonator.py` (usa fixtures, no la red) |
| Añadir una API oficial | Añade un subcomando en `bulonator.py`, documéntalo en `fuentes-oficiales.md` y en el agente que lo use |
| Cambiar la metodología o las calificaciones | Abre antes un issue de tipo **Propuesta de metodología** con la justificación y las fuentes (otras metodologías de verificación, estudios) |
| Traducir los textos de salida | Mejora `references/redaccion.md` y las plantillas. Mantén las citas en su idioma original |

## Entorno de desarrollo

```bash
git clone https://github.com/TU-USUARIO/bulonator.git
cd bulonator
python3 -m unittest discover -s tests -v       # pruebas unitarias y de estructura (sin red)
python3 tests/check_links.py                   # enlaces de la documentación (con red)
claude plugin validate .                       # manifiestos del plugin y del marketplace
claude --plugin-dir .                          # prueba las skills sin instalarlas
./install.sh --link                            # o instálalas con enlaces simbólicos al repositorio
```

Para probar un cambio en los agentes, ejecuta `/bulonator` sobre casos que ya estén resueltos por verificadores profesionales y compara el resultado. Hazlo con casos variados: un falso, uno descontextualizado, uno verdadero y uno sin pruebas. No incluyas datos personales en los casos de ejemplo que subas.

## Estilo

- **Idioma:** español para las skills, los agentes, las referencias y la documentación. En el código, los nombres de las funciones van en inglés y los mensajes para el usuario en español.
- **Prompts de los agentes:** instrucciones concretas y comprobables. Sus tres secciones obligatorias son **Lo que recibes**, **Seguridad** y **Salida**.
- **Python:** funciones pequeñas, sin dependencias externas, compatible con 3.9. Todo subcomando imprime JSON.
- **Commits:** mensajes descriptivos en español, por ejemplo `fuentes: añade el BOPA de Asturias` o `captura: soporte para Threads`.

## Versionado

Se sigue [SemVer](https://semver.org/lang/es/). Al publicar una versión, actualiza a la vez:

- `version` en `.claude-plugin/plugin.json`;
- `version` en `.claude-plugin/marketplace.json`;
- `VERSION` en `skills/bulonator/scripts/bulonator.py`;
- `CHANGELOG.md`.

La prueba `test_estructura` comprueba que las tres versiones coinciden.
