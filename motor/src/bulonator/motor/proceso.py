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
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel
from pydantic_ai import (Agent, BinaryContent, ModelMessagesTypeAdapter, ModelRetry, NativeOutput, PromptedOutput,
                         RunContext, UsageLimits, capture_run_messages)
from pydantic_ai.exceptions import (AgentRunError, ModelAPIError, ModelTimeoutError, UnexpectedModelBehavior,
                                   UsageLimitExceeded, UserError)

from .. import nucleo
from ..nucleo import documentos
from ..nucleo.caso import RegistroPaginas
from ..nucleo.reglas import calificaciones, modo as reglas_modo, reglas
from ..nucleo.validacion import capturas_registradas, problemas_de_evidencia
from . import render
from .config import PAPELES, Config, url_ollama
from .esquemas import (Apartado, Desglose, Dictamen, ElementoFicha, Evidencia, Ficha, InformeAgente, Publicaciones,
                       Redaccion, Resultado)
from .herramientas import POR_PAPEL, Contexto, Servicios, nombres_para, toolset
from .prompts import instrucciones

_GRAVEDAD = {"PALANTE": 0, "CAMBIOS": 1, "VETO": 2}
_RAZONAMIENTO = {"minimo": "minimal", "bajo": "low", "medio": "medium", "alto": "high"}
_PISTA_CONTEXTO = (" — Probablemente se ha llenado el contexto del modelo o se le ha ido la respuesta en razonar: con "
                   "Ollama, arráncalo con OLLAMA_CONTEXT_LENGTH=65536, y prueba también con --razonamiento bajo.")
_PISTA_TIEMPO = (" — Con Ollama local, las peticiones esperan en cola y esa espera cuenta: usa --concurrencia 1 o "
                 "sube timeout_peticion.")
_SIN_IMAGENES = ("No se adjuntan imágenes porque el modelo no las admite: no describas lo que no ves y decláralo "
                 "como limitación.")
_ENTREGA_FORZADA = ("Has llegado al límite de peticiones de este papel. No uses más herramientas: entrega ya la salida "
                    "con lo que tienes y declara en las lagunas lo que no has podido comprobar.")
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


class ModeloNoDisponible(Exception):
    """Un modelo de la configuración no se puede usar (falta la clave, el servidor no responde o el modelo
    no está descargado). Se detecta antes de crear el caso."""


class AnalisisFallido(Exception):
    """Un papel imprescindible (ficha, desglose o redacción) no ha podido terminar. ``caso`` es la carpeta
    con lo hecho hasta entonces."""

    def __init__(self, caso: Path, mensaje: str):
        super().__init__(mensaje)
        self.caso = caso


def comprobar_modelos(config: Config) -> dict:
    """Comprueba antes de empezar que cada modelo de la configuración se puede usar.

    Construye cada modelo con Pydantic AI (así salen los errores de clave o de proveedor) y, si alguno es
    de Ollama, comprueba que el servidor responde, que el modelo está descargado y que admite herramientas.
    Devuelve las capacidades conocidas de cada modelo de Ollama (``{"ollama:x": {"tools", "vision", …}}``).
    """
    from pydantic_ai.models import infer_model

    nombres = sorted({config.modelo(p) for p in PAPELES if isinstance(config.modelo(p), str)})
    for nombre in nombres:
        try:
            infer_model(nombre)
        except Exception as e:  # UserError de Pydantic AI o el error propio del SDK de cada proveedor
            raise ModeloNoDisponible(f"{nombre}: {type(e).__name__}: {e}") from e
    locales = [n.split(":", 1)[1] for n in nombres if n.startswith("ollama:")]
    if not locales:
        return {}
    base = os.environ.get("OLLAMA_BASE_URL") or url_ollama()
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=5) as r:
            disponibles = {m.get("id") for m in json.load(r).get("data", [])}
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ModeloNoDisponible(f"Ollama no responde en {base} ({e}). Arráncalo con "
                                 "«OLLAMA_CONTEXT_LENGTH=32768 ollama serve» o define OLLAMA_BASE_URL.") from e
    faltan = [m for m in locales if m not in disponibles and f"{m}:latest" not in disponibles]
    if faltan:
        raise ModeloNoDisponible(f"Ollama no tiene {', '.join(faltan)}: descárgalo con «ollama pull {faltan[0]}». "
                                 f"Disponibles: {', '.join(sorted(d for d in disponibles if d)) or 'ninguno'}.")
    capacidades = {}
    for modelo in locales:
        caps = _capacidades_ollama(base, modelo)
        if caps is not None and "tools" not in caps:
            raise ModeloNoDisponible(f"ollama:{modelo} no admite herramientas, que necesitan los papeles que "
                                     "investigan: elige un modelo que las tenga (aparecen en «ollama show <modelo>»).")
        if caps is not None:
            capacidades[f"ollama:{modelo}"] = caps
    return capacidades


