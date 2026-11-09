"""Pruebas del motor con modelos simulados (FunctionModel de Pydantic AI): sin red y sin modelos reales.

Se omiten si no está instalado el extra [motor] (Python 3.11 o superior).
Ejecuta: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import pydantic_ai  # noqa: F401
    HAY_MOTOR = sys.version_info >= (3, 11)
except ImportError:
    HAY_MOTOR = False

if HAY_MOTOR:
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    from bulonator import cli, nucleo
    from bulonator.motor import (CapturaVacia, Config, Contexto, Desglose, Evento, Redaccion, Resultado,
                                 Servicios, analizar)
    from bulonator.motor import herramientas as H
    from bulonator.motor import render
    from bulonator.motor.esquemas import Evidencia, Ficha, InformeAgente
    from bulonator.motor.prompts import instrucciones
    from bulonator.motor.proceso import Analisis
    from bulonator.nucleo import documentos
    from bulonator.nucleo.caso import RegistroPaginas

import caso_ejemplo as ej  # noqa: E402

# ---------------------------------------------------------------------------
# Salidas de ejemplo de cada papel
# ---------------------------------------------------------------------------

EV_C = {"id": "E-C-01", "afirmacion": "A1", "fuente": "Publicación investigada (usuario particular)",
        "url": ej.URL_ORIGINAL, "tipo": "archivo",
        "cita_literal": "el Gobierno aprueba una paga de 2.000 euros al mes para todos los inmigrantes",
        "que_demuestra": "lo que dice el contenido", "que_no_demuestra": "que sea cierto",
        "copia_archivada": ej.URL_COPIA}
FICHA = {"resumen": "Publicación en X que afirma que el Gobierno aprueba una paga para inmigrantes.",
         "plataforma": "x", "autor": "un usuario particular", "autor_es_publico": False,
         "fecha_publicacion": "2026-11-01", "texto_literal": ej.TEXTO_TUIT, "evidencias": [EV_C]}
DESGLOSE = {"como_se_entiende": "Que el Gobierno ha aprobado una paga.", "afirmacion_central": "A1",
            "afirmaciones": [{"id": "A1", "texto": "El Gobierno ha aprobado una paga de 2.000 euros al mes",
                              "tipo": "norma", "quien_tendria_el_dato": "BOE y Moncloa", "prioridad": "central"}],
            "encargos": [{"papel": "verificador", "ids": ["A1"]}], "palabras_clave_origen": ["paga 2000 euros"]}
EV_BOE = {"id": "E-A1-01", "afirmacion": "A1", "fuente": "BOE, Real Decreto-ley 20/2020", "url": ej.URL_BOE,
          "tipo": "primaria-oficial", "cita_literal": "tiene por objeto la creación y regulación del ingreso mínimo vital",
          "que_demuestra": "qué es el IMV", "que_no_demuestra": "quién lo cobra"}
EV_MONCLOA = {"id": "E-A1-02", "afirmacion": "A1", "fuente": "La Moncloa, referencia del Consejo de Ministros",
              "url": ej.URL_MONCLOA, "tipo": "primaria-oficial",
              "cita_literal": "No figura ninguna prestación nueva para personas extranjeras",
              "que_demuestra": "que no se aprobó esa paga", "que_no_demuestra": "lo aprobado otros días"}
INFORME_A1 = {"elemento": "El Gobierno ha aprobado una paga", "calificacion": "FALSO", "subtipo": "inventado",
              "confianza": "ALTA", "razonamiento": "No consta (E-A1-02). El IMV es otra cosa (E-A1-01).",
              "evidencias": [EV_BOE, EV_MONCLOA]}
ORIGEN = {"elemento": "contenido completo", "calificacion": "FALSO", "confianza": "MEDIA",
          "razonamiento": "No se han localizado verificaciones previas.", "lagunas": ["Sin buscador configurado."]}
BREVE = ("❌ FALSO: no existe ninguna paga de 2.000 euros para inmigrantes.\n\n"
         f"La referencia del Consejo de Ministros no la recoge 👉 {ej.URL_MONCLOA}\n\n#Bulo")
REDACCION = {
    "calificacion": "FALSO", "subtipo": "inventado", "confianza": "ALTA",
    "titular": "No existe ninguna paga de 2.000 euros para inmigrantes: el bulo es falso",
    "resumen": "Circula que el Gobierno aprobó una paga [1]. La referencia del Consejo de Ministros no la recoge [2] "
               "y el ingreso mínimo vital es otra cosa [3].",
    "que_circula": ["**Formato y plataforma:** publicación en X [1]."],
    "afirmacion_central_cita": "el Gobierno aprueba una paga de 2.000 euros",
    "apartados": [{"id": "A1", "titulo": "El Gobierno aprueba una paga de 2.000 euros", "valoracion": "FALSO (inventado)",
                   "explicacion": "Según la referencia del Consejo de Ministros, no figura ninguna prestación nueva [2]. "
                                  "El BOE regula el IMV contra la pobreza [3].", "evidencias": ["E-A1-01", "E-A1-02"]}],
    "origen_y_difusion": "No constan verificaciones previas.",
    "por_que": "Dos fuentes primarias independientes lo contradicen [2][3].",
    "limitaciones": ["No hemos consultado todas las referencias del año."], "replica": "No procede.",
    "fuentes": [
        {"n": 1, "autor": "Usuario de X", "titulo": "Publicación", "fecha": "2026-11-01", "url": ej.URL_COPIA,
         "tipo": "archivo", "evidencias": ["E-C-01"]},
        {"n": 2, "autor": "La Moncloa", "titulo": "Referencia del Consejo de Ministros", "fecha": "2026-11-03",
         "url": ej.URL_MONCLOA, "tipo": "primaria-oficial", "evidencias": ["E-A1-02"]},
        {"n": 3, "autor": "BOE", "titulo": "Real Decreto-ley 20/2020", "fecha": "2020-05-29", "url": ej.URL_BOE,
         "tipo": "primaria-oficial", "evidencias": ["E-A1-01"]}],
    "publicaciones": {
        "breve": BREVE,
        "hilo_x": ["1/ ❌ FALSO: no existe ninguna paga de 2.000 euros para inmigrantes. Os explicamos por qué 🧵",
                   f"2/ Qué circula: una publicación que lo afirma. Copia archivada: {ej.URL_COPIA}",
                   f"3/ La referencia del Consejo de Ministros no recoge ninguna prestación nueva {ej.URL_MONCLOA}",
                   "4/ Fuentes: [2] La Moncloa [3] BOE. Verificado con asistencia de IA."],
        "largo": f"❌ FALSO: no existe esa paga.\n\nFuentes:\n[2] La Moncloa: {ej.URL_MONCLOA}\n[3] BOE: {ej.URL_BOE}\n\n"
                 "Verificado con asistencia de IA (Bulonator).",
        "mensajeria": f"*❌ FALSO*: no existe esa paga.\n\nFuente: {ej.URL_MONCLOA}"},
}
PALANTE = {"dictamen": "PALANTE", "resumen": "Cada frase tiene su evidencia."}
CAMBIOS = {"dictamen": "CAMBIOS", "resumen": "Un retoque.", "afecta_a_calificacion_o_cifras": False,
           "cambios_obligatorios": [{"ubicacion": "informe.md, resumen", "problema": "frase larga",
                                     "correccion": "acortarla"}]}
VETO = {"dictamen": "VETO", "resumen": "No se sostiene.", "motivo_veto": "falta una segunda fuente"}


def _texto_usuario(messages) -> str:
    for m in messages:
        for p in getattr(m, "parts", []):
            if isinstance(p, UserPromptPart):
                return p.content if isinstance(p.content, str) else " ".join(x for x in p.content if isinstance(x, str))
    return ""


class Guion:
    """Modelo simulado: decide la respuesta según el papel (de sus instrucciones) y el punto de la conversación."""

    def __init__(self, **cambios):
        self.salidas = {"captura": FICHA, "desglose": DESGLOSE, "origen": ORIGEN, "redactor": REDACCION,
                        "auditor": [PALANTE]}
        self.salidas.update(cambios)
        self.verificador_inventa = cambios.pop("verificador_inventa", 0)  # nº de respuestas finales inventadas
        self.llamadas: list = []
        self.modelo = FunctionModel(self, model_name="guion")

    def __call__(self, messages, info: AgentInfo) -> ModelResponse:
        papel = re.search(r"# Bulonator: (\w+)", info.instructions or "").group(1)
        previas = sum(1 for m in messages if isinstance(m, ModelResponse))
        self.llamadas.append((papel, previas, _texto_usuario(messages)))
        final = info.output_tools[0].name

        def salida(datos):
            return ModelResponse(parts=[ToolCallPart(final, datos)])

        if papel == "verificador":
            if previas == 0:
                return ModelResponse(parts=[ToolCallPart("leer", {"url": ej.URL_MONCLOA})])
            if previas == 1:
                return ModelResponse(parts=[ToolCallPart("leer", {"url": ej.URL_BOE})])
            if previas - 2 < self.verificador_inventa:
                malo = json.loads(json.dumps(INFORME_A1))
                malo["evidencias"][1]["cita_literal"] = "El Consejo de Ministros aprueba una paga de 2.000 euros"
                return salida(malo)
            return salida(INFORME_A1)
        if papel == "auditor":
            ronda = int(re.search(r"Ronda (\d+)", _texto_usuario(messages)).group(1))
            lista = self.salidas["auditor"]
            return salida(lista[min(ronda, len(lista)) - 1])
        return salida(self.salidas[papel])

    def de(self, papel: str) -> list:
        return [x for x in self.llamadas if x[0] == papel]


def servicios_falsos(vacia: bool = False):
    paginas = {ej.URL_BOE: ej.TEXTO_BOE, ej.URL_MONCLOA: ej.TEXTO_MONCLOA}

    def capturar(entrada, carpeta, archivar=False, nombre=None, **kw):
        caso = Path(carpeta)
        cap = dict(ej.CAPTURA, avisos=["CAPTURA VACÍA: no se obtuvo contenido."] if vacia else [])
        (caso / "captura.json").write_text(json.dumps(cap, ensure_ascii=False), encoding="utf-8")
        reg = RegistroPaginas(caso)
        reg.registrar(ej.URL_ORIGINAL, nucleo.texto_de_captura(cap), "captura")
        reg.registrar(ej.URL_COPIA, "Copias en archivos web de " + ej.URL_ORIGINAL, "wayback")
        return dict(cap, archivo_captura=str(caso / "captura.json"))

    def leer(url, caso, max_texto=4000, **kw):
        if url not in paginas:
            raise nucleo.HttpError(f"HTTP 404 al pedir {url}")
        e = RegistroPaginas(caso).registrar(url, paginas[url], "leer", titulo="Documento")
        return {"url": url, "url_final": url, "titulo": "Documento", "origen": "leer", "archivo": e["ruta"],
                "texto": paginas[url]}

    def no_usar(*a, **k):
        raise AssertionError("el guion no debería llamar a esta herramienta")

    return Servicios(capturar=capturar, leer=leer, buscar=no_usar, boe=no_usar, boe_sumario=no_usar,
                     ine_operaciones=no_usar, ine_tablas=no_usar, ine_datos=no_usar, wayback=no_usar,
                     dominio=no_usar, factcheck=no_usar, buscar_imagen=no_usar, analizar_media=no_usar)


@unittest.skipUnless(HAY_MOTOR, "requiere el extra [motor] y Python 3.11+")
class BaseMotor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.entorno = mock.patch.dict(os.environ, {k: "" for k in ("BULONATOR_SEARXNG_URL", "BRAVE_API_KEY",
                                                                     "TAVILY_API_KEY", "BULONATOR_BUSCADOR")})
        self.entorno.start()

    def tearDown(self):
        self.entorno.stop()
        self.tmp.cleanup()

    def config(self, guion, **kw):
        return Config(modelos={"defecto": guion.modelo}, carpeta_casos=Path(self.tmp.name), **kw)

    def analizar(self, guion, vacia=False, **kw):
        eventos = []
        caso = asyncio.run(analizar(ej.URL_ORIGINAL, self.config(guion, **kw), al_progresar=eventos.append,
                                    servicios=servicios_falsos(vacia)))
        return caso, eventos


class TestAnalisisCompleto(BaseMotor):
    def test_palante(self):
        guion = Guion()
        caso, eventos = self.analizar(guion)
        self.assertEqual(caso.validacion["errores"], [], caso.validacion["errores"])
        self.assertTrue(caso.aprobado)
        r = caso.resultado
        self.assertEqual((r.calificacion, r.subtipo, r.confianza), ("FALSO", "inventado", "ALTA"))
        self.assertEqual(r.generado_por, "motor")
        self.assertEqual((r.auditoria.dictamen, r.auditoria.rondas, r.auditoria.cierre), ("PALANTE", 1, False))
        self.assertEqual(r.afirmacion_central, "A1")
        self.assertEqual(r.fuentes[1].evidencias, ["E-A1-02"])
        self.assertEqual(len(r.publicaciones["hilo_x"]), 4)
        self.assertEqual(r.etiqueta, "❌ FALSO")
        for nombre in ("captura.json", "01-captura.md", "02-afirmaciones.md", "evidencias/verificador-A1.md",
                       "evidencias/origen.md", "informe.md", "publicacion.md", "03-auditoria.md", "resultado.json"):
            self.assertTrue((caso.ruta / nombre).is_file(), nombre)
        self.assertIn("### E-A1-02", caso.leer("evidencias/verificador-A1.md"))
        self.assertEqual([e.fase for e in eventos][:2], ["preparacion", "captura"])
        self.assertEqual(eventos[-1].fase, "cierre")
        self.assertGreater(caso.uso["verificador"]["peticiones"], 2)
        self.assertEqual(caso.uso["verificador"]["llamadas_herramientas"], 2)
        self.assertEqual(json.loads(caso.leer("resultado.json"))["calificacion"], "FALSO")
        self.assertEqual(nucleo.validar(caso.ruta)["ok"], True)
        self.assertEqual(caso.fallos, [])

    def test_reintento_por_cita_inventada(self):
        guion = Guion(verificador_inventa=1)
        caso, _ = self.analizar(guion)
        self.assertTrue(caso.validacion["ok"], caso.validacion["errores"])
        textos = [t for p, n, t in guion.de("verificador")]
        self.assertEqual(len(guion.de("verificador")), 4)  # leer, leer, salida inventada, salida corregida
        self.assertIn("No figura ninguna prestación nueva", caso.leer("evidencias/verificador-A1.md"))
        self.assertTrue(textos)

    def test_evidencia_descartada_tras_agotar_reintentos(self):
        guion = Guion(verificador_inventa=99)
        caso, _ = self.analizar(guion, reintentos=1)
        evidencias = caso.leer("evidencias/verificador-A1.md")
        self.assertNotIn("### E-A1-02", evidencias)
        self.assertIn("### E-A1-01", evidencias)
        self.assertIn("Se descartaron 1 evidencias", evidencias)
        # La redacción cita una evidencia que ya no existe: la validación final lo detecta
        self.assertFalse(caso.validacion["ok"])
        self.assertFalse(caso.aprobado)

    def test_cambios_sin_nueva_ronda(self):
        guion = Guion(auditor=[CAMBIOS])
        caso, _ = self.analizar(guion)
        self.assertEqual(len(guion.de("auditor")), 1)
        correcciones = [t for p, n, t in guion.de("redactor") if "Dictamen de la auditoría" in t]
        self.assertTrue(correcciones)
        self.assertEqual((caso.resultado.auditoria.dictamen, caso.resultado.auditoria.aprobado), ("CAMBIOS", True))

    def test_veto_y_regla_de_cierre(self):
        guion = Guion(auditor=[VETO, VETO])
        caso, _ = self.analizar(guion)
        auditoria = caso.leer("03-auditoria.md")
        self.assertIn("## Ronda 1", auditoria)
        self.assertIn("## Ronda 2", auditoria)
        self.assertTrue(any("regla de cierre" in t for p, n, t in guion.de("redactor")))
        a = caso.resultado.auditoria
        self.assertEqual((a.dictamen, a.rondas, a.cierre, a.aprobado), ("VETO", 2, True, False))
        self.assertFalse(caso.aprobado)

    def test_modo_profundo_con_dos_auditores(self):
        guion = Guion()
        caso, _ = self.analizar(guion, modo="profundo")
        self.assertEqual(len(guion.de("auditor")), 2)
        enfoques = " ".join(t for p, n, t in guion.de("auditor"))
        self.assertIn("fuentes y datos", enfoques)
        self.assertIn("metodología, ética y redacción", enfoques)

    def test_captura_vacia(self):
        with self.assertRaises(CapturaVacia):
            self.analizar(Guion(), vacia=True)

    def test_un_verificador_que_falla_no_para_el_caso(self):
        guion = Guion()
        original = guion.__call__

        def con_fallo(messages, info):
            if "# Bulonator: verificador" in (info.instructions or ""):
                return ModelResponse(parts=[TextPart("no sé hacerlo")])
            return original(messages, info)

        guion.modelo = FunctionModel(con_fallo, model_name="guion")
        caso, _ = self.analizar(guion, reintentos=0)
        self.assertTrue(any(f.startswith("verificador A1") for f in caso.fallos))
        self.assertTrue((caso.ruta / "resultado.json").is_file())


@unittest.skipUnless(HAY_MOTOR, "requiere el extra [motor] y Python 3.11+")
class TestPiezas(BaseMotor):
    def ctx(self, **kw):
        caso = Path(nucleo.crear_caso("x", self.tmp.name)["caso"])
        deps = Contexto(caso, Config(carpeta_casos=Path(self.tmp.name), max_texto_herramienta=500, **kw),
                        servicios_falsos(), "verificador", "E-A1-")
        return types.SimpleNamespace(deps=deps), caso

    def test_leer_por_trozos(self):
        ctx, caso = self.ctx()
        texto_largo = "palabra " * 200
        ctx.deps.servicios.leer = lambda url, caso, max_texto=0, **k: {
            "url": url, "texto": texto_largo, "archivo": RegistroPaginas(caso).registrar(url, texto_largo, "leer")["ruta"]}
        primero = H.leer(ctx, "https://boe.es/a")
        self.assertEqual(len(primero["texto"]), 500)
        self.assertEqual(primero["siguiente"], 500)
        segundo = H.leer(ctx, "https://boe.es/a", desde=primero["siguiente"])
        self.assertEqual(segundo["desde"], 500)
        self.assertIsNotNone(segundo["siguiente"])
        ctx.deps.servicios.leer = servicios_falsos().leer
        self.assertIn("error", H.leer(ctx, "https://no-existe.es/x"))

    def test_archivos_fuera_del_caso_y_archivar(self):
        ctx, caso = self.ctx()
        self.assertIn("error", H.ver_imagen(ctx, "../../../../etc/passwd"))
        self.assertIn("error", H.media(ctx, "/etc/hosts"))
        (caso / "media" / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\nxxxx")
        self.assertEqual(H.ver_imagen(ctx, "media/foto.png").media_type, "image/png")
        llamadas = []
        ctx.deps.servicios.wayback = lambda url, guardar=False, caso=None: llamadas.append(guardar) or {}
        H.wayback(ctx, "https://a.es", guardar=True)
        self.assertEqual(llamadas, [False])  # sin --archivar no se piden copias nuevas
        self.assertEqual(ctx.deps.llamadas[-1]["herramienta"], "wayback")

    def test_herramientas_por_papel(self):
        sin = Config()
        self.assertNotIn("buscar", H.nombres_para("verificador", sin))
        self.assertIn("ine_datos", H.nombres_para("verificador", sin))
        self.assertEqual(H.nombres_para("redactor", sin), [])
        with mock.patch.dict(os.environ, {"BRAVE_API_KEY": "k"}):
            self.assertIn("buscar", H.nombres_para("origen", Config()))
        self.assertNotIn("ver_imagen", H.nombres_para("multimedia", Config(vision=False)))

    def test_instrucciones_neutras_y_con_sus_referencias(self):
        cfg = Config()
        for papel in ("captura", "desglose", "verificador", "multimedia", "origen", "redactor", "auditor"):
            texto = instrucciones(papel, cfg)
            with self.subTest(papel=papel):
                for prohibido in ("python3 SCRIPT", "WebFetch", "WebSearch", "herramientas-claude.md", "## Salida",
                                  "Lo que recibes"):
                    self.assertNotIn(prohibido, texto)
                self.assertIn("# Referencia: reglas.json", texto)
        self.assertIn("# Referencia: fuentes-oficiales.md", instrucciones("verificador", cfg))
        self.assertIn("# Plantilla: templates/informe.md", instrucciones("redactor", cfg))
        self.assertIn("no hay buscador configurado", instrucciones("verificador", cfg))
        nativa = Config(modelos={"defecto": "anthropic:modelo"})
        self.assertTrue(nativa.busqueda_nativa("verificador"))
        self.assertIn("búsqueda web nativa", instrucciones("verificador", nativa, busqueda_nativa=True))

    def test_config(self):
        toml = Path(self.tmp.name, "c.toml")
        toml.write_text('modo = "rapido"\nidioma = "ca"\n[modelos]\ndefecto = "ollama:gpt-oss:20b"\n'
                        'auditor = "google:otro"\n', encoding="utf-8")
        c = Config.desde_toml(toml)
        self.assertEqual((c.modo, c.idioma, c.modelo("auditor"), c.modelo("verificador")),
                         ("rapido", "ca", "google:otro", "ollama:gpt-oss:20b"))
        self.assertEqual(c.proveedor("auditor"), "google")
        with self.assertRaises(ValueError):
            Config(modelos={"defecto": "x", "inventado": "y"})
        with self.assertRaises(ValueError):
            Config(modelos={"auditor": "x"})

    def test_encargos_respetan_el_modo(self):
        afirmaciones = [{"id": f"A{i}", "texto": "t", "tipo": "dato", "quien_tendria_el_dato": "INE"} for i in range(1, 7)]
        d = Desglose(como_se_entiende="x", afirmacion_central="A1", afirmaciones=afirmaciones)
        a = Analisis("x", Config(modo="rapido"))
        grupos, _ = a._encargos(d)
        self.assertEqual(grupos, [["A1"], ["A2", "A3", "A4", "A5", "A6"]])

    def test_ida_y_vuelta_de_los_documentos(self):
        """Lo que escribe el motor lo leen igual validar y resultado (los del plugin)."""
        r = Redaccion.model_validate(REDACCION)
        informe = render.informe_md(r, "caso", ej.URL_COPIA, "guion", "PALANTE en 1 ronda", ["leer"])
        cab = documentos.cabecera_del_informe(informe)
        self.assertEqual((cab["calificacion"], cab["subtipo"], cab["confianza"]), ("FALSO", "inventado", "ALTA"))
        self.assertEqual([f.url for f in documentos.fuentes_del_informe(informe)],
                         [ej.URL_COPIA, ej.URL_MONCLOA, ej.URL_BOE])
        self.assertEqual(documentos.apartados_del_informe(informe, "A")[0].evidencias, ["E-A1-01", "E-A1-02"])
        pubs = documentos.publicaciones(render.publicacion_md(r, "caso"))
        self.assertEqual(set(pubs), {"breve", "hilo_x", "largo", "mensajeria"})
        self.assertEqual(pubs["breve"], BREVE)
        ev = Evidencia.model_validate(EV_MONCLOA)
        md = "# Evidencias\n\n## Registro de evidencias\n\n" + render.evidencia_md(ev, "hoy")
        caso = Path(nucleo.crear_caso("x", self.tmp.name)["caso"])
        (caso / "evidencias" / "v.md").write_text(md, encoding="utf-8")
        leida = documentos.leer_evidencias(caso)[0]
        self.assertEqual((leida.id, leida.url, leida.tipo), ("E-A1-02", ej.URL_MONCLOA, "primaria-oficial"))
        self.assertEqual(leida.citas, [EV_MONCLOA["cita_literal"]])

    def test_resultado_del_plugin_cabe_en_el_modelo(self):
        caso = ej.crear_caso_ejemplo(self.tmp.name)
        res = nucleo.construir_resultado(caso, calificacion="FALSO", subtipo="inventado", confianza="ALTA",
                                         dictamen="PALANTE", rondas=1)
        self.assertEqual(Resultado.model_validate(res).fuentes[0].evidencias, ["E-C-01"])

    def test_esquemas_rechazan_valores_fuera_de_reglas(self):
        with self.assertRaises(ValueError):
            Redaccion.model_validate(dict(REDACCION, confianza="BAJA"))  # FALSO exige MEDIA o ALTA
        with self.assertRaises(ValueError):
            Evidencia.model_validate(dict(EV_BOE, tipo="blog"))
        with self.assertRaises(ValueError):
            InformeAgente.model_validate(dict(INFORME_A1, calificacion="BULO GORDO"))
        with self.assertRaises(ValueError):
            Desglose.model_validate(dict(DESGLOSE, afirmacion_central="A9"))
        self.assertEqual(Ficha.model_validate(FICHA).evidencias[0].id, "E-C-01")


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


@unittest.skipUnless(HAY_MOTOR, "requiere el extra [motor] y Python 3.11+")
class TestRamas(BaseMotor):
    """Caminos menos frecuentes del proceso: multimedia, ronda dirigida, fallos, presupuesto y búsqueda nativa."""

    def test_multimedia_con_imagenes_y_veredicto_obligatorio(self):
        guion = Guion(desglose=dict(DESGLOSE, multimedia=[{"id": "M1", "archivo": "media/foto.png",
                                                            "que_se_dice_que_muestra": "la paga",
                                                            "que_comprobar": "origen"}]))
        vistos = {"imagenes": 0, "finales": 0}
        original = guion.__call__

        def con_multimedia(messages, info):
            if "# Bulonator: multimedia" not in (info.instructions or ""):
                return original(messages, info)
            contenido = next(p.content for p in messages[0].parts if isinstance(p, UserPromptPart))
            vistos["imagenes"] = sum(1 for x in contenido if not isinstance(x, str))
            vistos["finales"] += 1
            informe = {"elemento": "foto", "calificacion": "SIN VEREDICTO", "confianza": "BAJA",
                       "razonamiento": "Sin origen localizado (E-M1-01).",
                       "evidencias": [{"id": "E-M1-01", "afirmacion": "M1", "fuente": "Análisis técnico (ELA)",
                                       "tipo": "herramienta", "cita_literal": "—", "que_demuestra": "nada concluyente",
                                       "que_no_demuestra": "manipulación"}]}
            if vistos["finales"] > 1:  # la primera vez falta el veredicto multimedia
                informe["veredicto_multimedia"] = "no-determinado"
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, informe)])

        guion.modelo = FunctionModel(con_multimedia, model_name="guion")
        servicios = servicios_falsos()
        capturar = servicios.capturar

        def capturar_con_foto(entrada, carpeta, **kw):
            res = capturar(entrada, carpeta, **kw)
            (Path(carpeta) / "media" / "foto.png").write_bytes(PNG)
            return res

        def analizar_media(archivo, *a, **k):
            ela = Path(archivo).parent / "analisis" / "ela.png"
            ela.parent.mkdir(parents=True, exist_ok=True)
            ela.write_bytes(PNG)
            return {"archivo": str(archivo), "ela": {"archivo": str(ela)}, "texto_largo": "x" * 20000}

        servicios.capturar, servicios.analizar_media = capturar_con_foto, analizar_media
        caso = asyncio.run(analizar(ej.URL_ORIGINAL, self.config(guion), servicios=servicios))
        self.assertEqual(vistos["imagenes"], 2)  # la foto y el ELA
        self.assertEqual(vistos["finales"], 2)
        self.assertIn("**Veredicto multimedia:** no-determinado", caso.leer("evidencias/multimedia-M1.md"))

    def test_ronda_dirigida_si_la_central_queda_sin_veredicto(self):
        guion = Guion()
        original = guion.__call__

        def dos_rondas(messages, info):
            if "# Bulonator: verificador" in (info.instructions or "") and "segunda ronda" not in _texto_usuario(messages):
                previas = sum(1 for m in messages if isinstance(m, ModelResponse))
                if previas >= 2:
                    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, dict(
                        INFORME_A1, calificacion="SIN VEREDICTO", confianza="BAJA", subtipo=None,
                        lagunas=["falta la referencia del día"]))])
            if "segunda ronda" in _texto_usuario(messages):
                self.assertIn("E-A1-03", _texto_usuario(messages))
                previas = sum(1 for m in messages if isinstance(m, ModelResponse))
                if previas == 0:
                    return ModelResponse(parts=[ToolCallPart("leer", {"url": ej.URL_BOE})])
                return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, dict(
                    INFORME_A1, evidencias=[dict(EV_BOE, id="E-A1-03")]))])
            return original(messages, info)

        guion.modelo = FunctionModel(dos_rondas, model_name="guion")
        caso, eventos = self.analizar(guion)
        self.assertIn("### E-A1-03", caso.leer("evidencias/verificador-A1-ronda2.md"))
        self.assertTrue(any("Ronda dirigida" in e.mensaje for e in eventos))

    def test_auditor_que_falla_cuenta_como_veto(self):
        guion = Guion()
        original = guion.__call__

        def sin_auditor(messages, info):
            if "# Bulonator: auditor" in (info.instructions or ""):
                return ModelResponse(parts=[TextPart("no puedo")])
            return original(messages, info)

        guion.modelo = FunctionModel(sin_auditor, model_name="guion")
        caso, _ = self.analizar(guion, reintentos=0)
        self.assertTrue(any(f.startswith("auditoría ronda 1") for f in caso.fallos))
        self.assertEqual(caso.resultado.auditoria.dictamen, "VETO")
        self.assertFalse(caso.aprobado)

    def test_presupuesto_de_tokens(self):
        from bulonator.motor import PresupuestoAgotado

        with self.assertRaises(PresupuestoAgotado):
            self.analizar(Guion(), max_tokens_caso=1)

    def test_eventos_asincronos_y_version_sincrona(self):
        eventos = []

        async def anotar(e):
            eventos.append(e.fase)

        guion = Guion()
        asyncio.run(analizar(ej.URL_ORIGINAL, self.config(guion), al_progresar=anotar, servicios=servicios_falsos()))
        self.assertIn("auditoria", eventos)
        from bulonator.motor import analizar_sync

        caso = analizar_sync(ej.URL_ORIGINAL, self.config(Guion()), servicios=servicios_falsos())
        self.assertTrue(caso.informe.startswith("# ❌ FALSO"))
        self.assertIn("```text", caso.publicacion)

    def test_busqueda_nativa_y_temperatura(self):
        guion = Guion()
        original = guion.__call__
        visto = {}

        def mirar(messages, info):
            if "# Bulonator: verificador" in (info.instructions or ""):
                visto["nativas"] = [type(x).__name__ for x in info.model_request_parameters.native_tools]
                visto["temperatura"] = (info.model_settings or {}).get("temperature")
            return original(messages, info)

        guion.modelo = FunctionModel(mirar, model_name="guion")
        self.analizar(guion, buscador="nativo", temperatura=None)
        self.assertEqual(visto["nativas"], ["WebSearchTool"])
        self.assertIsNone(visto["temperatura"])


@unittest.skipUnless(HAY_MOTOR, "requiere el extra [motor] y Python 3.11+")
class TestEnvoltorios(BaseMotor):
    """Cada herramienta llama al núcleo con el caso y deja constancia de la consulta."""

    def test_llaman_al_nucleo_con_el_caso(self):
        caso = Path(nucleo.crear_caso("x", self.tmp.name)["caso"])
        llamadas = {}

        def grabar(nombre, devolver=None):
            def f(*a, **k):
                llamadas[nombre] = (a, k)
                return devolver if devolver is not None else {"resultados": [1, 2]}
            return f

        nombres = ("buscar", "boe", "boe_sumario", "ine_operaciones", "ine_tablas", "ine_datos", "dominio",
                   "factcheck", "buscar_imagen", "analizar_media")
        servicios = Servicios(**{n: grabar(n) for n in nombres},
                              capturar=grabar("capturar", {"entrada": "u", "texto": "t", "media": []}))
        with mock.patch.dict(os.environ, {"BRAVE_API_KEY": "k"}):
            ctx = types.SimpleNamespace(deps=Contexto(caso, Config(idioma="ca"), servicios, "verificador", "E-A1-"))
            H.buscar(ctx, "paga", ["boe.es"])
        H.boe(ctx, "ingreso", desde="20200101")
        H.boe_sumario(ctx, "20261103")
        H.ine_operaciones(ctx, "paro")
        H.ine_tablas(ctx, "EPA", "tasa")
        H.ine_datos(ctx, "65334", 3)
        H.dominio(ctx, "https://ejemplo.es")
        H.factcheck(ctx, "paga")
        H.buscar_imagen(ctx, "https://a.es/x.jpg")
        (caso / "media" / "v.mp4").write_bytes(b"x")
        H.media(ctx, "media/v.mp4")
        self.assertEqual(H.capturar(ctx, "https://x.com/a/status/2", "incrustado")["texto"], "t")
        self.assertEqual(llamadas["buscar"][0][:5], ("paga", ["boe.es"], 8, "brave", "ca"))
        self.assertEqual(llamadas["boe"][1]["caso"], caso)
        self.assertEqual(llamadas["ine_datos"][0][:2], ("65334", 3))
        self.assertEqual(llamadas["factcheck"][0][1], "ca")
        self.assertEqual(llamadas["capturar"][1]["nombre"], "incrustado")
        self.assertEqual({ll["herramienta"] for ll in ctx.deps.llamadas},
                         {"buscar", "boe", "boe_sumario", "ine_operaciones", "ine_tablas", "ine_datos", "dominio",
                          "factcheck", "buscar_imagen"})
        self.assertTrue(all(ll["resultado"] == "2 resultados" for ll in ctx.deps.llamadas))

    def test_errores_y_resumenes(self):
        self.assertEqual(H._resumen({"error": "x"}), "error: x")
        self.assertEqual(H._resumen({"primera_copia": {"url": "u"}}), "hay copias archivadas")
        self.assertEqual(H._resumen("otra cosa"), "consultado")
        caso = Path(nucleo.crear_caso("x", self.tmp.name)["caso"])
        ctx = types.SimpleNamespace(deps=Contexto(caso, Config(vision=False), servicios_falsos()))
        self.assertIn("error", H.ver_imagen(ctx, "media/foto.png"))
        (caso / "media" / "doc.txt").write_text("x")
        ctx.deps.config = Config()
        self.assertIn("error", H.ver_imagen(ctx, "media/doc.txt"))
        self.assertEqual(len(H.toolset().tools), len(H.TODAS))
        ctx.deps.servicios.capturar = mock.Mock(side_effect=nucleo.HttpError("caído"))
        self.assertIn("error", H.capturar(ctx, "https://x.com/a/status/2", "b"))


@unittest.skipUnless(HAY_MOTOR, "requiere el extra [motor] y Python 3.11+")
class TestCasosLimite(BaseMotor):
    def test_config_toml_con_variables_y_modelos_objeto(self):
        toml = Path(self.tmp.name, "c.toml")
        toml.write_text('buscador = "$BUSCADOR_DE_PRUEBA"\n[modelos]\ndefecto = "ollama:x"\n', encoding="utf-8")
        with mock.patch.dict(os.environ, {"BUSCADOR_DE_PRUEBA": "brave"}):
            c = Config.desde_toml(toml)
        self.assertEqual((c.buscador, c.buscador_local()), ("brave", "brave"))
        self.assertFalse(c.busqueda_nativa("verificador"))
        self.assertTrue(Config(buscador="nativo").busqueda_nativa("verificador"))
        self.assertIsNone(Config(buscador="ninguno").buscador_local())
        objeto = Config(modelos={"defecto": Guion().modelo})
        self.assertEqual(objeto.nombre_modelo("auditor"), "function:guion")

    def test_cli_con_config_y_presupuesto(self):
        from bulonator.motor import PresupuestoAgotado

        toml = Path(self.tmp.name, "c.toml")
        toml.write_text('modo = "profundo"\n[modelos]\ndefecto = "ollama:x"\n', encoding="utf-8")
        vista = {}

        async def falso(entrada, config, al_progresar=None):
            vista["modo"], vista["archivar"] = config.modo, config.archivar
            al_progresar(Evento("captura", "hola"))
            raise PresupuestoAgotado("demasiado")

        buf, err = io.StringIO(), io.StringIO()
        with mock.patch("bulonator.motor.cli.analizar", falso), redirect_stdout(buf), mock.patch("sys.stderr", err):
            code = cli.main(["analizar", "https://x.com/a/status/1", "--config", str(toml), "--archivar",
                             "--idioma", "en"])
        self.assertEqual((code, vista), (5, {"modo": "profundo", "archivar": True}))
        self.assertIn("[captura] hola", err.getvalue())

    def test_esquemas_y_render_en_casos_limite(self):
        from bulonator.motor.esquemas import Dictamen, ElementoMultimedia, Encargo  # noqa: F401
        for datos in ({"dictamen": "CAMBIOS", "resumen": "x"}, {"dictamen": "VETO", "resumen": "x"},
                      {"dictamen": "QUIZÁ", "resumen": "x"}):
            with self.subTest(datos=datos), self.assertRaises(ValueError):
                Dictamen.model_validate(datos)
        for malo in (dict(REDACCION, subtipo="inventadísimo"),
                     dict(REDACCION, fuentes=[dict(REDACCION["fuentes"][1], n=2)])):
            with self.assertRaises(ValueError):
                Redaccion.model_validate(malo)
        with self.assertRaises(ValueError):
            ElementoMultimedia.model_validate({"id": "X1", "que_se_dice_que_muestra": "a", "que_comprobar": "b"})
        with self.assertRaises(ValueError):
            Desglose.model_validate(dict(DESGLOSE, encargos=[{"papel": "verificador", "ids": ["A7"]}]))
        with self.assertRaises(ValueError):
            Desglose.model_validate(dict(DESGLOSE, afirmacion_central=None))
        with self.assertRaises(ValueError):
            InformeAgente.model_validate(dict(INFORME_A1, veredicto_multimedia="raro"))
        self.assertEqual(render._cita("dijo «hola, qué tal»"), "dijo «hola, qué tal»")
        r = Redaccion.model_validate(dict(REDACCION, afirmacion_central_cita="", origen_y_difusion="", subtipo=None,
                                          replica=""))
        informe = render.informe_md(r, "c", None, "m", "r", [])
        self.assertIn("**Copia archivada:** no disponible", informe)
        self.assertNotIn("### Origen y difusión", informe)
        d = Dictamen.model_validate({"dictamen": "VETO", "resumen": "x", "motivo_veto": "falta fuente",
                                     "fuentes_reabiertas": ["BOE: ok"], "recomendados": ["algo"],
                                     "trazabilidad": [{"frase": "a|b", "referencia": "[1]", "estado": "OK"}]})
        md = render.auditoria_md("", 1, [d], ["fuentes y datos"])
        for trozo in ("## Ronda 1 (fuentes y datos)", "Motivo del veto", "### Fuentes reabiertas", "| a/b | [1] | OK |",
                      "### Recomendados"):
            self.assertIn(trozo, md)
        sin_nada = render.informe_agente_md("x", InformeAgente.model_validate(ORIGEN), [], "hoy")
        self.assertIn("no se hicieron búsquedas", sin_nada)


@unittest.skipUnless(HAY_MOTOR, "requiere el extra [motor] y Python 3.11+")
class TestCLIMotor(BaseMotor):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, json.loads(buf.getvalue())

    def test_analizar(self):
        guion = Guion()

        async def falso(entrada, config, al_progresar=None):
            self.assertEqual(config.modo, "rapido")
            self.assertEqual(config.modelo("auditor"), "google:otro")
            return await analizar(entrada, config.model_copy(update={"modelos": {"defecto": guion.modelo}}),
                                  al_progresar=al_progresar, servicios=servicios_falsos())

        with mock.patch("bulonator.motor.cli.analizar", falso):
            code, res = self.run_cli("analizar", ej.URL_ORIGINAL, "--modelo", "ollama:x", "--auditor", "google:otro",
                                     "--modo", "rapido", "--casos", self.tmp.name, "--silencioso")
        self.assertEqual(code, 0)
        self.assertEqual(res["resultado"]["calificacion"], "FALSO")
        self.assertTrue(res["aprobado"])

    def test_captura_vacia(self):
        async def falso(entrada, config, al_progresar=None):
            raise CapturaVacia(Path(self.tmp.name), ["CAPTURA VACÍA"])

        with mock.patch("bulonator.motor.cli.analizar", falso):
            code, res = self.run_cli("analizar", "https://x.com/a/status/1", "--silencioso")
        self.assertEqual(code, 4)
        self.assertIn("siguiente_paso", res)


if __name__ == "__main__":
    unittest.main()
