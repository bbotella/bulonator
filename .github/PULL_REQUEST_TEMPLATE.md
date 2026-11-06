## Qué cambia

<!-- Describe el cambio y por qué es necesario -->

## Tipo

- [ ] Código (`bulonator.py`, `install.sh`)
- [ ] Skills o agentes (prompts)
- [ ] Referencias: fuentes, verificadores, técnicas
- [ ] Metodología: calificaciones, reglas (enlaza el issue de propuesta)
- [ ] Documentación

## Comprobaciones

- [ ] `python3 -m unittest discover -s tests -v` pasa
- [ ] Si añado o cambio enlaces: `python3 tests/check_links.py` no da enlaces rotos
- [ ] Si toco el script: incluyo pruebas sin red y no añado dependencias externas
- [ ] Si toco los prompts: lo he probado con al menos un caso real ya resuelto por verificadores profesionales
- [ ] El cambio no debilita la cadena de evidencias ni la auditoría
- [ ] El cambio se aplica con neutralidad, sea quien sea el que difunde o el afectado
- [ ] Si cambia la versión: está actualizada en `plugin.json`, `marketplace.json`, `bulonator.py` y `CHANGELOG.md`