def _capacidades_ollama(base: str, modelo: str) -> Optional[set]:
    """Capacidades de un modelo según la API nativa de Ollama (None si no se pueden saber)."""
    raiz = re.sub(r"/v1/?$", "", base.rstrip("/"))
    peticion = urllib.request.Request(raiz + "/api/show", data=json.dumps({"model": modelo}).encode(),
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=10) as r:
            caps = json.load(r).get("capabilities")
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return set(caps) if isinstance(caps, list) else None


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
        self._central_sin_investigar = False
        self._capacidades: dict = {}

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

    def admite_imagenes(self, papel: str) -> bool:
        """False si la visión está desactivada o si Ollama dice que el modelo del papel no ve imágenes."""
        caps = self._capacidades.get(self.config.nombre_modelo(papel))
        return self.config.vision and (caps is None or "vision" in caps)

    def _imagenes(self, rutas: list, papel: str = "multimedia") -> list:
        if not self.admite_imagenes(papel):
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
                     ids_previos=(), imagenes: Optional[list] = None, validador: Optional[Callable] = None,
                     con_herramientas: bool = True):
        cfg = self.config
        nativa = con_herramientas and "buscar" in POR_PAPEL[papel] and cfg.busqueda_nativa(papel)
        herramientas = [toolset(papel, cfg)] if con_herramientas and nombres_para(papel, cfg) else []
        tipo_salida = {"herramienta": salida, "nativa": NativeOutput(salida), "texto": PromptedOutput(salida)}[cfg.salida]
        agente = Agent(output_type=tipo_salida, deps_type=Contexto,
                       instructions=instrucciones(papel, cfg, nativa, con_herramientas),
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
        ajustes = self._ajustes()
        if ajustes:
            extra["model_settings"] = ajustes
        async with self.semaforo:
            with capture_run_messages() as mensajes:
                try:
                    res = await agente.run(contenido, deps=deps, model=cfg.modelo(papel),
                                           usage_limits=self._limites(), **extra)
                except UsageLimitExceeded as e:
                    self._guardar_conversacion(papel, mensajes, fallo=True)
                    if cfg.max_tokens_caso and "total_tokens" in str(e):
                        raise PresupuestoAgotado(f"{papel}: {e}") from e
                    if not herramientas or not mensajes:
                        raise
                    # Ha agotado las peticiones investigando: se le pide la salida con lo que tiene
                    await self._evento("investigacion", f"{papel}: límite de peticiones; se pide la salida con lo que hay")
                    res = await agente.run(_ENTREGA_FORZADA, message_history=list(mensajes), deps=deps,
                                           model=cfg.modelo(papel),
                                           usage_limits=UsageLimits(request_limit=cfg.reintentos + 2), **extra)
                except (AgentRunError, ModelAPIError) as e:
                    ruta = self._guardar_conversacion(papel, mensajes, fallo=True)
                    if ruta is not None:
                        e.add_note(f"Conversación del papel {papel}: {ruta}")
                    raise _con_pista(e) from e
        if cfg.guardar_conversaciones:
            self._guardar_conversacion(papel, res.all_messages())
        for k, v in _uso(res).items():
            self.uso[papel][k] += v
        self.llamadas.extend(deps.llamadas)
        return res.output, deps

    def _ajustes(self) -> dict:
        """Ajustes de cada petición al modelo (los que el proveedor no admite los descarta Pydantic AI)."""
        cfg = self.config
        ajustes = {"temperature": cfg.temperatura, "max_tokens": cfg.max_tokens_respuesta,
                   "timeout": cfg.timeout_peticion, "thinking": _RAZONAMIENTO.get(cfg.razonamiento)}
        return {k: v for k, v in ajustes.items() if v is not None}

    def _guardar_conversacion(self, papel: str, mensajes: list, fallo: bool = False) -> Optional[Path]:
        """Guarda los mensajes de un papel en <caso>/motor/ (sin las imágenes) para poder depurarlo."""
        if not mensajes or not self.caso.name:
            return None
        carpeta = self.caso / "motor"
        carpeta.mkdir(exist_ok=True)
        n = len(list(carpeta.glob(f"{papel}-*.json"))) + 1
        ruta = carpeta / f"{papel}-{n:02d}{'-fallo' if fallo else ''}.json"
        datos = _sin_binarios(json.loads(ModelMessagesTypeAdapter.dump_json(mensajes)))
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        return ruta

    # -- validadores de salida -----------------------------------------------------

    @staticmethod
    def _validador_evidencias(ctx: RunContext[Contexto], salida):
        """Comprueba cada evidencia contra lo registrado en el caso; tras el último reintento descarta las malas."""
        reg = RegistroPaginas(ctx.deps.caso)
        capturas = capturas_registradas(reg)
        patron = re.compile("^" + re.escape(ctx.deps.prefijo or "E-") + r"\d{2,}$")
        problemas, validas, vistos = [], [], set(ctx.deps.ids_previos)
        for ev in salida.evidencias:
            if not ev.afirmacion:
                ev.afirmacion = _afirmacion_del_prefijo(ctx.deps.prefijo)
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
        imagenes = self._imagenes([m.get("archivo") for m in captura.get("media", []) if m.get("archivo")], "captura")
        mensaje = ("Datos de la captura (JSON):\n" + _json(_sin_ruido(captura)) +
                   "\n\nPrefijo de tus evidencias: E-C- (desde E-C-01). " +
                   ("Las imágenes descargadas van adjuntas." if imagenes else _SIN_IMAGENES))
        mensaje += ("\n\nEn las evidencias E-C, la cita literal es un fragmento seguido del texto capturado (una o dos "
                    "frases, sin saltar partes). La copia archivada solo puede ser una de archivo_web.primera_copia o "
                    "archivo_web.copia_mas_reciente; «buscar_en_archive_today» no es una copia. Si no hay ninguna, "
                    "deja vacía la copia archivada: no hace falta archivar nada para hacer la ficha.")
        sin_url = captura.get("plataforma") in ("texto", "archivo_local")
        if sin_url:
            mensaje += ("\n\nLa entrada no es una URL: las evidencias E-C no llevan URL y su cita literal es un "
                        "fragmento copiado del texto capturado. No busques ni inventes una fuente: aquí solo se "
                        "describe lo que circula.")
        try:
            # Sin URL no hay nada que abrir: sin herramientas, los modelos pequeños no se confunden
            ficha, _ = await self._papel("captura", Ficha, mensaje, prefijo="E-C-", imagenes=imagenes,
                                         validador=self._validador_evidencias, con_herramientas=not sin_url)
        except (AgentRunError, ModelAPIError) as e:
            # La ficha solo describe lo capturado: si el modelo no la consigue, se hace sin modelo y se sigue
            self.fallos.append(f"ficha de la captura: no terminó ({type(e).__name__}: {e}); se usa una ficha mínima")
            await self._evento("captura", "El modelo no ha hecho la ficha: se usa una ficha mínima", error=str(e))
            ficha = self._ficha_minima(captura)
        hay_imagenes = any(_IMAGEN.search(str(m.get("archivo") or "")) for m in captura.get("media", []))
        if hay_imagenes and not imagenes:
            ficha.limitaciones.append("El modelo no ve imágenes: las imágenes capturadas no se han descrito.")
        render.escribir(self.caso / "01-captura.md", render.ficha_md(ficha, self._consultada()))
        await self._evento("captura", "Ficha del contenido lista")
        return ficha

    def _ficha_minima(self, captura: dict) -> Ficha:
        """Ficha hecha sin modelo a partir de la captura, con una evidencia E-C-01 que cita su texto."""
        texto = str(captura.get("texto") or captura.get("titulo") or "").strip()
        entrada = str(captura.get("entrada") or "")
        evidencias = []
        if texto:
            cita = re.split(r"(?<=[.!?])\s+", texto, maxsplit=1)[0][:300].strip()
            evidencias.append(Evidencia(
                id="E-C-01", afirmacion="contenido", fuente="Contenido capturado",
                url=entrada if entrada.startswith("http") else None, tipo="primaria-documental", cita_literal=cita,
                que_demuestra="qué dice exactamente el contenido", que_no_demuestra="que lo que dice sea cierto",
                copia_archivada=self._copia_actual))
        multimedia = [ElementoFicha(archivo=Path(m["archivo"]).relative_to(self.caso).as_posix()
                                    if Path(m["archivo"]).is_relative_to(self.caso) else m["archivo"],
                                    descripcion=f"{m.get('tipo') or 'archivo'} descargado (sin describir)")
                      for m in captura.get("media", []) if m.get("archivo")]
        return Ficha(resumen=texto[:280] or "Contenido sin texto capturado.",
                     plataforma=str(captura.get("plataforma") or "desconocida"),
                     autor="autor sin valorar (se trata como particular)", autor_es_publico=False,
                     fecha_publicacion=captura.get("fecha_publicacion"), texto_literal=texto, multimedia=multimedia,
                     evidencias=evidencias,
                     limitaciones=["La ficha la ha hecho el motor sin modelo, porque el papel de captura no terminó: "
                                   "no describe las imágenes ni valora si el autor es una figura pública."])

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
        ids_a = {a.id for a in d.afirmaciones}
        grupos, asignadas = [], set()
        for e in d.encargos:  # cada afirmación va a un solo verificador, aunque el desglose la repita
            if e.papel != "verificador":
                continue
            ids = [i for i in dict.fromkeys(e.ids) if i in ids_a and i not in asignadas]
            if ids:
                grupos.append(ids)
                asignadas.update(ids)
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
        imagenes = self._imagenes(rutas, "multimedia")
        mensaje = ("Elemento (JSON):\n" + _json(elemento) + "\n\nAnálisis técnico (JSON):\n" + _json(_recortar(analisis)) +
                   f"\n\nPrefijo de tus evidencias: {prefijo} (desde {prefijo}01). " +
                   ("Adjuntos: el archivo y las imágenes del análisis." if imagenes else _SIN_IMAGENES))
        inf, deps = await self._papel("multimedia", InformeAgente, mensaje, prefijo=prefijo,
                                      imagenes=imagenes, validador=self._validador_evidencias)
        if rutas and not imagenes:
            inf.lagunas.append("El modelo no ve imágenes: el elemento se ha analizado solo con sus metadatos y "
                               "el análisis técnico.")
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
        clave = next((k for k in informes if k.startswith("verificador") and central and central in _ids_de_la_tarea(k)),
                     None)
        if clave:
            inf = informes[clave]
            sin_resolver = inf.calificacion == "SIN VEREDICTO" or inf.confianza == "BAJA"
            if sin_resolver and (reglas_modo(self.config.modo)["segunda_ronda_investigacion"]
                                 or inf.calificacion == "SIN VEREDICTO"):
                await self._evento("investigacion", f"Ronda dirigida sobre {central}")
                ids = _ids_de_la_tarea(clave)
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
        partes.append("Las fuentes [n] son documentos abiertos con URL (las evidencias que la tienen). Los análisis de "
                      "las herramientas (metadatos, ELA, búsqueda inversa) no son fuentes con URL: cuéntalos en el texto "
                      "y en «Herramientas», y nunca inventes una URL para ellos.")
        if self._central_sin_investigar:
            partes.append(f"La afirmación central ({d.afirmacion_central}) no se ha podido investigar: su verificador "
                          "no terminó. No digas que se ha buscado o comprobado algo que no figura en los informes de "
                          "la investigación. Sin esa investigación, la calificación es SIN VEREDICTO "
                          "(ver calificaciones.md), y las limitaciones explican qué falta.")
        if captura.get("plataforma") in ("texto", "archivo_local"):
            partes.append("La entrada es un texto o un archivo sin URL: descríbelo en «Qué circula» sin número de "
                          "fuente y no inventes una URL ni una copia archivada para él. Las fuentes [n] son solo las "
                          "de las evidencias que tienen URL.")
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

    def _redaccion_minima(self, ficha: Ficha, d: Desglose, informes: dict) -> Redaccion:
        """SIN VEREDICTO hecho sin modelo: dice lo que circula y que no se ha podido verificar, sin fuentes."""
        etiqueta = calificaciones()["SIN VEREDICTO"]["etiqueta"]
        central = next((a for a in d.afirmaciones if a.id == d.afirmacion_central), None)
        que = (central.texto if central else ficha.texto_literal or ficha.resumen).strip().rstrip(".")
        lagunas = [x for inf in informes.values() for x in inf.lagunas]
        return Redaccion(
            calificacion="SIN VEREDICTO", confianza="BAJA",
            titular=f"Aún no podemos confirmar ni desmentir que {que[:160]}",
            resumen=f"Circula que {que[:200]}. No hemos podido completar la verificación con las herramientas y los "
                    "modelos disponibles, así que no damos un veredicto.",
            que_circula=[f"**Formato y plataforma:** {ficha.plataforma}."],
            apartados=[Apartado(id=a.id, titulo=a.texto, valoracion="SIN VEREDICTO",
                                explicacion="No se ha podido completar su verificación.") for a in d.afirmaciones],
            por_que="La investigación no ha llegado a una conclusión sostenida por evidencias registradas en el caso.",
            limitaciones=list(dict.fromkeys(self.fallos + lagunas)) or ["La verificación no se ha completado."],
            replica="No procede.",
            publicaciones=Publicaciones(
                breve=f"{etiqueta}: aún no podemos confirmar ni desmentir que {que[:150]}. Seguimos investigando.",
                mensajeria=f"*{etiqueta}*: aún no podemos confirmar ni desmentir que {que[:150]}.\n\n"
                           "Verificación incompleta, con asistencia de IA (Bulonator). Antes de reenviar, espera a "
                           "que haya una fuente fiable."))

    async def _sin_veredicto_de_respaldo(self, captura, ficha, d, informes, error) -> "Caso":
        """La redacción no ha superado la validación: el caso termina en un SIN VEREDICTO sin aprobar."""
        self.fallos.append(f"redacción: no terminó ({type(error).__name__}: {error}); se genera un SIN VEREDICTO "
                           "de respaldo, sin auditar")
        await self._evento("redaccion", "El modelo no ha redactado el informe: se genera un SIN VEREDICTO de respaldo")
        r = self._redaccion_minima(ficha, d, informes)
        self._escribir_textos(r, "sin auditar: redacción de respaldo")
        render.escribir(self.caso / "03-auditoria.md", "# Auditoría\n\n## Ronda 1\n\n**Dictamen: VETO**. No hay "
                        "auditoría: la redacción del modelo no superó la validación y el motor ha generado un SIN "
                        "VEREDICTO de respaldo. El caso no está aprobado.\n")
        res = nucleo.escribir_resultado(self.caso, calificacion=r.calificacion, confianza=r.confianza, dictamen="VETO",
                                       rondas=1, idioma=self.config.idioma, generado_por="motor",
                                       modelos=self._modelos(), cierre=True)
        validacion = nucleo.validar(self.caso)
        await self._evento("cierre", "SIN VEREDICTO de respaldo (sin aprobar)", calificacion="SIN VEREDICTO",
                           ok=validacion["ok"])
        return Caso(self.caso, Resultado.model_validate(res), validacion, [], self.uso, list(self.fallos))

    async def _corregir(self, captura, ficha, d, informes, previa, dictamenes, cierre=False) -> Optional[Redaccion]:
        """Corrección tras la auditoría. Si el modelo no la consigue, devuelve None y se conserva la anterior."""
        try:
            return await self._redactar(captura, ficha, d, informes, previa, dictamenes, cierre=cierre)
        except (AgentRunError, ModelAPIError) as e:
            self.fallos.append(f"corrección tras la auditoría: no terminó ({type(e).__name__}: {e}); "
                               "se conserva la redacción anterior y el caso no queda aprobado")
            await self._evento("auditoria", "No se ha podido aplicar la corrección: se conserva la redacción anterior")
            self._escribir_textos(previa, "pendiente de auditoría")
            return None

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
                       "\n\nDocumentos del caso:\n\n" + self._documentos_del_caso() +
                       "\n\nNota del motor: resultado.json se genera después de la auditoría, no lo pidas. Comprueba "
                       "sobre todo que cada afirmación de los textos se apoya en una evidencia o en una búsqueda que "
                       "figura en los documentos: lo que no figure no se ha comprobado.")
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
        self._capacidades = await asyncio.to_thread(comprobar_modelos, self.config) or {}
        if self.config.permitir_red_privada:
            nucleo.permitir_red_privada(True)
        try:
            return await self._ejecutar()
        except (AgentRunError, ModelAPIError, UserError) as e:
            raise AnalisisFallido(self.caso, f"{type(e).__name__}: {e}") from e

    async def _ejecutar(self) -> Caso:
        cfg = self.config
        captura = await self._capturar()
        self._copia_actual = self._copia(captura)
        ficha = await self._ficha(captura)
        d = await self._desglose(captura, ficha)
        informes = await self._investigar(captura, ficha, d)
        if d.afirmacion_central and not any(d.afirmacion_central in _ids_de_la_tarea(k) for k in informes
                                            if k.startswith("verificador")):
            # Sin investigar la afirmación central no hay base para ningún veredicto sobre los hechos
            self._central_sin_investigar = True
            self.fallos.append(f"la afirmación central ({d.afirmacion_central}) no se ha podido investigar: "
                               "el caso no puede quedar aprobado")
        await self._evento("redaccion", "Redactando el informe y los textos")
        try:
            r = await self._redactar(captura, ficha, d, informes)
        except (AgentRunError, ModelAPIError) as e:
            return await self._sin_veredicto_de_respaldo(captura, ficha, d, informes, e)
        rondas_max = reglas()["auditoria"]["rondas_max"]
        ronda, dictamenes, cierre = 1, await self._auditar(1), False
        while True:
            peor = max(dictamenes, key=lambda x: _GRAVEDAD[x.dictamen])
            if peor.dictamen == "PALANTE":
                break
            anterior = (r.calificacion, r.confianza)
            corregida = await self._corregir(captura, ficha, d, informes, r, dictamenes)
            if corregida is None:  # no se han podido aplicar los cambios: el caso no queda aprobado
                cierre = True
                break
            r = corregida
            necesita_ronda = peor.dictamen == "VETO" or any(x.afecta_a_calificacion_o_cifras for x in dictamenes) \
                or anterior != (r.calificacion, r.confianza)
            if not necesita_ronda:
                break  # cambios aplicados que no tocan la calificación ni las cifras [FLU-13]
            if ronda >= rondas_max:
                await self._evento("cierre", "Sin PALANTE tras la última ronda: se aplica la regla de cierre")
                r = await self._corregir(captura, ficha, d, informes, r, dictamenes, cierre=True) or r
                cierre = True
                break
            ronda += 1
            dictamenes = await self._auditar(ronda)
        peor = max(dictamenes, key=lambda x: _GRAVEDAD[x.dictamen])
        self._escribir_textos(r, f"{peor.dictamen} en {ronda} {'ronda' if ronda == 1 else 'rondas'}")
        res = nucleo.escribir_resultado(self.caso, calificacion=r.calificacion, subtipo=r.subtipo, confianza=r.confianza,
                                       dictamen=peor.dictamen, rondas=ronda, idioma=cfg.idioma, generado_por="motor",
                                       modelos=self._modelos(), cierre=cierre or self._central_sin_investigar)
        validacion = nucleo.validar(self.caso)
        await self._evento("cierre", f"{res['calificacion']} ({res['confianza']}), validación "
                                     f"{'correcta' if validacion['ok'] else 'con errores'}",
                           calificacion=res["calificacion"], ok=validacion["ok"])
        return Caso(self.caso, Resultado.model_validate(res), validacion,
                    [x for x in dictamenes], self.uso, list(self.fallos))


