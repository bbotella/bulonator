"""Pruebas del núcleo: registro del caso, leer, buscar, fuentes, validar, resultado y red (sin Internet).

Las pruebas de ``leer`` y ``buscar`` levantan un servidor HTTP local.
Ejecuta: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bulonator import cli  # noqa: E402
from bulonator import nucleo as n  # noqa: E402
from bulonator.nucleo import busqueda as mod_buscar  # noqa: E402
from bulonator.nucleo import fuentes as mod_fuentes  # noqa: E402
from bulonator.nucleo import lectura as mod_leer  # noqa: E402
from bulonator.nucleo import red  # noqa: E402
from bulonator.nucleo.validacion import cita_en_texto, fragmentos  # noqa: E402
import caso_ejemplo as ej  # noqa: E402

HTML = """<!doctype html><html lang="es"><head><title>Nota oficial</title>
<meta property="og:title" content="Nota oficial del ministerio"><script>var x = "no debe salir";</script></head>
<body><nav>Inicio | Prensa</nav><main><h1>Nota oficial del ministerio</h1>
<div class="cuerpo">El ministerio desmiente que exista una paga de 2.000 euros.</div>
<p>La medida <b>no figura</b> en el BOE.</p></main><footer>Aviso legal</footer></body></html>"""


class _Manejador(BaseHTTPRequestHandler):
    rutas: dict = {}

    def do_GET(self):  # noqa: N802
        ruta = self.path.split("?")[0]
        if ruta not in self.rutas:
            self.send_response(404)
            self.end_headers()
            return
        estado, ctype, cuerpo, extra = self.rutas[ruta]
        self.send_response(estado)
        self.send_header("Content-Type", ctype)
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)
        type(self).ultima_consulta = self.path

    def log_message(self, *args):
        pass


class ConServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _Manejador.rutas = {
            "/nota": (200, "text/html; charset=utf-8", HTML.encode("utf-8"), {}),
            "/datos.json": (200, "application/json", json.dumps({"valor": 10.29, "serie": "paro"}).encode(), {}),
            "/doc.pdf": (200, "application/pdf", b"%PDF-1.4\n%binario\n", {}),
            "/imagen.png": (200, "image/png", b"\x89PNG\r\n\x1a\n", {}),
            "/redirige": (302, "text/plain", b"", {"Location": "http://169.254.169.254/latest/meta-data"}),
            "/search": (200, "application/json", json.dumps({"results": [
                {"title": "BOE", "url": "https://www.boe.es/buscar/doc.php?id=1", "content": "extracto"},
                {"title": "Otro", "url": "https://ejemplo.com/x", "content": "fuera de dominio"},
                {"title": "BOE 2", "url": "https://boe.es/diario_boe/2", "content": "otro"},
            ]}).encode(), {}),
        }
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.caso = Path(n.crear_caso("prueba", self.tmp.name)["caso"])
        red.permitir_red_privada(True)

    def tearDown(self):
        red.permitir_red_privada(False)
        self.tmp.cleanup()


class TestRed(unittest.TestCase):
    def test_bloquea_direcciones_internas_y_esquemas(self):
        for url in ("http://127.0.0.1/x", "http://10.0.0.1/", "http://169.254.169.254/latest", "http://[::1]/",
                    "http://localhost:8080/", "http://192.168.1.1/admin", "file:///etc/passwd", "ftp://x.org/a"):
            with self.subTest(url=url), self.assertRaises(n.HttpError):
                n.comprobar_destino(url)

    def test_permite_direcciones_publicas_y_permiso_expreso(self):
        n.comprobar_destino("https://8.8.8.8/")
        red.permitir_red_privada(True)
        try:
            n.comprobar_destino("http://127.0.0.1/")
        finally:
            red.permitir_red_privada(False)
        with mock.patch.dict(os.environ, {"BULONATOR_PERMITIR_RED_PRIVADA": "1"}):
            n.comprobar_destino("http://10.0.0.1/")
        with self.assertRaises(n.HttpError):
            n.comprobar_destino("file:///etc/passwd")  # el permiso no abre otros esquemas

    def test_redireccion_a_direccion_interna(self):
        req = urllib.request.Request("https://8.8.8.8/")
        with self.assertRaises(n.HttpError):
            red._RedireccionSegura().redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/")

    def test_capturar_rechaza_url_interna(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(n.HttpError):
            n.capturar("http://127.0.0.1:9/", tmp, sin_archivo=True)


class TestRegistro(unittest.TestCase):
    def test_normalizar_url(self):
        self.assertEqual(n.normalizar_url("https://www.twitter.com/a/status/1/"), "x.com/a/status/1")
        self.assertEqual(n.normalizar_url("http://x.com/a/status/1#frag"), "x.com/a/status/1")
        self.assertEqual(n.normalizar_url("boe.es/a?id=1"), "boe.es/a?id=1")

    def test_registrar_y_recuperar(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = n.RegistroPaginas(tmp)
            reg.registrar("https://www.boe.es/a", "texto uno", "leer")
            reg.registrar("https://boe.es/a", "texto dos", "leer")  # misma URL normalizada: la última gana
            reg.registrar("https://boe.es/a", "api", "boe")
            reg.registrar("https://bit.ly/x", "corto", "leer", url_final="https://boe.es/final")
            self.assertEqual(len(reg.entradas()), 3)
            self.assertEqual({t for _, t in reg.textos_de("http://boe.es/a/")}, {"texto dos", "api"})
            self.assertEqual(reg.textos_de("https://boe.es/final")[0][1], "corto")
            with self.assertRaises(ValueError):
                reg.registrar("https://boe.es", "x", "inventado")

    def test_busquedas(self):
        with tempfile.TemporaryDirectory() as tmp:
            n.registrar_busqueda(tmp, "paga", "searxng", [{"url": "https://a.es"}], ["boe.es"])
            n.registrar_busqueda(tmp, "nada", "searxng", [])
            filas = n.busquedas(tmp)
            self.assertEqual([f["resultados"] for f in filas], [1, 0])

    def test_captura_de_texto_queda_registrada(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = n.crear_caso("x", tmp)["caso"]
            n.capturar("Dicen que hay una paga", caso)
            textos = [t for e, t in [(e, n.RegistroPaginas(caso).texto(e)) for e in n.RegistroPaginas(caso).entradas()]]
            self.assertIn("Dicen que hay una paga", textos)

    def test_texto_de_captura(self):
        t = n.texto_de_captura({"texto": "Hola", "autor": {"nombre": "Ana"}, "avisos": ["x"], "metricas": {"likes": 3}})
        self.assertTrue(t.startswith("Hola"))
        self.assertIn("autor.nombre: Ana", t)
        self.assertIn("metricas.likes: 3", t)
        self.assertNotIn("avisos", t)


class TestLeer(ConServidor):
    def test_html_guarda_todo_el_texto_visible(self):
        res = n.leer(self.base + "/nota", self.caso)
        self.assertEqual(res["origen"], "leer")
        guardado = Path(res["archivo"]).read_text(encoding="utf-8")
        self.assertIn("El ministerio desmiente que exista una paga de 2.000 euros.", guardado)  # texto en un div
        self.assertIn("La medida no figura en el BOE.", guardado)
        self.assertNotIn("no debe salir", guardado)
        self.assertEqual(res["titulo"], "Nota oficial del ministerio")
        self.assertEqual(len(n.RegistroPaginas(self.caso).de(self.base + "/nota")), 1)

    def test_json_y_recorte(self):
        res = n.leer(self.base + "/datos.json", self.caso, max_texto=10)
        self.assertIn("recortado", res["texto"])
        self.assertIn("10.29", Path(res["archivo"]).read_text(encoding="utf-8"))

    def test_pdf_sin_texto_extraible(self):
        with mock.patch.object(mod_leer, "texto_pdf", return_value=None):
            res = n.leer(self.base + "/doc.pdf", self.caso)
        self.assertFalse(res["texto_extraido"])
        self.assertTrue(Path(res["pdf"]).is_file())
        self.assertEqual(n.RegistroPaginas(self.caso).entradas(), [])

    def test_pdf_con_texto(self):
        with mock.patch.object(mod_leer, "texto_pdf", return_value="[página 1]\nArtículo 1. Objeto."):
            res = n.leer(self.base + "/doc.pdf", self.caso)
        self.assertIn("Artículo 1", Path(res["archivo"]).read_text(encoding="utf-8"))

    def test_binario_no_se_lee(self):
        with self.assertRaises(n.HttpError):
            n.leer(self.base + "/imagen.png", self.caso)

    def test_desde_archivo(self):
        txt = Path(self.tmp.name, "pasaje.txt")
        txt.write_text("Pasaje copiado del navegador", encoding="utf-8")
        res = n.leer("https://ejemplo.es/muro", self.caso, desde_archivo=str(txt))
        self.assertEqual(res["origen"], "manual")
        self.assertEqual(n.RegistroPaginas(self.caso).de("https://ejemplo.es/muro")[0]["origen"], "manual")

    def test_redireccion_a_metadatos_bloqueada(self):
        red.permitir_red_privada(False)
        real = red.comprobar_destino

        def solo_el_servidor_de_prueba(url):
            return None if url.startswith(self.base) else real(url)

        with mock.patch.object(red, "comprobar_destino", solo_el_servidor_de_prueba):
            with self.assertRaises(n.HttpError) as ctx:
                n.leer(self.base + "/redirige", self.caso)
        self.assertIn("169.254.169.254", str(ctx.exception))


class TestBuscar(ConServidor):
    def test_searxng_filtra_dominios_y_registra(self):
        red.permitir_red_privada(False)  # la instancia propia de SearXNG se permite aunque sea local
        with mock.patch.dict(os.environ, {"BULONATOR_SEARXNG_URL": self.base, "BULONATOR_BUSCADOR": ""}):
            res = n.buscar("paga inmigrantes", ["boe.es"], caso=self.caso)
        self.assertEqual(res["buscador"], "searxng")
        self.assertEqual([r["titulo"] for r in res["resultados"]], ["BOE", "BOE 2"])
        self.assertIn("site%3Aboe.es", _Manejador.ultima_consulta)
        self.assertEqual(n.busquedas(self.caso)[0]["resultados"], 2)

    def test_sin_buscador(self):
        limpio = {k: "" for k in ("BULONATOR_SEARXNG_URL", "BRAVE_API_KEY", "TAVILY_API_KEY", "BULONATOR_BUSCADOR")}
        with mock.patch.dict(os.environ, limpio):
            self.assertIsNone(n.buscador_configurado())
            with self.assertRaises(ValueError):
                n.buscar("algo")

    def test_brave_y_tavily(self):
        llamadas = []

        def falso(url, headers=None, timeout=None, datos=None, interna_permitida=False):
            llamadas.append((url, headers, datos))
            if "brave" in url:
                return {"web": {"results": [{"title": "T", "url": "https://ine.es/a", "description": "d"}]}}
            return {"results": [{"title": "U", "url": "https://ine.es/b", "content": "c"}]}

        with mock.patch.object(mod_buscar, "http_json", falso), \
                mock.patch.dict(os.environ, {"BRAVE_API_KEY": "k1", "TAVILY_API_KEY": "k2", "BULONATOR_BUSCADOR": ""}):
            self.assertEqual(n.buscar("paro", ["ine.es"], buscador="brave")["resultados"][0]["url"], "https://ine.es/a")
            self.assertEqual(n.buscar("paro", ["ine.es"], buscador="tavily")["resultados"][0]["url"], "https://ine.es/b")
        self.assertEqual(llamadas[0][1]["X-Subscription-Token"], "k1")
        self.assertEqual(llamadas[1][2]["include_domains"], ["ine.es"])

    def test_error_queda_anotado(self):
        with mock.patch.dict(mod_buscar._FUNCIONES, {"searxng": mock.Mock(side_effect=n.HttpError("caído"))}), \
                mock.patch.dict(os.environ, {"BULONATOR_SEARXNG_URL": self.base}):
            with self.assertRaises(n.HttpError):
                n.buscar("x", buscador="searxng", caso=self.caso)
        self.assertEqual(n.busquedas(self.caso)[0]["error"], "caído")


class TestFuentesRegistradas(unittest.TestCase):
    def test_ine_datos_registra_lineas(self):
        datos = [{"Nombre": "Tasa de paro. Total Nacional.", "Unidad": {"Nombre": "Porcentaje"},
                  "Data": [{"NombrePeriodo": "2026T2", "Valor": 10.29, "Fecha": 0}]}]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod_fuentes, "http_json", return_value=datos):
            res = n.ine_datos("65334", caso=tmp)
            texto = n.RegistroPaginas(tmp).textos_de(res["url_tabla"])[0][1]
        self.assertEqual(texto, "Tasa de paro. Total Nacional. | 2026T2 | 10.29 | Porcentaje")

    def test_boe_registra_resultados(self):
        datos = {"data": [{"identificador": "BOE-A-2020-5493", "titulo": "Real Decreto-ley 20/2020",
                           "url_html_consolidada": "https://www.boe.es/buscar/act.php?id=BOE-A-2020-5493",
                           "fecha_publicacion": "20200601"}]}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod_fuentes, "http_json", return_value=datos):
            n.boe("ingreso mínimo vital", caso=tmp)
            entradas = n.RegistroPaginas(tmp).entradas()
        self.assertEqual(entradas[0]["origen"], "boe")


class TestCitas(unittest.TestCase):
    def test_fragmentos(self):
        self.assertEqual(fragmentos("uno dos tres […] cuatro cinco seis [trad.: four]"),
                         ["uno dos tres", "cuatro cinco seis"])

    def test_cita_en_texto(self):
        texto = "El Consejo de Ministros ha aprobado hoy, 3 de noviembre, un acuerdo sobre trans-\nporte urbano."
        self.assertEqual(cita_en_texto("ha aprobado hoy, 3 de noviembre", texto), "exacta")
        self.assertEqual(cita_en_texto("ha aprobado hoy 3 de noviembre", texto), "puntuacion")
        self.assertEqual(cita_en_texto("un acuerdo sobre transporte urbano", texto), "exacta")
        self.assertEqual(cita_en_texto("ha aprobado una paga", texto), "no")
        self.assertEqual(cita_en_texto("hoy", texto), "corta")
        self.assertEqual(cita_en_texto("«El Consejo de Ministros» … «un acuerdo sobre»", texto), "exacta")


class TestValidarYResultado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.caso = ej.crear_caso_ejemplo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def codigos(self, res, tipo="errores"):
        return {e["codigo"] for e in res[tipo]}

    def reescribir(self, nombre, viejo, nuevo):
        p = self.caso / nombre
        texto = p.read_text(encoding="utf-8")
        self.assertIn(viejo, texto)
        p.write_text(texto.replace(viejo, nuevo), encoding="utf-8")

    def test_caso_valido(self):
        res = n.validar(self.caso)
        self.assertEqual(res["errores"], [], res["errores"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["resumen"]["citas_comprobadas"], 3)
        self.assertIn("sin_resultado", self.codigos(res, "avisos"))

    def test_cita_que_no_esta_en_la_fuente(self):
        self.reescribir("evidencias/verificador-A1.md", "No figura ninguna prestación nueva",
                        "Se aprueba una prestación nueva")
        self.assertIn("cita_no_encontrada", self.codigos(n.validar(self.caso)))

    def test_url_no_abierta(self):
        self.reescribir("evidencias/verificador-A1.md", ej.URL_MONCLOA, "https://www.lamoncloa.gob.es/otra")
        res = n.validar(self.caso)
        self.assertIn("url_no_abierta", self.codigos(res))
        self.assertIn("fuente_sin_evidencia", self.codigos(res))

    def test_referencia_y_evidencia_inexistentes(self):
        self.reescribir("informe.md", "es otra cosa [3].", "es otra cosa [3][4]. <!-- E-A9-01 -->")
        self.assertTrue({"referencia_inexistente", "evidencia_inexistente"} <= self.codigos(n.validar(self.caso)))

    def test_calificacion_incoherente_y_confianza(self):
        self.reescribir("publicacion.md", "*❌ FALSO*", "*✅ VERDADERO*")
        self.reescribir("informe.md", "**Confianza:** ALTA", "**Confianza:** BAJA")
        errores = self.codigos(n.validar(self.caso))
        self.assertIn("calificacion_incoherente", errores)
        self.assertIn("confianza_no_permitida", errores)

    def test_prosa_en_minusculas_no_es_calificacion(self):
        self.reescribir("publicacion.md", "*❌ FALSO*: no existe esa paga.", "*❌ FALSO*: lo verdadero es otra cosa.")
        self.assertNotIn("calificacion_incoherente", self.codigos(n.validar(self.caso)))

    def test_limite_de_x_y_plantilla(self):
        self.reescribir("publicacion.md", "#Bulo", "#Bulo " + "palabra " * 40)
        self.reescribir("informe.md", "No procede.", "{{Si afecta a declaraciones…}}")
        errores = self.codigos(n.validar(self.caso))
        self.assertIn("excede_limite", errores)
        self.assertIn("plantilla_sin_rellenar", errores)

    def test_campos_e_identificadores(self):
        self.reescribir("evidencias/verificador-A1.md", "### E-A1-02", "### E-A1-01")
        self.reescribir("evidencias/verificador-A1.md", "- **Tipo:** primaria-oficial\n- **Fecha del documento:** 2026",
                        "- **Tipo:** blog\n- **Fecha del documento:** 2026")
        errores = self.codigos(n.validar(self.caso))
        self.assertIn("id_duplicado", errores)
        self.assertIn("tipo_desconocido", errores)

    def test_enlace_al_original(self):
        self.reescribir("informe.md", "- **Formato y plataforma:** publicación en X [1].",
                        f"- **Formato y plataforma:** publicación en X [1]: {ej.URL_ORIGINAL}")
        self.assertIn("enlace_al_original", self.codigos(n.validar(self.caso), "avisos"))

    def test_resultado(self):
        res = n.escribir_resultado(self.caso, calificacion="FALSO", subtipo="inventado", confianza="ALTA",
                                   dictamen="PALANTE", rondas=1)
        self.assertEqual(n.comprobar_resultado(res), [])
        self.assertEqual(res["afirmacion_central"], "A1")
        self.assertEqual(res["afirmaciones"][0]["calificacion"], "FALSO")
        self.assertEqual(res["afirmaciones"][0]["evidencias"], ["E-A1-01", "E-A1-02"])
        self.assertEqual([f["n"] for f in res["fuentes"]], [1, 2, 3])
        self.assertEqual(res["fuentes"][0]["evidencias"], ["E-C-01"])
        self.assertEqual(res["fuentes"][1]["tipo"], "primaria-oficial")
        self.assertEqual(len(res["publicaciones"]["hilo_x"]), 4)
        self.assertEqual(res["entrada"]["copia_archivada"], ej.URL_COPIA)
        self.assertTrue(res["auditoria"]["aprobado"])
        self.assertTrue(n.validar(self.caso)["ok"])

    def test_resultado_incoherente(self):
        n.escribir_resultado(self.caso, calificacion="ALERTA", confianza="MEDIA", dictamen="PALANTE", rondas=1)
        self.assertIn("calificacion_incoherente", self.codigos(n.validar(self.caso)))
        res = n.construir_resultado(self.caso, calificacion="FALSO", confianza="BAJA", dictamen="OK", rondas=5,
                                    subtipo="sin-tipo")
        problemas = " ".join(n.comprobar_resultado(res))
        for texto in ("confianza BAJA", "subtipo", "dictamen", "rondas"):
            self.assertIn(texto, problemas)


class TestCLI(unittest.TestCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, json.loads(buf.getvalue())

    def test_validar_y_resultado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = ej.crear_caso_ejemplo(tmp)
            code, res = self.run_cli("validar", str(caso))
            self.assertEqual((code, res["ok"]), (0, True))
            code, res = self.run_cli("resultado", str(caso), "--calificacion", "FALSO", "--subtipo", "inventado",
                                     "--confianza", "ALTA", "--dictamen", "PALANTE", "--rondas", "1")
            self.assertEqual((code, res["problemas"]), (0, []))
            (caso / "informe.md").write_text("# Sin calificación\n", encoding="utf-8")
            code, res = self.run_cli("validar", str(caso))
            self.assertEqual(code, 1)

    def test_errores_en_json(self):
        code, res = self.run_cli("buscar", "x", "--buscador", "brave")
        self.assertEqual(code, 1)
        self.assertIn("BRAVE_API_KEY", res["error"])


class TestLanzador(unittest.TestCase):
    def test_desde_el_repositorio(self):
        r = subprocess.run([sys.executable, str(ROOT / "skills/bulonator/scripts/bulonator.py"), "--version"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout.strip(), r"^\d+\.\d+\.\d+$")

    def test_copia_instalada_con_vendor(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp, "skills", "bulonator")
            shutil.copytree(ROOT / "skills" / "bulonator", skill, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "src" / "bulonator", skill / "scripts" / "_vendor" / "bulonator",
                            ignore=shutil.ignore_patterns("__pycache__"))
            entorno = {k: v for k, v in os.environ.items() if not k.startswith("BULONATOR_")}
            r = subprocess.run([sys.executable, "-I", str(skill / "scripts" / "bulonator.py"), "contar"],
                               input="hola", capture_output=True, text=True, timeout=60, env=entorno, cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["bloques"][0]["x_ponderado"], 4)


class TestMetodologia(unittest.TestCase):
    def test_rutas_del_repositorio(self):
        m = n.metodologia()
        self.assertTrue((m.referencias / "reglas.json").is_file())
        self.assertTrue(m.agente("bulonator-auditor").is_file())

    def test_longitudes(self):
        self.assertEqual(n.longitud("hola https://boe.es/x", "mastodon"), 5 + 23)
        self.assertEqual(n.longitud("hola 😀", "x"), 7)
        self.assertEqual(n.longitud("hola 😀", "bluesky"), 6)


if __name__ == "__main__":
    unittest.main()
