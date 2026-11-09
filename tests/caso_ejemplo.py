"""Caso de ejemplo completo y válido para las pruebas de validar, resultado y el motor."""
from __future__ import annotations

import json
from pathlib import Path

URL_ORIGINAL = "https://x.com/usuario/status/123"
URL_COPIA = "https://web.archive.org/web/20261101000000/https://x.com/usuario/status/123"
URL_BOE = "https://www.boe.es/buscar/act.php?id=BOE-A-2020-15678"
URL_MONCLOA = "https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2026/20261103.aspx"

TEXTO_TUIT = "ÚLTIMA HORA: el Gobierno aprueba una paga de 2.000 euros al mes para todos los inmigrantes."
TEXTO_BOE = ("Real Decreto-ley 20/2020, de 29 de mayo, por el que se establece el ingreso mínimo vital.\n"
             "Artículo 1. Objeto. El presente real decreto-ley tiene por objeto la creación y regulación del "
             "ingreso mínimo vital como prestación dirigida a prevenir el riesgo de pobreza.")
TEXTO_MONCLOA = ("Referencia del Consejo de Ministros del 3 de noviembre de 2026. El Consejo de Ministros ha "
                 "aprobado un acuerdo sobre infraestructuras. No figura ninguna prestación nueva para "
                 "personas extranjeras.")

EVIDENCIAS_A1 = f"""# Evidencias: verificador A1

## Afirmación / elemento analizado
El Gobierno aprueba una paga de 2.000 euros al mes para todos los inmigrantes.

## Conclusión propuesta
- **Calificación propuesta:** FALSO (inventado)
- **Confianza:** ALTA
- **Razonamiento:** La referencia del Consejo de Ministros no la recoge (E-A1-02). El IMV no es eso (E-A1-01).

## Registro de evidencias

### E-A1-01
- **Afirmación:** A1
- **Fuente:** Agencia Estatal BOE. "Real Decreto-ley 20/2020"
- **URL:** {URL_BOE}
- **Tipo:** primaria-oficial
- **Fecha del documento:** 2020-05-29
- **Consultada:** 2026-11-09, con leer
- **Cita literal:** "tiene por objeto la creación y regulación del ingreso mínimo vital como prestación dirigida a prevenir el riesgo de pobreza"
- **Ubicación:** artículo 1
- **Qué demuestra:** que el IMV es una prestación contra la pobreza.
- **Qué NO demuestra:** quién lo cobra.

### E-A1-02
- **Afirmación:** A1
- **Fuente:** La Moncloa. "Referencia del Consejo de Ministros"
- **URL:** {URL_MONCLOA}
- **Tipo:** primaria-oficial
- **Fecha del documento:** 2026-11-03
- **Consultada:** 2026-11-09, con leer
- **Cita literal:** "No figura ninguna prestación nueva para personas extranjeras"
- **Ubicación:** final de la referencia
- **Qué demuestra:** que no se aprobó esa paga ese día.
- **Qué NO demuestra:** lo aprobado otros días.

## Búsquedas realizadas
| Consulta / fuente | Herramienta | Resultado |
|---|---|---|
| "paga 2000 euros inmigrantes" en boe.es | buscar | 0 resultados relevantes |

## Lagunas y limitaciones
- Ninguna relevante.
"""

EVIDENCIAS_CAPTURA = f"""# Evidencias: captura

## Registro de evidencias

### E-C-01
- **Afirmación:** A1
- **Fuente:** Publicación investigada (usuario particular)
- **URL:** {URL_ORIGINAL}
- **Tipo:** archivo
- **Fecha del documento:** 2026-11-01
- **Consultada:** 2026-11-09, con capturar
- **Cita literal:** "el Gobierno aprueba una paga de 2.000 euros al mes para todos los inmigrantes"
- **Ubicación:** texto de la publicación
- **Qué demuestra:** lo que dice el contenido.
- **Qué NO demuestra:** que sea cierto.
- **Copia archivada:** {URL_COPIA}
"""

AFIRMACIONES = """# Desglose del caso: ejemplo

## Afirmación central
**A1**: El Gobierno ha aprobado una paga de 2.000 euros al mes para todos los inmigrantes.

## Afirmaciones verificables

| ID | Afirmación (comprobable) | Tipo | ¿Quién tendría el dato? | Prioridad |
|---|---|---|---|---|
| A1 | Paga de 2.000 euros aprobada | norma | BOE, Moncloa | central |
"""

