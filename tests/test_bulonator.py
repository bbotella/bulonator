"""Pruebas unitarias de skills/bulonator/scripts/bulonator.py (sin red).

Ejecuta: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "bulonator" / "scripts" / "bulonator.py"
spec = importlib.util.spec_from_file_location("bulonator", SCRIPT)
bt = importlib.util.module_from_spec(spec)
sys.modules["bulonator"] = bt
spec.loader.exec_module(bt)


def run_cli(*argv) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = bt.main(list(argv))
    assert code == 0, f"código de salida {code}: {buf.getvalue()}"
    return json.loads(buf.getvalue())


# --- Construcción de imágenes de prueba -------------------------------------

def tiff_exif(entries_ifd0, entries_exif=None, entries_gps=None) -> bytes:
    """TIFF little-endian mínimo con IFD0, ExifIFD y GPSIFD (solo ASCII y RATIONAL)."""
    def ifd_bytes(entries, base):
        # entries: list of (tag, type, values)
        n = len(entries)
        head = struct.pack("<H", n)
        data_off = base + 2 + n * 12 + 4
        body, extra = b"", b""
        for tag, typ, val in entries:
            if typ == 2:
                raw = val.encode() + b"\0"
                cnt = len(raw)
            elif typ == 5:
                raw = b"".join(struct.pack("<II", int(v * 1000), 1000) for v in val)
                cnt = len(val)
            elif typ == 4:
                raw = struct.pack("<I", val)
                cnt = 1
            if len(raw) <= 4:
                body += struct.pack("<HHI", tag, typ, cnt) + raw.ljust(4, b"\0")
            else:
                body += struct.pack("<HHI", tag, typ, cnt) + struct.pack("<I", data_off + len(extra))
                extra += raw
        return head + body + struct.pack("<I", 0) + extra

    header = b"II*\0" + struct.pack("<I", 8)
    exif_entries = entries_exif or []
    gps_entries = entries_gps or []
    # Calculamos en dos pasadas: primero IFD0 sin punteros para conocer su tamaño
    ptrs = []
    if exif_entries:
        ptrs.append((0x8769, 4, 0))
    if gps_entries:
        ptrs.append((0x8825, 4, 0))
    ifd0 = ifd_bytes(entries_ifd0 + ptrs, 8)
    off = 8 + len(ifd0)
    exif_blk = ifd_bytes(exif_entries, off) if exif_entries else b""
    gps_off = off + len(exif_blk)
    gps_blk = ifd_bytes(gps_entries, gps_off) if gps_entries else b""
    real_ptrs = []
    if exif_entries:
        real_ptrs.append((0x8769, 4, off))
    if gps_entries:
        real_ptrs.append((0x8825, 4, gps_off))
    ifd0 = ifd_bytes(entries_ifd0 + real_ptrs, 8)
    return header + ifd0 + exif_blk + gps_blk


def jpeg_with(exif: bytes | None = None, xmp: str | None = None, pixel_noise: bytes = b"") -> bytes:
    out = b"\xff\xd8"
    if exif:
        seg = b"Exif\0\0" + exif
        out += b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    if xmp:
        seg = b"http://ns.adobe.com/xap/1.0/\0" + xmp.encode()
        out += b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    out += b"\xff\xda" + struct.pack(">H", 8) + b"\0" * 6 + pixel_noise + b"\xff\xd9"
    return out


def png_with_text(key: str, value: str) -> bytes:
    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\0\0\0\0")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", key.encode() + b"\0" + value.encode())
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


# --- Pruebas ------------------------------------------------------------------

class TestUtilidades(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(bt.slugify("https://www.Ejemplo.es/Noticia-Ñandú?x=1"), "www-ejemplo-es-noticia-nandu-x-1")
        self.assertEqual(bt.slugify("¿¿??"), "caso")
        self.assertLessEqual(len(bt.slugify("a" * 200)), 50)

    def test_registered_domain(self):
        self.assertEqual(bt.registered_domain("www.elpais.com"), "elpais.com")
        self.assertEqual(bt.registered_domain("sede.agenciatributaria.gob.es"), "agenciatributaria.gob.es")
        self.assertEqual(bt.registered_domain("news.bbc.co.uk"), "bbc.co.uk")

    def test_safe_url_codifica_tildes(self):
        url = bt.safe_url("https://ejemplo.es/año/canción ñ.jpg?q=café")
        self.assertTrue(url.isascii())
        self.assertIn("%C3%B1", url)

    def test_guess_ext(self):
        self.assertEqual(bt.guess_ext("https://x/a.jpg"), ".jpg")
        self.assertEqual(bt.guess_ext("https://pbs.twimg.com/media/abc?format=png&name=orig"), ".png")
        self.assertEqual(bt.guess_ext("https://x/a", "image/webp; q=1"), ".webp")

    def test_detect_platform(self):
        casos = {
            "https://x.com/usuario/status/123": "x",
            "https://twitter.com/i/web/status/123": "x",
            "https://bsky.app/profile/a.bsky.social/post/3abc": "bluesky",
            "https://t.me/canal/45": "telegram",
            "https://www.youtube.com/watch?v=abc": "youtube",
            "https://youtu.be/abc": "youtube",
            "https://www.tiktok.com/@a/video/1": "tiktok",
            "https://www.instagram.com/p/abc/": "instagram",
            "https://www.reddit.com/r/spain/comments/abc/titulo/": "reddit",
            "https://mastodon.social/@usuario/112233": "mastodon",
            "https://vimeo.com/123": "video",
            "https://www.elpais.com/espana/noticia.html": "web",
            "https://x.com/usuario": "web",
        }
        for url, esperado in casos.items():
            with self.subTest(url=url):
                self.assertEqual(bt.detect_platform(url), esperado)

    def test_tweet_id_y_token(self):
        self.assertEqual(bt.tweet_id("https://x.com/a/status/1234567890?s=20"), "1234567890")
        tok = bt.syndication_token("1234567890123456789")
        self.assertTrue(tok and tok.isalnum())

    def test_orig_photo(self):
        self.assertIn("name=orig", bt._orig_photo("https://pbs.twimg.com/media/ABC.jpg?format=jpg&name=small"))

    def test_x_weight(self):
        self.assertEqual(bt.x_weight("hola"), 4)
        self.assertEqual(bt.x_weight("ver https://www.boe.es/buscar/act.php?id=BOE-A-2024-1"), 4 + 23)
        self.assertEqual(bt.x_weight("❌"), 2)
        self.assertEqual(bt.x_weight("👍🏽"), 2)  # emoji + tono de piel = 2
        self.assertEqual(bt.x_weight("€"), 2)


class TestMetadatos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_exif_basico_y_gps(self):
        exif = tiff_exif(
            [(0x010F, 2, "Canon"), (0x0110, 2, "EOS 5D"), (0x0131, 2, "Adobe Photoshop 25.0")],
            [(0x9003, 2, "2019:05:04 10:11:12")],
            [(1, 2, "N"), (2, 5, [40, 25, 0]), (3, 2, "W"), (4, 5, [3, 42, 0])],
        )
        parsed = bt.parse_tiff_exif(exif)
        self.assertEqual(parsed["Make"], "Canon")
        self.assertEqual(parsed["DateTimeOriginal"], "2019:05:04 10:11:12")
        self.assertAlmostEqual(parsed["GPS"]["lat"], 40.416667, places=4)
        self.assertAlmostEqual(parsed["GPS"]["lon"], -3.7, places=4)

    def test_exif_corrupto_no_rompe(self):
        self.assertEqual(bt.parse_tiff_exif(b"II*\0\xff\xff\xff\xff"), {})
        self.assertEqual(bt.parse_tiff_exif(b"basura"), {})

    def test_jpeg_xmp_ia(self):
        xmp = ('<x:xmpmeta><rdf:Description xmp:CreatorTool="Adobe Firefly" '
               'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/>'
               '</x:xmpmeta>')
        p = self.dir / "ia.jpg"
        p.write_bytes(jpeg_with(xmp=xmp))
        meta = bt.read_image_metadata(p)
        self.assertIn("xmp:CreatorTool", meta["xmp"])
        self.assertIn("Adobe Firefly", meta["indicios_ia_en_metadatos"])
        self.assertTrue(any("trainedAlgorithmicMedia" in x for x in meta["indicios_ia_en_metadatos"]))

    def test_sin_falsos_positivos_en_pixeles(self):
        p = self.dir / "ruido.jpg"
        p.write_bytes(jpeg_with(exif=tiff_exif([(0x010F, 2, "Apple")]), pixel_noise=b" grok sora midjourney "))
        meta = bt.read_image_metadata(p)
        self.assertNotIn("indicios_ia_en_metadatos", meta)
        self.assertEqual(meta["exif"]["Make"], "Apple")

    def test_png_parametros_stable_diffusion(self):
        p = self.dir / "sd.png"
        p.write_bytes(png_with_text("parameters", "a cat, Steps: 20, Model: stable-diffusion-xl"))
        meta = bt.read_image_metadata(p)
        self.assertIn("parameters", meta["png_texto"])
        self.assertIn("Stable Diffusion", meta["indicios_ia_en_metadatos"])

    def test_sniff_kind(self):
        p = self.dir / "a.bin"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 60)
        self.assertEqual(bt.sniff_kind(p), "imagen")
        p.write_bytes(b"%PDF-1.7" + b"\0" * 60)
        self.assertEqual(bt.sniff_kind(p), "documento")
        p.write_bytes(b"\0\0\0\x18ftypisom" + b"\0" * 60)
        self.assertEqual(bt.sniff_kind(p), "audiovisual")


class TestExtraccionHTML(unittest.TestCase):
    HTML = """<!doctype html><html lang="es"><head>
    <title>Titular · Medio</title>
    <meta property="og:title" content="Titular de prueba">
    <meta property="og:image" content="/img/portada.jpg">
    <meta property="og:site_name" content="El Medio">
    <meta property="article:published_time" content="2026-10-01T09:00:00+02:00">
    <link rel="canonical" href="https://medio.es/noticia">
    <script type="application/ld+json">{"@context":"https://schema.org","@type":"NewsArticle",
      "headline":"Titular de prueba","author":[{"@type":"Person","name":"Ana Pérez"}],
      "datePublished":"2026-10-01T09:00:00+02:00","publisher":{"@type":"Organization","name":"El Medio"}}</script>
    <script>var basura = "<p>no es texto</p>";</script>
    </head><body>
    <header><nav><a href="/portada">Portada</a> Menú de la web</nav></header>
    <article>
      <header><h1>Titular de prueba</h1><p class="entradilla">Entradilla importante del artículo.</p></header>
      <p>Primer párrafo con un <a href="https://www.ine.es/tabla">dato del INE</a> y bastante texto para que el
      extractor considere que el artículo tiene cuerpo suficiente. Lorem ipsum dolor sit amet, consectetur
      adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
      <p>Segundo párrafo. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
      commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore.</p>
      <img src="/fotos/escena.jpg" alt="Escena">
      <img src="/static/logo.png" alt="logo">
      <blockquote class="twitter-tweet"><p>texto del tuit</p>
        <a href="https://twitter.com/usuario/status/1789">1 de octubre</a></blockquote>
      <iframe src="https://www.youtube.com/embed/abc123"></iframe>
    </article>
    <footer>Aviso legal © El Medio</footer>
    </body></html>"""

    def test_extract_page(self):
        info = bt.extract_page("https://medio.es/noticia", self.HTML)
        self.assertEqual(info["titulo"], "Titular de prueba")
        self.assertEqual(info["medio"], "El Medio")
        self.assertEqual(info["autor"], ["Ana Pérez"])
        self.assertEqual(info["fecha_publicacion"], "2026-10-01T09:00:00+02:00")
        self.assertEqual(info["idioma"], "es")
        self.assertIn("Entradilla importante", info["texto"])  # la cabecera del artículo se conserva
        self.assertNotIn("Menú de la web", info["texto"])      # la navegación de la web no
        self.assertNotIn("Aviso legal", info["texto"])
        self.assertNotIn("no es texto", info["texto"])
        urls = [i["url"] for i in info["imagenes"]]
        self.assertEqual(urls[0], "https://medio.es/img/portada.jpg")
        self.assertIn("https://medio.es/fotos/escena.jpg", urls)
        self.assertFalse(any("logo" in u for u in urls))
        tipos = {(e["tipo"], e["url"]) for e in info["incrustados"]}
        self.assertIn(("tuit", "https://twitter.com/usuario/status/1789"), tipos)
        self.assertIn(("iframe", "https://www.youtube.com/embed/abc123"), tipos)
        self.assertIn("https://www.ine.es/tabla", [e["url"] for e in info["enlaces_salientes"]])

    def test_html_roto_no_rompe(self):
        info = bt.extract_page("https://a.es", "<html><p>texto <b>sin cerrar<article><p>más</p></html>")
        self.assertIsInstance(info["texto"], str)
        self.assertIn("más", info["texto"])


class TestCLI(unittest.TestCase):
    def test_caso_y_captura_de_texto(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = run_cli("caso", "Dicen que el BOE publica una paga", "--base", tmp)["caso"]
            self.assertTrue(Path(caso, "media").is_dir())
            out = run_cli("capturar", "Dicen que el BOE publica una paga", "--dir", caso)
            self.assertEqual(out["plataforma"], "texto")
            saved = json.loads(Path(caso, "captura.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["texto"], "Dicen que el BOE publica una paga")

    def test_captura_de_archivo_local_y_nombre_secundario(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp, "foto.png")
            img.write_bytes(png_with_text("Software", "test"))
            caso = run_cli("caso", "foto", "--base", tmp)["caso"]
            out = run_cli("capturar", str(img), "--dir", caso, "--nombre", "secundaria")
            self.assertEqual(out["plataforma"], "archivo_local")
            self.assertTrue(Path(caso, "secundaria.json").exists())
            self.assertFalse(Path(caso, "captura.json").exists())
            self.assertTrue(Path(caso, "media", "foto.png").exists())

    def test_contar_bloques(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp, "pub.md")
            f.write_text("# T\n\n```text\nhola https://boe.es/x\n```\n\nprosa\n\n```text\n" + "a" * 281 + "\n```\n",
                         encoding="utf-8")
            out = run_cli("contar", "--bloques", str(f))
            self.assertEqual(out["bloques"][0]["x_ponderado"], 5 + 23)
            self.assertIn("x", out["bloques"][0]["cabe_en"])
            self.assertNotIn("x", out["bloques"][1]["cabe_en"])

    def test_buscar_imagen_sin_clave(self):
        out = run_cli("buscar-imagen", "https://ejemplo.es/a.jpg")
        self.assertIn("tineye", out["enlaces_manual"])
        self.assertIn("https%3A%2F%2Fejemplo.es%2Fa.jpg", out["enlaces_manual"]["google_lens"])


if __name__ == "__main__":
    unittest.main()
