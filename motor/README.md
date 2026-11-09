# Bulonator

**Verifica si una noticia, un tuit, una imagen, un vídeo o un audio es un bulo, con la metodología del periodismo de verificación (Maldita.es, IFCN/EFCSN) y tus propios modelos**: Ollama en local, OpenAI, Gemini, Anthropic o cualquier modelo que admita [Pydantic AI](https://pydantic.dev/docs/ai/overview/).

Para cada caso:

1. Captura el contenido.
2. Lo divide en afirmaciones comprobables.
3. Las contrasta con fuentes oficiales y primarias: BOE, INE y boletines, entre otras.
4. Analiza la multimedia.
5. Rastrea el origen y la difusión.
6. Somete el resultado a una auditoría con derecho a veto.
7. Entrega un informe con las fuentes citadas, textos listos para redes y un `resultado.json` que otros programas pueden leer.

Cada cita se comprueba con código contra la fuente que se abrió durante el caso.

```bash
pip install bulonator     # Python 3.11 o superior
bulonator analizar https://x.com/usuario/status/123 --modelo ollama:gpt-oss:20b --auditor google:<modelo>
```

```python
from bulonator import analizar, Config

caso = await analizar("https://…", Config(modelos={"defecto": "ollama:gpt-oss:20b"}))
caso.resultado.calificacion     # "FALSO"
caso.resultado.publicaciones    # textos para redes
caso.aprobado                   # auditoría superada y validación mecánica sin errores
```

- **Documentación del motor:** modelos, Ollama, búsqueda web y uso en servicios. Está en [docs/motor.md](https://github.com/bbotella/bulonator/blob/main/docs/motor.md).
- **Proyecto completo:** metodología, plugin para Claude Code y limitaciones. Está en <https://github.com/bbotella/bulonator>.
- **Solo las herramientas, sin modelos:** con Python 3.9 o superior y sin dependencias, usa [`bulonator-nucleo`](https://pypi.org/project/bulonator-nucleo/).

> Bulonator es una herramienta de apoyo: sus resultados los genera una IA y **una persona debe revisarlos antes de publicarlos**. No está afiliado a Maldita.es ni a ningún verificador.