INFORME = f"""# ❌ FALSO: No existe ninguna paga de 2.000 euros para inmigrantes: el bulo es falso

> **Caso:** ejemplo · **Verificado el:** 09/11/2026 · **Calificación:** FALSO (inventado) · **Confianza:** ALTA
> **Metodología:** Bulonator 1.1.0.

## En resumen

Circula que el Gobierno aprobó una paga de 2.000 euros [1]. La referencia del Consejo de Ministros no la recoge [2] y el ingreso mínimo vital es otra cosa [3].
<!-- E-C-01, E-A1-01, E-A1-02 -->

## Qué circula

- **Formato y plataforma:** publicación en X [1].
- **Copia archivada:** {URL_COPIA}

## Qué hemos comprobado

### A1: El Gobierno aprueba una paga de 2.000 euros → FALSO (inventado)

Según la referencia del Consejo de Ministros, «no figura ninguna prestación nueva» [2]. El BOE regula el IMV contra la pobreza [3].
<!-- Evidencias: E-A1-01, E-A1-02 -->

## Por qué lo calificamos como FALSO

Dos fuentes primarias independientes lo contradicen [2][3].

## Lo que no hemos podido comprobar

- No hemos podido consultar todas las referencias del año.

## Derecho de réplica

No procede.

## Fuentes

[1] Usuario de X, publicación del 1 de noviembre de 2026. Copia: {URL_COPIA} (consultado el 2026-11-09). archivo.
[2] La Moncloa, «Referencia del Consejo de Ministros», 3 de noviembre de 2026. {URL_MONCLOA} (consultado el 2026-11-09; copia: —). primaria-oficial.
[3] BOE, «Real Decreto-ley 20/2020», 29 de mayo de 2020. {URL_BOE} (consultado el 2026-11-09; copia: —). primaria-oficial.

## Metodología y transparencia

- **Asistencia de IA:** este informe lo ha elaborado un sistema de agentes de IA.
"""

PUBLICACION = f"""# Textos para compartir: ejemplo

## 1. Publicación breve (X, Bluesky, Threads, Mastodon): 280 como máximo, ponderado para X

```text
❌ FALSO: no existe ninguna paga de 2.000 euros para inmigrantes.

La referencia del Consejo de Ministros no la recoge 👉 {URL_MONCLOA}

#Bulo
```

## 2. Hilo para X (de 4 a 8 publicaciones de 280 como máximo cada una)

```text
1/ ❌ FALSO: no existe ninguna paga de 2.000 euros para inmigrantes. Os explicamos por qué 🧵
```

```text
2/ Qué circula: una publicación que lo afirma. Copia archivada: {URL_COPIA}
```

```text
3/ La referencia del Consejo de Ministros no recoge ninguna prestación nueva {URL_MONCLOA}
```

```text
4/ Fuentes: [2] La Moncloa [3] BOE. Verificado el 09/11/2026 con asistencia de IA (metodología inspirada en Maldita.es).
```

## 3. Texto largo (Facebook, Instagram, LinkedIn, Telegram)

```text
❌ FALSO: no existe ninguna paga de 2.000 euros para inmigrantes.

Fuentes:
[2] La Moncloa: {URL_MONCLOA}
[3] BOE: {URL_BOE}

Verificado el 09/11/2026 con asistencia de IA (Bulonator).
```

## 4. Respuesta para grupos de WhatsApp o Telegram

```text
*❌ FALSO*: no existe esa paga.

Fuente: {URL_MONCLOA}
```
"""

CAPTURA = {
    "entrada": URL_ORIGINAL, "plataforma": "x", "texto": TEXTO_TUIT,
    "autor": {"nombre": "Usuario", "usuario": "usuario"},
    "metricas": {"retweets": 1500},
    "archivo_web": {"primera_copia": {"url": URL_COPIA, "fecha": "20261101000000"}},
    "media": [], "avisos": [], "metodo": [],
}


def crear_caso_ejemplo(base) -> Path:
    """Crea en ``base`` un caso válido: captura, páginas registradas, evidencias, informe y textos."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from bulonator.nucleo import RegistroPaginas, crear_caso, texto_de_captura

    caso = Path(crear_caso("ejemplo", str(base))["caso"])
    (caso / "captura.json").write_text(json.dumps(CAPTURA, ensure_ascii=False), encoding="utf-8")
    reg = RegistroPaginas(caso)
    reg.registrar(URL_ORIGINAL, texto_de_captura(CAPTURA), "captura")
    reg.registrar(URL_BOE, TEXTO_BOE, "leer", titulo="Real Decreto-ley 20/2020")
    reg.registrar(URL_MONCLOA, TEXTO_MONCLOA, "leer", titulo="Referencia del Consejo de Ministros")
    reg.registrar(URL_COPIA, "Copias en archivos web de " + URL_ORIGINAL, "wayback")
    (caso / "evidencias" / "verificador-A1.md").write_text(EVIDENCIAS_A1, encoding="utf-8")
    (caso / "evidencias" / "captura.md").write_text(EVIDENCIAS_CAPTURA, encoding="utf-8")
    (caso / "02-afirmaciones.md").write_text(AFIRMACIONES, encoding="utf-8")
    (caso / "informe.md").write_text(INFORME, encoding="utf-8")
    (caso / "publicacion.md").write_text(PUBLICACION, encoding="utf-8")
    return caso
