"""Pruebas de la metodología: una sola definición por regla, agentes neutros y coherencia con reglas.json.

Ejecuta: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bulonator.nucleo import datos  # noqa: E402

REFS = ROOT / "skills" / "bulonator" / "references"
AGENTES = sorted(p.stem for p in (ROOT / "agents").glob("bulonator-*.md"))
PREFIJOS = {"MET": "metodologia.md", "CAL": "calificaciones.md", "EV": "formato-evidencias.md",
            "RED": "redaccion.md", "PROP": "analisis-propagacion.md", "MM": "tecnicas-multimedia.md",
            "FUE": "fuentes-oficiales.md", "VER": "verificadores.md", "FLU": "flujo.md"}
ID_RE = re.compile(r"\[(%s)-(\d+)\]" % "|".join(PREFIJOS))
DEF_RE = re.compile(r"\*\*\[(%s)-(\d+)\]\*\*" % "|".join(PREFIJOS))
PROHIBIDOS = ("python3 SCRIPT", "SCRIPT ", "WebSearch", "WebFetch", "Bash", "`Read`", "`Write`", "`Edit`",
              "`Glob`", "`Grep`", "`Agent`", "curl", "${CLAUDE", "allowed_domains", "REFS/")
CAPACIDADES = {"buscar", "leer", "boe", "boe_sumario", "ine_operaciones", "ine_tablas", "ine_datos", "wayback",
               "dominio", "factcheck", "buscar_imagen", "media", "ver_imagen", "navegador"}


def archivos_markdown():
    yield from sorted(REFS.glob("*.md"))
    yield from sorted((ROOT / "agents").glob("*.md"))
    yield from sorted((ROOT / "skills").glob("*/SKILL.md"))
    yield from sorted((ROOT / "skills" / "bulonator" / "templates").glob("*.md"))


class TestIdentificadoresDeReglas(unittest.TestCase):
    def test_cada_regla_se_define_una_vez_en_su_archivo(self):
        definiciones = defaultdict(list)
        for p in archivos_markdown():
            for pref, num in DEF_RE.findall(p.read_text(encoding="utf-8")):
                definiciones[f"{pref}-{num}"].append(p.name)
        self.assertGreater(len(definiciones), 50)
        for rid, donde in definiciones.items():
            with self.subTest(regla=rid):
                self.assertEqual(donde, [PREFIJOS[rid.split("-")[0]]], f"{rid} definida en {donde}")

    def test_las_referencias_existen(self):
        definidas = set()
        for p in archivos_markdown():
            definidas |= {f"{a}-{b}" for a, b in DEF_RE.findall(p.read_text(encoding="utf-8"))}
        for p in archivos_markdown():
            for pref, num in ID_RE.findall(p.read_text(encoding="utf-8")):
                with self.subTest(archivo=p.name, regla=f"{pref}-{num}"):
                    self.assertIn(f"{pref}-{num}", definidas)

    def test_numeracion_sin_huecos(self):
        for pref, archivo in PREFIJOS.items():
            nums = sorted(int(n) for a, n in DEF_RE.findall((REFS / archivo).read_text(encoding="utf-8")) if a == pref)
            with self.subTest(archivo=archivo):
                self.assertEqual(nums, list(range(1, len(nums) + 1)))


class TestAgentesNeutros(unittest.TestCase):
    def test_secciones_compartidas_sin_herramientas_de_claude(self):
        for agente in AGENTES:
            texto = datos.texto_compartido_de_agente(agente)
            for token in PROHIBIDOS:
                with self.subTest(agente=agente, token=token):
                    self.assertNotIn(token, texto)

    def test_secciones_de_claude_presentes(self):
        for agente in AGENTES:
            _, partes = datos.partes_de_agente(agente)
            titulos = [t for t, _ in partes]
            with self.subTest(agente=agente):
                self.assertTrue(any(t.startswith("Lo que recibes") for t in titulos))
                self.assertIn("Salida", titulos)
                self.assertIn("Referencias", titulos)

    def test_referencias_existen(self):
        for agente in AGENTES:
            refs = datos.referencias_de_agente(agente)
            with self.subTest(agente=agente):
                self.assertIn("formato-evidencias.md", refs + (["formato-evidencias.md"] if agente == "bulonator-captura" else []))
                for r in refs:
                    self.assertTrue((REFS / r).is_file(), f"{agente}: no existe {r}")

    def test_capacidades_documentadas_para_claude(self):
        hoja = (REFS / "herramientas-claude.md").read_text(encoding="utf-8")
        for cap in CAPACIDADES:
            with self.subTest(capacidad=cap):
                self.assertIn(f"`{cap}`", hoja)


class TestFlujo(unittest.TestCase):
    def test_secciones_que_usa_el_motor(self):
        for titulo in ("Fases", "Modos", "Desglose", "Deliberación y redacción", "Auditoría y cierre"):
            with self.subTest(seccion=titulo):
                self.assertTrue(datos.seccion_de_referencia("flujo.md", titulo).strip())


class TestReglasJson(unittest.TestCase):
    def setUp(self):
        self.reglas = json.loads((REFS / "reglas.json").read_text(encoding="utf-8"))

    def test_etiquetas_coinciden_con_calificaciones_md(self):
        texto = (REFS / "calificaciones.md").read_text(encoding="utf-8")
        for nombre, conf in self.reglas["calificaciones"].items():
            with self.subTest(calificacion=nombre):
                self.assertIn(conf["etiqueta"], texto)
                self.assertTrue(set(conf["confianzas"]) <= set(self.reglas["confianzas"]))
        for subtipo in self.reglas["calificaciones"]["FALSO"]["subtipos"]:
            self.assertIn(f"`{subtipo}`", texto)

    def test_tipos_de_fuente_documentados(self):
        texto = (REFS / "formato-evidencias.md").read_text(encoding="utf-8")
        for tipo in self.reglas["tipos_fuente"]:
            with self.subTest(tipo=tipo):
                self.assertIn(f"`{tipo}`", texto)

    def test_publicaciones_coinciden_con_la_plantilla(self):
        plantilla = (ROOT / "skills" / "bulonator" / "templates" / "publicacion.md").read_text(encoding="utf-8")
        titulos = [re.sub(r"^\d+\.\s*", "", t).lower() for t in re.findall(r"^## (.+)$", plantilla, re.M)]
        for clave, conf in self.reglas["publicaciones"].items():
            with self.subTest(publicacion=clave):
                self.assertTrue(any(t.startswith(conf["titulo"].lower()) for t in titulos))


class TestSinRepeticiones(unittest.TestCase):
    """La metodología no repite pasajes: cada regla vive en un solo sitio y el resto la cita por su ID."""

    N = 12  # palabras seguidas idénticas a partir de las que se considera una copia

    def corpus(self):
        textos = {p.name: p.read_text(encoding="utf-8") for p in sorted(REFS.glob("*.md"))}
        for agente in AGENTES:
            textos[agente] = datos.texto_compartido_de_agente(agente)
        return textos

    def test_sin_pasajes_copiados(self):
        def palabras(t):
            return re.findall(r"[\wáéíóúñü]+", re.sub(r"\[[A-Z]+-\d+\]", " ", t.lower()))

        vistos = {}
        copias = []
        for nombre, texto in self.corpus().items():
            w = palabras(texto)
            propios = set()
            for i in range(len(w) - self.N + 1):
                g = tuple(w[i:i + self.N])
                if g in propios:
                    continue
                propios.add(g)
                if g in vistos and vistos[g] != nombre:
                    copias.append((vistos[g], nombre, " ".join(g)))
                vistos.setdefault(g, nombre)
        self.assertEqual(copias[:5], [], f"{len(copias)} pasajes de {self.N} palabras repetidos entre archivos")


if __name__ == "__main__":
    unittest.main()