def _con_pista(error: Exception) -> Exception:
    """Añade la causa probable a los errores de «respuesta cortada sin contenido» (contexto lleno)."""
    texto = str(error)
    if "token limit" in texto and "before any response" in texto and isinstance(error, UnexpectedModelBehavior):
        nuevo = UnexpectedModelBehavior(texto + _PISTA_CONTEXTO)
    elif isinstance(error, ModelTimeoutError) or "timed out" in texto.lower():
        nuevo = UnexpectedModelBehavior(f"{type(error).__name__}: {texto}{_PISTA_TIEMPO}")
    else:
        return error
    nuevo.__notes__ = list(getattr(error, "__notes__", []))
    return nuevo


def _ids_de_la_tarea(clave: str) -> list:
    """«verificador A1, A3 (ronda 2)» → ["A1", "A3"]."""
    return clave.split(" ", 1)[1].split(" (")[0].split(", ") if " " in clave else []


def _afirmacion_del_prefijo(prefijo: Optional[str]) -> str:
    """«E-A1-» → «A1», «E-M2-» → «M2»; las de captura y origen se refieren al contenido entero."""
    m = re.match(r"^E-([AM]\d+)-$", prefijo or "")
    return m.group(1) if m else "contenido"


def _sin_binarios(datos: Any) -> Any:
    """Quita de una conversación serializada el contenido de las imágenes adjuntas (campos ``data`` largos)."""
    if isinstance(datos, dict):
        return {k: (f"<{len(v)} caracteres omitidos>" if k == "data" and isinstance(v, str) and len(v) > 1000
                    else _sin_binarios(v)) for k, v in datos.items()}
    if isinstance(datos, list):
        return [_sin_binarios(v) for v in datos]
    return datos


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
