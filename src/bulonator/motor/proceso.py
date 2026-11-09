"""Proceso completo de un análisis: las fases de ``flujo.md`` fijadas en código.

1. Preparación y captura (núcleo, sin modelo) → 2. ficha de la captura → 3. desglose → 4. verificación,
análisis multimedia y rastreo de origen en paralelo → 5. redacción → 6. validación mecánica →
7. auditoría con rondas de corrección → 8. ``resultado.json``.

Cada papel trabaja con su metodología (``prompts.py``) y sus herramientas (``herramientas.py``); su salida
estructurada se valida con las mismas comprobaciones que ``bulonator validar`` antes de aceptarla.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent, ModelRetry, RunContext, UsageLimits
from pydantic_ai.exceptions import AgentRunError, ModelAPIError, UsageLimitExceeded

from .. import nucleo
from ..nucleo import documentos
from ..nucleo.caso import RegistroPaginas
from ..nucleo.reglas import modo as reglas_modo, reglas
from ..nucleo.validacion import capturas_registradas, problemas_de_evidencia
from . import render
from .config import PAPELES, Config
from .esquemas import Desglose, Dictamen, Evidencia, Ficha, InformeAgente, Redaccion, Resultado
from .herramientas import POR_PAPEL, Contexto, Servicios, nombres_para, toolset
from .prompts import instrucciones

_GRAVEDAD = {"PALANTE": 0, "CAMBIOS": 1, "VETO": 2}
_ENFOQUES = {1: [None], 2: ["fuentes y datos", "metodología, ética y redacción"]}
_IMAGEN = re.compile(r"\.(jpe?g|png|webp|gif)$", re.I)


@dataclass
class Evento:
    """Aviso de progreso: ``fase`` (captura, desglose, investigacion, redaccion, auditoria, cierre…)."""

    fase: str
    mensaje: str
    datos: dict = field(default_factory=dict)


class CapturaVacia(Exception):
    """No se ha obtenido el contenido: no se puede llegar a un veredicto [FLU-2]. Hay que pedir el texto,
    una captura de pantalla o el archivo y volver a empezar con eso."""

    def __init__(self, caso: Path, avisos: list):
        super().__init__("no se ha podido obtener el contenido: " + "; ".join(avisos))
        self.caso = caso
        self.avisos = avisos


class PresupuestoAgotado(Exception):
    """Se ha alcanzado ``Config.max_tokens_caso``."""


@dataclass
class Caso:
    """Resultado de ``analizar``: la carpeta del caso y su ``resultado.json``."""

    ruta: Path
    resultado: Resultado
    validacion: dict
    dictamenes: list
    uso: dict
    fallos: list = field(default_factory=list)

    def leer(self, nombre: str) -> str:
        return (self.ruta / nombre).read_text(encoding="utf-8")

    @property
    def informe(self) -> str:
        return self.leer("informe.md")

    @property
    def publicacion(self) -> str:
        return self.leer("publicacion.md")

    @property
    def aprobado(self) -> bool:
        """PALANTE del auditor y validación sin errores. Aun así, una persona debe revisarlo antes de publicar."""
        return self.resultado.auditoria.aprobado and self.validacion.get("ok", False)


def _json(obj: Any) -> str:
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=1, exclude_none=True)
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)


def _uso(resultado) -> dict:
    u = resultado.usage
    return {"peticiones": getattr(u, "requests", 0) or 0, "tokens_entrada": getattr(u, "input_tokens", 0) or 0,
            "tokens_salida": getattr(u, "output_tokens", 0) or 0, "llamadas_herramientas": getattr(u, "tool_calls", 0) or 0}


def _sin_ruido(captura: dict) -> dict:
    """Captura sin las partes que no aportan al modelo (respuestas brutas, metadatos de la página)."""
    return {k: v for k, v in nucleo.resumen_captura(captura, 6000).items() if k not in {"meta", "http", "metodo"}}


def _evidencia_para_validar(ev: Evidencia) -> documentos.Evidencia:
    campos = {"Fuente": ev.fuente, "URL": ev.url or "", "Tipo": ev.tipo, "Cita literal": render._cita(ev.cita_literal)}
    if ev.copia_archivada:
        campos["Copia archivada"] = ev.copia_archivada
    return documentos.Evidencia(ev.id, "", campos)


class Analisis:
    """Un análisis de principio a fin. Normalmente se usa a través de ``analizar``."""

    def __init__(self, entrada: str, config: Optional[Config] = None, servicios: Optional[Servicios] = None,
                 al_progresar: Optional[Callable] = None):
        self.entrada = entrada
        self.config = config or Config()
        self.servicios = servicios or Servicios()
        self.al_progresar = al_progresar
        self.semaforo = asyncio.Semaphore(self.config.concurrencia)
        self.uso: dict = {p: {"peticiones": 0, "tokens_entrada": 0, "tokens_salida": 0, "llamadas_herramientas": 0}
                          for p in PAPELES}
        self.fallos: list = []
        self.llamadas: list = []
        self.caso: Path = Path()
        self._copia_actual: Optional[str] = None

    # -- utilidades ----------------------------------------------------------------

    async def _evento(self, fase: str, mensaje: str, **datos) -> None:
        if self.al_progresar is None:
            return
        res = self.al_progresar(Evento(fase, mensaje, datos))
        if inspect.isawaitable(res):
            await res

    def _tokens_usados(self) -> int:
        return sum(u["tokens_entrada"] + u["tokens_salida"] for u in self.uso.values())

    def _limites(self) -> UsageLimits:
        restante = None
        if self.config.max_tokens_caso:
            restante = self.config.max_tokens_caso - self._tokens_usados()
            if restante <= 0:
                raise PresupuestoAgotado(f"se han usado {self._tokens_usados()} tokens")
        return UsageLimits(request_limit=self.config.max_peticiones, total_tokens_limit=restante)

    def _imagenes(self, rutas: list) -> list:
        if not self.config.vision:
            return []
        salida = []
        for r in rutas:
            p = Path(r)
            if p.is_file() and _IMAGEN.search(p.name) and p.stat().st_size <= 8 * 1024 * 1024:
                salida.append(BinaryContent(p.read_bytes(), media_type=mimetypes.guess_type(p.name)[0] or "image/jpeg"))
            if len(salida) >= self.config.max_imagenes:
                break
        return salida

    async def _papel(self, papel: str, salida: type, mensaje: str, *, prefijo: Optional[str] = None,
                     ids_previos=(), imagenes: Optional[list] = None, validador: Optional[Callable] = None):
        cfg = self.config
        nativa = "buscar" in POR_PAPEL[papel] and cfg.busqueda_nativa(papel)
        herramientas = [toolset(papel, cfg)] if nombres_para(papel, cfg) else []
        agente = Agent(output_type=salida, deps_type=Contexto, instructions=instrucciones(papel, cfg, nativa),
                       toolsets=herramientas, retries={"tools": 2, "output": cfg.reintentos},
                       name=f"bulonator-{papel}", defer_model_check=True)
        if validador is not None:
            agente.output_validator(validador)
        deps = Contexto(self.caso, cfg, self.servicios, papel, prefijo, set(ids_previos))
        contenido: Any = [mensaje, *imagenes] if imagenes else mensaje
        extra: dict = {}
        if nativa:
            from pydantic_ai.capabilities import WebSearch

            extra["capabilities"] = [WebSearch()]
        if cfg.temperatura is not None:
            extra["model_settings"] = {"temperature": cfg.temperatura}
        async with self.semaforo:
            try:
                res = await agente.run(contenido, deps=deps, model=cfg.modelo(papel), usage_limits=self._limites(),
                                       **extra)
            except UsageLimitExceeded as e:
                if cfg.max_tokens_caso and "total_tokens" in str(e):
                    raise PresupuestoAgotado(f"{papel}: {e}") from e
                raise
        for k, v in _uso(res).items():
            self.uso[papel][k] += v
        self.llamadas.extend(deps.llamadas)
        return res.output, deps

    # -- validadores de salida -----------------------------------------------------

    @staticmethod
    def _validador_evidencias(ctx: RunContext[Contexto], salida):
        """Comprueba cada evidencia contra lo registrado en el caso; tras el último reintento descarta las malas."""
        reg = RegistroPaginas(ctx.deps.caso)
        capturas = capturas_registradas(reg)
        patron = re.compile("^" + re.escape(ctx.deps.prefijo or "E-") + r"\d{2,}$")
        problemas, validas, vistos = [], [], set(ctx.deps.ids_previos)
        for ev in salida.evidencias:
            propios = []
            if not patron.match(ev.id):
                propios.append(f"el ID debe ser {ctx.deps.prefijo}NN (dos cifras o más)")
            if ev.id in vistos:
                propios.append("ID repetido: usa el siguiente número libre")
            vistos.add(ev.id)
            propios += [d for nivel, _, d in problemas_de_evidencia(_evidencia_para_validar(ev), reg, capturas)
                        if nivel == "error"]
            if propios:
                problemas.append(f"{ev.id}: " + "; ".join(propios))
            else:
                validas.append(ev)
        if isinstance(salida, InformeAgente) and ctx.deps.papel == "multimedia" and not salida.veredicto_multimedia:
            problemas.append("falta veredicto_multimedia (reglas.json → veredictos_multimedia)")
        if not problemas:
            return salida
        if ctx.retry < ctx.max_retries:
            raise ModelRetry("Corrige estas evidencias (abre la URL con `leer` y copia la cita literal del texto "
                             "devuelto, o elimina la evidencia):\n- " + "\n- ".join(problemas))
        descartadas = len(salida.evidencias) - len(validas)
        salida.evidencias = validas
        nota = f"Se descartaron {descartadas} evidencias que no superaron la validación mecánica."
        (salida.limitaciones if isinstance(salida, Ficha) else salida.lagunas).append(nota)
        return salida

    def _validador_redaccion(self, ctx: RunContext[Contexto], r: Redaccion) -> Redaccion:
        self._escribir_textos(r, "pendiente de auditoría")
        res = nucleo.validar(self.caso)
        errores = [e for e in res["errores"] if e["archivo"] in ("informe.md", "publicacion.md")]
        if errores and ctx.retry < ctx.max_retries:
            raise ModelRetry("La validación mecánica ha encontrado estos errores; corrígelos:\n- " + "\n- ".join(
                f"{e['archivo']} ({e.get('ubicacion') or '—'}): {e['detalle']}" for e in errores))
        return r

    # -- fases ---------------------------------------------------------------------

    def _copia(self, captura: dict) -> Optional[str]:
        web = captura.get("archivo_web") or {}
        for clave in ("nueva_copia", "primera_copia", "copia_mas_reciente"):
            if (web.get(clave) or {}).get("url"):
                return web[clave]["url"]
        return None

    async def _capturar(self) -> dict:
        datos = nucleo.crear_caso(self.entrada, str(self.config.carpeta_casos))
        self.caso = Path(datos["caso"])
        await self._evento("preparacion", f"Caso creado en {self.caso}", caso=str(self.caso))
        captura = await asyncio.to_thread(self.servicios.capturar, self.entrada, self.caso,
                                          archivar=self.config.archivar)
        if any("CAPTURA VACÍA" in a for a in captura.get("avisos", [])):
            raise CapturaVacia(self.caso, captura.get("avisos", []))
        await self._evento("captura", f"Capturado: {captura.get('plataforma')}", plataforma=captura.get("plataforma"))
        return captura

    async def _ficha(self, captura: dict) -> Ficha:
        imagenes = self._imagenes([m.get("archivo") for m in captura.get("media", []) if m.get("archivo")])
        mensaje = ("Datos de la captura (JSON):\n" + _json(_sin_ruido(captura)) +
                   "\n\nPrefijo de tus evidencias: E-C- (desde E-C-01). Las imágenes descargadas van adjuntas.")
        ficha, deps = await self._papel("captura", Ficha, mensaje, prefijo="E-C-", imagenes=imagenes,
                                        validador=self._validador_evidencias)
        render.escribir(self.caso / "01-captura.md", render.ficha_md(ficha, self._consultada()))
        await self._evento("captura", "Ficha del contenido lista")
        return ficha

    async def _desglose(self, captura: dict, ficha: Ficha) -> Desglose:
        limites = reglas_modo(self.config.modo)
        media = [m.get("archivo") for m in captura.get("media", []) if m.get("archivo")]
        mensaje = ("Ficha del contenido (JSON):\n" + _json(ficha) + "\n\nArchivos multimedia descargados: "
                   + (", ".join(Path(m).relative_to(self.caso).as_posix() for m in media) or "ninguno")
                   + f"\n\nLímites del modo {self.config.modo} (reglas.json → modos): {_json(limites)}")
        d, _ = await self._papel("desglose", Desglose, mensaje)
        render.escribir(self.caso / "02-afirmaciones.md",
                        render.desglose_md(d, self.caso.name, self.entrada, self._copia(captura)))
        await self._evento("desglose", f"{len(d.afirmaciones)} afirmaciones y {len(d.multimedia)} elementos multimedia",
                           afirmaciones=[a.id for a in d.afirmaciones])
        return d

    def _encargos(self, d: Desglose) -> tuple:
        limites = reglas_modo(self.config.modo)
        grupos = [e.ids for e in d.encargos if e.papel == "verificador" and e.ids]
        asignadas = {i for g in grupos for i in g}
        grupos += [[a.id] for a in d.afirmaciones if a.id not in asignadas]
        maximo = limites["verificadores"] or len(grupos)
        if len(grupos) > maximo:
            grupos = grupos[:maximo - 1] + [[i for g in grupos[maximo - 1:] for i in g]]
        elementos = [m for m in d.multimedia]
        if limites["multimedia"] is not None:
            elementos = elementos[:limites["multimedia"]]
        return grupos, elementos

    async def _verificar(self, d: Desglose, ficha: Ficha, ids: list, ronda: int = 1,
                         previas: Optional[InformeAgente] = None) -> Optional[InformeAgente]:
        afirmaciones = [a for a in d.afirmaciones if a.id in ids]
        prefijo = f"E-{ids[0]}-"
        existentes = {e.id for e in (previas.evidencias if previas else [])}
        inicio = len(existentes) + 1
        mensaje = ("Afirmaciones encargadas (JSON):\n" + _json([a.model_dump() for a in afirmaciones]) +
                   f"\n\nContexto: {ficha.resumen} Publicado: {ficha.fecha_publicacion or 'fecha desconocida'}."
                   f"\n\nPrefijo de tus evidencias: {prefijo} (numera desde {prefijo}{inicio:02d}).")
        if previas:
            mensaje += ("\n\nEs una segunda ronda dirigida: la primera dejó estas lagunas, que debes intentar cerrar:\n- "
                        + "\n- ".join(previas.lagunas or ["(sin lagunas declaradas)"]))
        inf, deps = await self._papel("verificador", InformeAgente, mensaje, prefijo=prefijo, ids_previos=existentes,
                                      validador=self._validador_evidencias)
        nombre = f"verificador-{ids[0]}" + (f"-ronda{ronda}" if ronda > 1 else "")
        render.escribir(self.caso / "evidencias" / f"{nombre}.md",
                        render.informe_agente_md(f"verificador {', '.join(ids)}", inf, deps.llamadas, self._consultada()))
        return inf

    async def _multimedia(self, elemento) -> Optional[InformeAgente]:
        analisis, rutas = {}, []
        archivo = None
        if elemento.archivo:
            archivo = Path(elemento.archivo)
            archivo = archivo if archivo.is_absolute() else self.caso / archivo
        if archivo and archivo.is_file():
            try:
                analisis = await asyncio.to_thread(self.servicios.analizar_media, archivo)
            except (FileNotFoundError, OSError) as e:
                analisis = {"error": str(e)}
            rutas = list(dict.fromkeys([str(archivo)] + [v for v in _rutas_en(analisis) if _IMAGEN.search(v)]))
        prefijo = f"E-{elemento.id}-"
        mensaje = ("Elemento (JSON):\n" + _json(elemento) + "\n\nAnálisis técnico (JSON):\n" + _json(_recortar(analisis)) +
                   f"\n\nPrefijo de tus evidencias: {prefijo} (desde {prefijo}01). Adjuntos: el archivo y las imágenes del análisis.")
        inf, deps = await self._papel("multimedia", InformeAgente, mensaje, prefijo=prefijo,
                                      imagenes=self._imagenes(rutas), validador=self._validador_evidencias)
        render.escribir(self.caso / "evidencias" / f"multimedia-{elemento.id}.md",
                        render.informe_agente_md(f"multimedia {elemento.id}", inf, deps.llamadas, self._consultada()))
        return inf

    async def _origen(self, captura: dict, ficha: Ficha, d: Desglose) -> Optional[InformeAgente]:
        datos = {"url": captura.get("entrada"), "plataforma": captura.get("plataforma"), "autor": ficha.autor,
                 "fecha": ficha.fecha_publicacion, "texto_literal": ficha.texto_literal,
                 "palabras_clave": d.palabras_clave_origen, "modo": self.config.modo}
        mensaje = "Contenido que hay que rastrear (JSON):\n" + _json(datos) + "\n\nPrefijo de tus evidencias: E-O- (desde E-O-01)."
        inf, deps = await self._papel("origen", InformeAgente, mensaje, prefijo="E-O-",
                                      validador=self._validador_evidencias)
        render.escribir(self.caso / "evidencias" / "origen.md",
                        render.informe_agente_md("origen", inf, deps.llamadas, self._consultada()))
        return inf

    async def _tarea(self, descripcion: str, corrutina):
        try:
            return await corrutina
        except (AgentRunError, ModelAPIError, PresupuestoAgotado, OSError, ValueError) as e:
            self.fallos.append(f"{descripcion}: no terminó ({type(e).__name__}: {e})")
            await self._evento("investigacion", f"{descripcion} falló", error=str(e))
            return None

    async def _investigar(self, captura: dict, ficha: Ficha, d: Desglose) -> dict:
        grupos, elementos = self._encargos(d)
        await self._evento("investigacion", f"{len(grupos)} verificadores, {len(elementos)} análisis multimedia y "
                                            "1 rastreo de origen")
        tareas = {f"verificador {', '.join(g)}": self._verificar(d, ficha, g) for g in grupos}
        tareas.update({f"multimedia {m.id}": self._multimedia(m) for m in elementos})
        tareas["origen"] = self._origen(captura, ficha, d)
        resultados = await asyncio.gather(*(self._tarea(k, v) for k, v in tareas.items()))
        informes = {k: v for k, v in zip(tareas, resultados) if v is not None}
        # Ronda dirigida [FLU-3]: en modo profundo, o si sin ella el veredicto sería SIN VEREDICTO
        central = d.afirmacion_central
        clave = next((k for k in informes if k.startswith("verificador") and central and central in k.split(" ", 1)[1]
                      .split(", ")), None)
        if clave:
            inf = informes[clave]
            sin_resolver = inf.calificacion == "SIN VEREDICTO" or inf.confianza == "BAJA"
            if sin_resolver and (reglas_modo(self.config.modo)["segunda_ronda_investigacion"]
                                 or inf.calificacion == "SIN VEREDICTO"):
                await self._evento("investigacion", f"Ronda dirigida sobre {central}")
                ids = clave.split(" ", 1)[1].split(", ")
                extra = await self._tarea(f"verificador {central} (ronda 2)", self._verificar(d, ficha, ids, 2, inf))
                if extra is not None:
                    informes[f"verificador {', '.join(ids)} (ronda 2)"] = extra
        return informes

    def _consultada(self) -> str:
        import datetime as dt

        return f"{dt.date.today().isoformat()}, con leer (motor de Bulonator)"

    def _herramientas_usadas(self) -> list:
        nombres = {"captura (Bulonator)"} | {ll["herramienta"] for ll in self.llamadas}
        return sorted(nombres)

    def _modelos(self) -> dict:
        return {p: self.config.nombre_modelo(p) for p in PAPELES}

    def _escribir_textos(self, r: Redaccion, rondas: str) -> None:
        modelos = ", ".join(sorted(set(self._modelos().values())))
        render.escribir(self.caso / "informe.md", render.informe_md(
            r, self.caso.name, self._copia_actual, modelos, rondas, self._herramientas_usadas()))
        render.escribir(self.caso / "publicacion.md", render.publicacion_md(r, self.caso.name))

    async def _redactar(self, captura, ficha, d, informes, previa=None, dictamenes=None, cierre=False) -> Redaccion:
        partes = [f"Entrada: {captura.get('entrada')} (plataforma: {captura.get('plataforma')}). "
                  f"Copia archivada del contenido: {self._copia_actual or 'no disponible'}.",
                  "Ficha (JSON):\n" + _json(ficha), "Desglose (JSON):\n" + _json(d),
                  "Informes de la investigación (JSON):\n" + _json({k: v.model_dump(exclude_none=True)
                                                                    for k, v in informes.items()})]
        if self.fallos:
            partes.append("Tareas que no terminaron (decláralo en las limitaciones):\n- " + "\n- ".join(self.fallos))
        if previa is not None:
            partes.append("Tu redacción anterior (JSON):\n" + _json(previa))
            partes.append("Dictamen de la auditoría (JSON):\n" + _json([x.model_dump() for x in dictamenes or []]))
            partes.append("Aplica la regla de cierre [FLU-14]: baja la calificación a la más prudente que se sostenga "
                          "(o SIN VEREDICTO) y explica la discrepancia." if cierre else
                          "Aplica todos los cambios obligatorios. Si hay un VETO, corrige el fondo (otra calificación o "
                          "menos confianza) con las evidencias disponibles.")
        r, _ = await self._papel("redactor", Redaccion, "\n\n".join(partes), validador=self._validador_redaccion)
        return r

    def _documentos_del_caso(self) -> str:
        nombres = ["informe.md", "publicacion.md", "02-afirmaciones.md", "01-captura.md"]
        nombres += [p.relative_to(self.caso).as_posix() for p in sorted((self.caso / "evidencias").glob("*.md"))]
        return "\n\n".join(f"### {n}\n\n{(self.caso / n).read_text(encoding='utf-8')}" for n in nombres
                           if (self.caso / n).is_file())

    async def _auditar(self, ronda: int) -> list:
        n = reglas_modo(self.config.modo)["auditores"]
        enfoques = _ENFOQUES.get(n, [None] * n)
        validacion = nucleo.validar(self.caso)
        medidas = nucleo.contar((self.caso / "publicacion.md").read_text(encoding="utf-8"), True)

        async def uno(enfoque):
            mensaje = (f"Ronda {ronda}. Enfoque: {enfoque or 'fuentes y datos; metodología, ética y redacción'}.\n\n"
                       "Resultado de la validación mecánica (JSON):\n" + _json(validacion) +
                       "\n\nMedida de las publicaciones (JSON):\n" + _json(medidas) +
                       "\n\nDocumentos del caso:\n\n" + self._documentos_del_caso())
            d, _ = await self._papel("auditor", Dictamen, mensaje)
            return d

        try:
            dictamenes = list(await asyncio.gather(*(uno(e) for e in enfoques)))
        except (AgentRunError, ModelAPIError, PresupuestoAgotado) as e:
            self.fallos.append(f"auditoría ronda {ronda}: no terminó ({type(e).__name__}: {e})")
            dictamenes = [Dictamen(dictamen="VETO", resumen="La auditoría no se pudo completar.",
                                   motivo_veto=f"La auditoría falló ({type(e).__name__}); hace falta repetirla.")]
            enfoques = [None]
        previo = (self.caso / "03-auditoria.md").read_text(encoding="utf-8") if (self.caso / "03-auditoria.md").is_file() else ""
        render.escribir(self.caso / "03-auditoria.md", render.auditoria_md(previo, ronda, dictamenes, enfoques))
        peor = max(dictamenes, key=lambda x: _GRAVEDAD[x.dictamen])
        await self._evento("auditoria", f"Ronda {ronda}: {peor.dictamen}", dictamen=peor.dictamen, ronda=ronda)
        return dictamenes

    async def ejecutar(self) -> Caso:
        cfg = self.config
        if cfg.permitir_red_privada:
            nucleo.permitir_red_privada(True)
        captura = await self._capturar()
        self._copia_actual = self._copia(captura)
        ficha = await self._ficha(captura)
        d = await self._desglose(captura, ficha)
        informes = await self._investigar(captura, ficha, d)
        await self._evento("redaccion", "Redactando el informe y los textos")
        r = await self._redactar(captura, ficha, d, informes)
        rondas_max = reglas()["auditoria"]["rondas_max"]
        ronda, dictamenes, cierre = 1, await self._auditar(1), False
        while True:
            peor = max(dictamenes, key=lambda x: _GRAVEDAD[x.dictamen])
            if peor.dictamen == "PALANTE":
                break
            anterior = (r.calificacion, r.confianza)
            r = await self._redactar(captura, ficha, d, informes, r, dictamenes)
            necesita_ronda = peor.dictamen == "VETO" or any(x.afecta_a_calificacion_o_cifras for x in dictamenes) \
                or anterior != (r.calificacion, r.confianza)
            if not necesita_ronda:
                break  # cambios aplicados que no tocan la calificación ni las cifras [FLU-13]
            if ronda >= rondas_max:
                await self._evento("cierre", "Sin PALANTE tras la última ronda: se aplica la regla de cierre")
                r = await self._redactar(captura, ficha, d, informes, r, dictamenes, cierre=True)
                cierre = True
                break
            ronda += 1
            dictamenes = await self._auditar(ronda)
        peor = max(dictamenes, key=lambda x: _GRAVEDAD[x.dictamen])
        self._escribir_textos(r, f"{peor.dictamen} en {ronda} {'ronda' if ronda == 1 else 'rondas'}")
        res = nucleo.escribir_resultado(self.caso, calificacion=r.calificacion, subtipo=r.subtipo, confianza=r.confianza,
                                       dictamen=peor.dictamen, rondas=ronda, idioma=cfg.idioma, generado_por="motor",
                                       modelos=self._modelos(), cierre=cierre)
        validacion = nucleo.validar(self.caso)
        await self._evento("cierre", f"{res['calificacion']} ({res['confianza']}), validación "
                                     f"{'correcta' if validacion['ok'] else 'con errores'}",
                           calificacion=res["calificacion"], ok=validacion["ok"])
        return Caso(self.caso, Resultado.model_validate(res), validacion,
                    [x for x in dictamenes], self.uso, list(self.fallos))


def _rutas_en(datos: Any) -> list:
    if isinstance(datos, dict):
        return [r for v in datos.values() for r in _rutas_en(v)]
    if isinstance(datos, list):
        return [r for v in datos for r in _rutas_en(v)]
    return [datos] if isinstance(datos, str) and ("/" in datos) else []


def _recortar(datos: Any, maximo: int = 12000) -> Any:
    texto = json.dumps(datos, ensure_ascii=False, default=str)
    if len(texto) <= maximo:
        return datos
    return {"resumen_recortado": texto[:maximo] + "…"}


async def analizar(entrada: str, config: Optional[Config] = None, *, al_progresar: Optional[Callable] = None,
                   servicios: Optional[Servicios] = None) -> Caso:
    """Analiza un enlace, un archivo o un texto y devuelve el caso con su ``resultado``.

    ``al_progresar`` recibe un ``Evento`` en cada paso (puede ser una función normal o asíncrona).
    Lanza ``CapturaVacia`` si no se puede obtener el contenido.
    """
    return await Analisis(entrada, config, servicios, al_progresar).ejecutar()


def analizar_sync(entrada: str, config: Optional[Config] = None, **kw) -> Caso:
    """Versión síncrona de ``analizar`` (no la uses dentro de un bucle de eventos ya en marcha)."""
    return asyncio.run(analizar(entrada, config, **kw))
