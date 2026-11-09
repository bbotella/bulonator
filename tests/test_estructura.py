"""Pruebas de estructura del plugin: manifiestos, frontmatter y referencias cruzadas.

Ejecuta: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
AGENTS = sorted((ROOT / "agents").glob("*.md"))
REFS = ROOT / "skills" / "bulonator" / "references"
TEMPLATES = ROOT / "skills" / "bulonator" / "templates"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path}: falta el frontmatter YAML"
    data = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        assert sep, f"{path}: línea de frontmatter no válida: {line!r}"
        value = value.strip()
        # Un valor sin comillas no puede contener ': ' ni empezar por comillas sin cerrarlas (YAML)
        if value and value[0] not in "'\"[":
            assert ": " not in value, f"{path}: '{key}' contiene ': ' sin comillas"
        if value[:1] in "'\"":
            assert value[-1] == value[0], f"{path}: '{key}' abre comillas y no las cierra al final"
        data[key.strip()] = value.strip("'\"")
    return data


class TestManifiestos(unittest.TestCase):
    def test_plugin_y_marketplace(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], "bulonator")
        entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(entry["version"], plugin["version"], "la versión del marketplace no coincide con plugin.json")
        self.assertEqual(entry["source"], "./")

    def test_versiones_a_la_par(self):
        """El plugin, bulonator-nucleo y bulonator (el motor) llevan la misma versión, y el motor exige
        exactamente ese núcleo."""
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        nucleo = (ROOT / "src" / "bulonator" / "__init__.py").read_text(encoding="utf-8")
        motor = (ROOT / "motor" / "src" / "bulonator" / "motor" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{version}"', nucleo)
        self.assertIn(f'__version__ = "{version}"', motor)
        self.assertIn(f'"bulonator-nucleo=={version}"', (ROOT / "motor" / "pyproject.toml").read_text(encoding="utf-8"))

    def test_dos_paquetes(self):
        raiz = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        motor = (ROOT / "motor" / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "bulonator-nucleo"', raiz)
        self.assertIn("dependencies = []", raiz)
        self.assertIn('name = "bulonator"', motor)
        self.assertIn('requires-python = ">=3.11"', motor)
        # El espacio de nombres compartido: el núcleo aporta bulonator/__init__.py y el motor solo su subpaquete
        self.assertFalse((ROOT / "motor" / "src" / "bulonator" / "__init__.py").exists())
        self.assertFalse((ROOT / "src" / "bulonator" / "motor").exists())
        self.assertEqual((ROOT / "LICENSE").read_text(encoding="utf-8"), (ROOT / "motor" / "LICENSE").read_text(encoding="utf-8"))


class TestSkills(unittest.TestCase):
    def test_hay_skills(self):
        self.assertEqual({p.parent.name for p in SKILLS}, {"bulonator", "verificar-dato", "verificar-multimedia"})

    def test_frontmatter(self):
        for path in SKILLS:
            with self.subTest(skill=path.parent.name):
                fm = frontmatter(path)
                self.assertEqual(fm.get("name"), path.parent.name)
                self.assertGreater(len(fm.get("description", "")), 80)
                self.assertIn("argument-hint", fm)
                self.assertLessEqual(len(fm["description"]), 1024)

    def test_rutas_referenciadas_existen(self):
        for path in SKILLS + AGENTS:
            text = path.read_text(encoding="utf-8")
            for ref in set(re.findall(r"REFS/([\w-]+\.md)", text)) | set(re.findall(r"`([\w-]+\.md)`", text)):
                if ref in {"SKILL.md", "README.md", "CONTRIBUTING.md"} or ref.startswith(("bulonator-", "verificador-",
                                                                                           "multimedia-", "01-", "02-",
                                                                                           "03-")):
                    continue
                with self.subTest(archivo=path.name, ref=ref):
                    self.assertTrue((REFS / ref).exists() or (TEMPLATES / ref).exists(),
                                    f"{path} menciona {ref}, que no existe en references/ ni templates/")
            for tpl in re.findall(r"templates/([\w-]+\.md)", text):
                with self.subTest(archivo=path.name, plantilla=tpl):
                    self.assertTrue((TEMPLATES / tpl).exists())

    def test_agentes_mencionados_existen(self):
        names = {p.stem for p in AGENTS}
        for path in SKILLS:
            for agent in set(re.findall(r"\bbulonator-(?:captura|verificador|multimedia|origen|auditor)\b",
                                        path.read_text(encoding="utf-8"))):
                with self.subTest(skill=path.parent.name, agente=agent):
                    self.assertIn(agent, names)


class TestAgentes(unittest.TestCase):
    def test_frontmatter(self):
        self.assertEqual(len(AGENTS), 5)
        for path in AGENTS:
            with self.subTest(agente=path.stem):
                fm = frontmatter(path)
                self.assertEqual(fm.get("name"), path.stem)
                self.assertTrue(re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}[a-z0-9]", fm["name"]))
                self.assertGreater(len(fm.get("description", "")), 80)
                self.assertIn(fm.get("model"), {"inherit", "sonnet", "opus", "haiku", "fable"})

    def test_principios_de_seguridad(self):
        # Todos los agentes deben tratar el contenido como datos (defensa frente a inyección de instrucciones)
        for path in AGENTS:
            with self.subTest(agente=path.stem):
                self.assertIn("## Seguridad", path.read_text(encoding="utf-8"))


def valores_yaml_sin_comillas(texto: str) -> list:
    """Líneas ``clave: valor`` cuyo valor sin comillas contiene ': ' (YAML lo rechaza o lo malinterpreta).

    Ignora el contenido de los bloques literales (``run: |``) y los comentarios finales.
    """
    problemas, bloque = [], None
    for n, linea in enumerate(texto.splitlines(), 1):
        sangria = len(linea) - len(linea.lstrip())
        if bloque is not None:
            if not linea.strip() or sangria > bloque:
                continue
            bloque = None
        m = re.match(r"^\s*(?:-\s+)?[\w.-]+:\s+(.*)$", linea)
        if not m:
            continue
        valor = re.sub(r"\s+#.*$", "", m.group(1)).strip()
        if valor[:1] in ("|", ">"):
            bloque = sangria
        elif valor and valor[0] not in "'\"[{&*!" and ": " in valor:
            problemas.append(f"línea {n}: {linea.strip()}")
    return problemas


class TestYamlDeGitHub(unittest.TestCase):
    def test_valores_con_dos_puntos_entre_comillas(self):
        archivos = sorted((ROOT / ".github").rglob("*.yml"))
        self.assertTrue(archivos)
        for path in archivos:
            with self.subTest(archivo=path.relative_to(ROOT).as_posix()):
                self.assertEqual(valores_yaml_sin_comillas(path.read_text(encoding="utf-8")), [])

    def test_el_comprobador_detecta_el_error(self):
        malo = "steps:\n  - name: Comprobar (falla: 404)\n  - run: |\n      echo a: b\n  - name: \"bien: así\"\n"
        self.assertEqual(valores_yaml_sin_comillas(malo), ["línea 2: - name: Comprobar (falla: 404)"])


class TestInstalador(unittest.TestCase):
    def test_listas_del_instalador(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        for path in SKILLS:
            self.assertIn(path.parent.name, text)
        for path in AGENTS:
            self.assertIn(path.stem, text)


if __name__ == "__main__":
    unittest.main()
