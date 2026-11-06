#!/usr/bin/env python3
"""Bulonator: herramientas de captura, preservación y análisis multimedia para verificar bulos.

Solo usa la biblioteca estándar de Python (3.9 o superior). Las funciones multimedia usan
ffmpeg/ffprobe y yt-dlp cuando están instalados; si faltan, el script lo indica en "avisos".

Todos los subcomandos imprimen JSON por la salida estándar. Ejecuta
`python3 bulonator.py -h` o `python3 bulonator.py <subcomando> -h` para ver la ayuda.

Subcomandos:
  deps            Comprueba qué herramientas externas hay disponibles.
  caso            Crea la carpeta de un caso nuevo y devuelve su ruta.
  capturar        Captura una URL (X/Twitter, Bluesky, Telegram, Mastodon, Reddit, YouTube,
                  TikTok, Instagram, Facebook, webs de noticias...), descarga su multimedia y
                  consulta copias en archivos web.
  media           Analiza una imagen, vídeo o audio: metadatos, marcas de IA/C2PA, ELA,
                  fotogramas clave, hoja de contactos, audio y transcripción.
  wayback         Consulta (y opcionalmente solicita) copias en la Wayback Machine.
  dominio         Datos de registro de un dominio (RDAP o whois).
  boe             Busca legislación consolidada en el BOE o lista el sumario de un día.
  ine             Busca operaciones estadísticas, tablas y datos del INE.
  buscar-imagen   Enlaces de búsqueda inversa de una imagen (y resultados con SerpAPI si hay clave).
  factcheck       Busca verificaciones previas (Google Fact Check Tools si hay clave).
  contar          Longitud de los textos para redes (reglas de X: enlaces = 23, emojis = 2).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import html
import http.client
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from pathlib import Path

VERSION = "1.0.0"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 Bulonator/" + VERSION
)
TIMEOUT = 30
MAX_PAGE_BYTES = 20 * 1024 * 1024
MAX_MEDIA_BYTES = 500 * 1024 * 1024


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------


class HttpError(Exception):
    """Fallo de red o respuesta HTTP no satisfactoria."""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def emit(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Ejecuta un comando sin shell y devuelve (código, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: no encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: tiempo agotado ({timeout} s)"


def tail(text: str, n: int = 600) -> str:
    text = (text or "").strip()
    return text[-n:]


def slugify(text: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"^https?://", "", text.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:max_len].strip("-")) or "caso"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_url(url: str) -> str:
    """Convierte una IRI (con tildes, espacios, eñes...) en una URL ASCII válida."""
    parts = urllib.parse.urlsplit(url.strip())
    try:
        host = (parts.hostname or "").encode("idna").decode("ascii")
    except UnicodeError:
        host = parts.hostname or ""
    netloc = host + (f":{parts.port}" if parts.port else "")
    if parts.username:
        netloc = f"{parts.username}@{netloc}"
    keep = "/%:@!$&'()*+,;=-._~"
    return urllib.parse.urlunsplit((parts.scheme, netloc, urllib.parse.quote(parts.path, safe=keep),
                                    urllib.parse.quote(parts.query, safe=keep + "?"), ""))


def _open(url: str, headers: dict | None, timeout: int):
    try:
        url = safe_url(url)
    except ValueError as e:
        raise HttpError(f"URL no válida: {url} ({e})") from e
    hdrs = {
        "User-Agent": UA,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise HttpError(f"HTTP {e.code} al pedir {url}") from e
    except urllib.error.URLError as e:
        hint = ""
        if "CERTIFICATE" in str(e.reason).upper():
            hint = " (instala los certificados raíz de Python, p. ej. 'Install Certificates.command')"
        raise HttpError(f"no se pudo conectar con {url}: {e.reason}{hint}") from e
    except (TimeoutError, OSError, ValueError, UnicodeError) as e:
        raise HttpError(f"error de red con {url}: {e}") from e


def http_get(url: str, headers: dict | None = None, timeout: int = TIMEOUT,
             max_bytes: int = MAX_PAGE_BYTES) -> tuple[int, str, dict, bytes]:
    """GET con descompresión. Devuelve (estado, url_final, cabeceras, cuerpo)."""
    with _open(url, headers, timeout) as r:
        try:
            raw = r.read(max_bytes + 1)
        except (OSError, http.client.HTTPException) as e:
            raise HttpError(f"lectura interrumpida de {url}: {e}") from e
        if len(raw) > max_bytes:
            raise HttpError(f"respuesta demasiado grande (> {max_bytes} bytes): {url}")
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            raw = gzip.decompress(raw)
        elif enc == "deflate":
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        return r.status, r.geturl(), hdrs, raw


def decode_body(raw: bytes, headers: dict) -> str:
    m = re.search(r"charset=([\w.-]+)", headers.get("content-type", ""), re.I)
    charset = m.group(1) if m else None
    if not charset:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w.-]+)", raw[:4096], re.I)
        charset = m2.group(1).decode("ascii", "ignore") if m2 else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def http_json(url: str, headers: dict | None = None, timeout: int = TIMEOUT):
    hdrs = {"Accept": "application/json"}
    hdrs.update(headers or {})
    _, _, h, raw = http_get(url, hdrs, timeout)
    return json.loads(decode_body(raw, h))


EXT_BY_CTYPE = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
    "image/avif": ".avif", "image/heic": ".heic", "video/mp4": ".mp4", "video/webm": ".webm",
    "video/quicktime": ".mov", "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "application/pdf": ".pdf",
}


def guess_ext(url: str, ctype: str = "") -> str:
    ctype = (ctype or "").split(";")[0].strip().lower()
    if ctype in EXT_BY_CTYPE:
        return EXT_BY_CTYPE[ctype]
    path = urllib.parse.urlsplit(url).path
    ext = os.path.splitext(path)[1].lower()
    if re.fullmatch(r"\.[a-z0-9]{2,5}", ext):
        return ext
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    fmt = (q.get("format") or [""])[0].lower()
    return f".{fmt}" if fmt in {"jpg", "jpeg", "png", "webp", "gif"} else ".bin"


def download(url: str, dest_dir: Path, stem: str, max_bytes: int = MAX_MEDIA_BYTES,
             timeout: int = 90) -> dict:
    """Descarga un fichero a dest_dir/stem.<ext> y devuelve ruta, tamaño y sha256."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    with _open(url, {"Accept-Encoding": "identity"}, timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        dest = dest_dir / (stem + guess_ext(url, ctype))
        tmp = dest.with_name(dest.name + ".part")
        with open(tmp, "wb") as f:
            while True:
                try:
                    chunk = r.read(1 << 16)
                except (OSError, http.client.HTTPException) as e:
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise HttpError(f"descarga interrumpida de {url}: {e}") from e
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise HttpError(f"fichero demasiado grande (> {max_bytes} bytes): {url}")
                h.update(chunk)
                f.write(chunk)
    tmp.replace(dest)
    return {"archivo": str(dest), "bytes": size, "sha256": h.hexdigest(), "content_type": ctype}


def registered_domain(host: str) -> str:
    host = (host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "gob", "gov", "net", "edu", "ac", "nom", "mil", "gv"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def host_of(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


# ---------------------------------------------------------------------------
# deps
# ---------------------------------------------------------------------------

TOOLS = {
    "yt-dlp": "descargar vídeos y metadatos de YouTube, X, TikTok, Instagram, Facebook...",
    "ffmpeg": "extraer fotogramas, audio y generar ELA",
    "ffprobe": "leer metadatos técnicos de vídeo e imagen",
    "exiftool": "metadatos EXIF/XMP/IPTC completos (opcional; el script trae un lector básico)",
    "c2patool": "leer credenciales de contenido C2PA (opcional)",
    "whisper": "transcribir audio (openai-whisper, opcional)",
    "mlx_whisper": "transcribir audio en Mac con Apple Silicon (opcional)",
    "whisper-cli": "transcribir audio con whisper.cpp (opcional; requiere BULONATOR_WHISPER_MODEL)",
    "whois": "datos de registro de dominios sin RDAP (p. ej. .es)",
}


def cmd_deps(args) -> int:
    found = {name: shutil.which(name) for name in TOOLS}
    transcribe = bool(
        os.environ.get("BULONATOR_TRANSCRIBE_CMD") or found["whisper"] or found["mlx_whisper"]
        or (found["whisper-cli"] and os.environ.get("BULONATOR_WHISPER_MODEL"))
    )
    caps = {
        "captura_redes_y_web": True,
        "descarga_video": bool(found["yt-dlp"]),
        "fotogramas_y_audio": bool(found["ffmpeg"] and found["ffprobe"]),
        "ela": bool(found["ffmpeg"]),
        "transcripcion_audio": transcribe,
        "metadatos_completos": bool(found["exiftool"]),
        "c2pa_detallado": bool(found["c2patool"]),
        "busqueda_inversa_api": bool(os.environ.get("SERPAPI_API_KEY")),
        "factcheck_api": bool(os.environ.get("GOOGLE_FACTCHECK_API_KEY")),
    }
    missing = [f"{n}: {d}" for n, d in TOOLS.items() if not found[n]]
    emit({
        "python": sys.version.split()[0],
        "bulonator": VERSION,
        "herramientas": {n: (p or None) for n, p in found.items()},
        "capacidades": caps,
        "faltan": missing,
        "sugerencia_instalacion": "macOS: brew install yt-dlp ffmpeg exiftool | "
                                  "Linux: pipx install yt-dlp; apt install ffmpeg libimage-exiftool-perl | "
                                  "Transcripción: pipx install openai-whisper",
    })
    return 0


# ---------------------------------------------------------------------------
# caso
# ---------------------------------------------------------------------------


def cmd_caso(args) -> int:
    base = Path(args.base).expanduser()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    case = (base / f"{stamp}-{slugify(args.entrada)}").resolve()
    for sub in ("media", "evidencias", "captura_raw"):
        (case / sub).mkdir(parents=True, exist_ok=True)
    emit({"caso": str(case), "media": str(case / "media"), "evidencias": str(case / "evidencias")})
    return 0


# ---------------------------------------------------------------------------
# Extracción de HTML
# ---------------------------------------------------------------------------

SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "template"}
TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "figcaption", "pre", "td"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "source", "track", "wbr"}
JUNK_IMG = re.compile(r"(logo|icon|avatar|sprite|pixel|blank|placeholder|emoji|badge|banner-ad|1x1)", re.I)


class PageParser(HTMLParser):
    """Extractor tolerante de metadatos, texto, multimedia y enlaces de una página."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.meta: dict[str, str] = {}
        self.title = ""
        self.lang = ""
        self.canonical = ""
        self.jsonld: list = []
        self.blocks: list[tuple[bool, str]] = []  # (dentro_de_article_o_main, texto)
        self.images: list[dict] = []
        self.videos: list[str] = []
        self.iframes: list[str] = []
        self.links: list[dict] = []
        self.times: list[str] = []
        self._skip: list[str] = []  # pila de etiquetas cuyo contenido se ignora
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []
        self._main_depth = 0
        self._text_tag: str | None = None
        self._buf: list[str] = []
        self._link: dict | None = None
        self._blockquote_tweet = 0

    def _pop_skip(self, tag: str) -> None:
        while self._skip:
            if self._skip.pop() == tag:
                break

    def _abs(self, url: str) -> str:
        return urllib.parse.urljoin(self.base, html.unescape(url.strip()))

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
            return
        if tag == "link" and "canonical" in a.get("rel", "").lower() and a.get("href"):
            self.canonical = self._abs(a["href"])
            return
        if tag == "script":
            if "ld+json" in a.get("type", "").lower():
                self._in_jsonld = True
                self._jsonld_buf = []
            else:
                self._skip.append("script")
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "time" and a.get("datetime"):
            self.times.append(a["datetime"])
        # La cabecera de un artículo (titular, entradilla, firma) sí interesa; la de la web no.
        if tag in SKIP_TAGS and not (tag == "header" and self._main_depth > 0):
            if tag not in VOID_TAGS:
                self._skip.append(tag)
            return
        if tag in ("article", "main"):
            self._main_depth += 1
        if tag == "blockquote" and "twitter-tweet" in a.get("class", ""):
            self._blockquote_tweet += 1
        if self._skip:
            return
        if tag == "img":
            src = a.get("src") or a.get("data-src") or a.get("data-lazy-src") or ""
            srcset = a.get("srcset") or a.get("data-srcset") or ""
            if srcset:
                cands = [c.strip().split(" ")[0] for c in srcset.split(",") if c.strip()]
                if cands:
                    src = cands[-1]
            if src and not src.startswith("data:"):
                self.images.append({"url": self._abs(src), "alt": a.get("alt", ""),
                                    "en_articulo": self._main_depth > 0})
        elif tag in ("video", "source") and a.get("src"):
            self.videos.append(self._abs(a["src"]))
        elif tag == "iframe" and (a.get("src") or a.get("data-src")):
            self.iframes.append(self._abs(a.get("src") or a.get("data-src")))
        elif tag == "a" and a.get("href"):
            href = self._abs(a["href"])
            if href.startswith("http"):
                self._link = {"url": href, "texto": "", "en_articulo": self._main_depth > 0,
                              "en_tuit_incrustado": self._blockquote_tweet > 0}
        if tag in TEXT_TAGS and self._text_tag is None:
            self._text_tag = tag
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "script":
            if self._in_jsonld:
                self._in_jsonld = False
                raw = "".join(self._jsonld_buf).strip()
                try:
                    self.jsonld.append(json.loads(raw))
                except ValueError:
                    pass
            elif "script" in self._skip:
                self._pop_skip("script")
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in self._skip:
            self._pop_skip(tag)
            return
        if tag in ("article", "main"):
            self._main_depth = max(0, self._main_depth - 1)
        if tag == "blockquote" and self._blockquote_tweet:
            self._blockquote_tweet -= 1
        if tag == "a" and self._link is not None:
            self._link["texto"] = re.sub(r"\s+", " ", self._link["texto"]).strip()[:200]
            self.links.append(self._link)
            self._link = None
        if tag == self._text_tag:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if text:
                self.blocks.append((self._main_depth > 0, text))
            self._text_tag = None
            self._buf = []

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._in_title:
            self.title += data
            return
        if self._skip:
            return
        if self._text_tag is not None:
            self._buf.append(data)
        if self._link is not None:
            self._link["texto"] += data


def _jsonld_items(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _jsonld_items(x)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            yield from _jsonld_items(obj["@graph"])
        yield obj


def _names(val) -> list[str]:
    out = []
    for v in val if isinstance(val, list) else [val]:
        if isinstance(v, dict) and v.get("name"):
            out.append(str(v["name"]))
        elif isinstance(v, str):
            out.append(v)
    return out


def extract_page(url: str, html_text: str) -> dict:
    p = PageParser(url)
    try:
        p.feed(html_text)
        p.close()
    except Exception as e:  # HTML muy roto: devolvemos lo que haya
        p.meta.setdefault("_error_parser", str(e))
    m = p.meta
    article_ld = {}
    for item in _jsonld_items(p.jsonld):
        types = item.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(t in {"NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting", "AnalysisNewsArticle",
                     "OpinionNewsArticle", "SocialMediaPosting", "VideoObject", "WebPage"} for t in types):
            if not article_ld or "Article" in str(types):
                article_ld = item
    in_main = [t for flag, t in p.blocks if flag]
    blocks = in_main if sum(len(t) for t in in_main) > 400 else [t for _, t in p.blocks]
    seen, text_parts = set(), []
    for t in blocks:
        if t not in seen and len(t) > 1:
            seen.add(t)
            text_parts.append(t)
    images, seen_img = [], set()
    og_img = m.get("og:image") or m.get("twitter:image") or m.get("twitter:image:src")
    if og_img:
        images.append({"url": urllib.parse.urljoin(url, og_img), "alt": m.get("og:image:alt", ""), "origen": "og:image"})
        seen_img.add(images[0]["url"])
    for img in p.images:
        if img["url"] in seen_img or JUNK_IMG.search(img["url"]) or img["url"].lower().endswith(".svg"):
            continue
        seen_img.add(img["url"])
        img["origen"] = "articulo" if img.pop("en_articulo") else "pagina"
        images.append(img)
    images.sort(key=lambda x: {"og:image": 0, "articulo": 1, "pagina": 2}[x["origen"]])
    embeds = []
    for link in p.links:
        if link["en_tuit_incrustado"] and re.search(r"(twitter|x)\.com/[^/]+/status/\d+", link["url"]):
            embeds.append({"tipo": "tuit", "url": link["url"]})
    for fr in p.iframes:
        if re.search(r"youtube(-nocookie)?\.com/embed/|player\.vimeo|tiktok\.com/embed|instagram\.com/p/|"
                     r"facebook\.com/plugins|platform\.twitter|dailymotion\.com/embed", fr):
            embeds.append({"tipo": "iframe", "url": fr})
    page_host = registered_domain(host_of(url))
    outbound = []
    for link in p.links:
        if link["en_articulo"] and registered_domain(host_of(link["url"])) != page_host:
            outbound.append({"url": link["url"], "texto": link["texto"]})
    date_pub = (m.get("article:published_time") or article_ld.get("datePublished") or m.get("date")
                or m.get("pubdate") or m.get("dc.date") or m.get("datepublished") or (p.times[0] if p.times else None))
    return {
        "titulo": (m.get("og:title") or article_ld.get("headline") or p.title or "").strip(),
        "descripcion": m.get("og:description") or m.get("description") or "",
        "texto": "\n\n".join(text_parts),
        "autor": _names(article_ld.get("author")) or ([m["author"]] if m.get("author") else []) or
                 ([m["article:author"]] if m.get("article:author") else []),
        "medio": m.get("og:site_name") or ", ".join(_names(article_ld.get("publisher"))) or page_host,
        "fecha_publicacion": date_pub,
        "fecha_modificacion": m.get("article:modified_time") or article_ld.get("dateModified"),
        "idioma": p.lang or m.get("og:locale", ""),
        "canonica": p.canonical,
        "tipo_og": m.get("og:type", ""),
        "imagenes": images,
        "videos": list(dict.fromkeys(p.videos + ([m["og:video"]] if m.get("og:video") else []))),
        "incrustados": embeds,
        "enlaces_salientes": outbound[:80],
        "meta": {k: v for k, v in m.items() if k.startswith(("og:", "article:", "twitter:", "author", "date",
                                                               "description", "keywords", "news_keywords"))},
        "jsonld_tipo": article_ld.get("@type"),
    }


# ---------------------------------------------------------------------------
# Capturadores por plataforma
# ---------------------------------------------------------------------------

TWITTER_HOSTS = {"x.com", "twitter.com", "mobile.twitter.com", "mobile.x.com", "fxtwitter.com",
                 "vxtwitter.com", "fixupx.com", "fixvx.com", "nitter.net", "nitter.poast.org"}
VIDEO_HOSTS = ("vimeo.com", "dailymotion.com", "twitch.tv", "rumble.com", "odysee.com", "kick.com",
               "bitchute.com", "threads.net", "threads.com", "vk.com", "ok.ru", "bilibili.com")


def detect_platform(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    host = host_of(url)
    path = parts.path
    if (host in TWITTER_HOSTS or host.endswith(".twitter.com")) and re.search(r"/status(?:es)?/\d+", path):
        return "x"
    if host == "bsky.app" and "/post/" in path:
        return "bluesky"
    if host in {"t.me", "telegram.me"} and re.search(r"^/(s/)?[\w]+/\d+", path):
        return "telegram"
    if host.endswith("youtube.com") or host == "youtu.be":
        return "youtube"
    if host.endswith("tiktok.com"):
        return "tiktok"
    if host.endswith("instagram.com"):
        return "instagram"
    if host.endswith("facebook.com") or host in {"fb.watch", "fb.com"}:
        return "facebook"
    if host.endswith("reddit.com") or host == "redd.it":
        return "reddit"
    if re.fullmatch(r"/@[\w.\-]+/\d+", path):
        return "mastodon"
    if host.endswith(VIDEO_HOSTS):
        return "video"
    return "web"


def tweet_id(url: str) -> str | None:
    m = re.search(r"/status(?:es)?/(\d+)", url)
    return m.group(1) if m else None


def _base36(x: float) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    ip, fp = int(x), x - int(x)
    s = ""
    while ip > 0:
        s = digits[ip % 36] + s
        ip //= 36
    s = s or "0"
    frac = ""
    for _ in range(11):
        fp *= 36
        d = int(fp)
        frac += digits[d]
        fp -= d
    return s + "." + frac


def syndication_token(tid: str) -> str:
    return re.sub(r"(0+|\.)", "", _base36((int(tid) / 1e15) * math.pi))


def _orig_photo(url: str) -> str:
    if "pbs.twimg.com/media/" not in url:
        return url
    parts = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(parts.query))
    q["name"] = "orig"
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(q)))


def _ts_to_iso(ts) -> str | None:
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _fx_tweet_summary(t: dict) -> dict:
    a = t.get("author") or {}
    media = []
    for item in ((t.get("media") or {}).get("all") or []):
        media.append({"tipo": {"photo": "imagen", "video": "video", "gif": "video"}.get(item.get("type"), item.get("type")),
                      "url": _orig_photo(item.get("url", "")), "miniatura": item.get("thumbnail_url"),
                      "ancho": item.get("width"), "alto": item.get("height"), "duracion": item.get("duration"),
                      "texto_alternativo": item.get("altText") or item.get("alt_text")})
    note = t.get("community_note")
    if isinstance(note, dict):
        note = note.get("text") or json.dumps(note, ensure_ascii=False)[:2000]
    return {
        "url": t.get("url"),
        "texto": t.get("text"),
        "fecha_publicacion": _ts_to_iso(t.get("created_timestamp")) or t.get("created_at"),
        "idioma": t.get("lang"),
        "cliente": t.get("source"),
        "autor": {k: v for k, v in {
            "nombre": a.get("name"), "usuario": a.get("screen_name"), "url": a.get("url"),
            "descripcion": a.get("description"), "ubicacion": a.get("location"),
            "alta_en_la_red": a.get("joined"), "seguidores": a.get("followers"),
            "siguiendo": a.get("following"), "publicaciones": a.get("tweets") or a.get("statuses"),
            "publicaciones_con_media": a.get("media_count"), "me_gusta_dados": a.get("likes"),
            "verificacion": a.get("verification"), "protegida": a.get("protected"),
            "web": (a.get("website") or {}).get("url") if isinstance(a.get("website"), dict) else a.get("website"),
        }.items() if v not in (None, "")},
        "republicado_por": t.get("reposted_by"),
        "metricas": {k: t.get(k) for k in ("likes", "retweets", "replies", "quotes", "views", "bookmarks")
                     if t.get(k) is not None},
        "respuesta_a": {"usuario": t.get("replying_to"), "id": t.get("replying_to_status")} if t.get("replying_to") else None,
        "media": media,
        "nota_de_la_comunidad": note,
        "encuesta": t.get("poll"),
    }


def capture_x(url: str, out: dict, raw_dir: Path) -> list[dict]:
    tid = tweet_id(url)
    out["id"] = tid
    try:
        data = http_json(f"https://api.fxtwitter.com/status/{tid}")
        (raw_dir / "fxtwitter.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        t = data.get("tweet")
        if not t:
            raise HttpError(f"fxtwitter respondió sin tuit: {data.get('message')}")
        s = _fx_tweet_summary(t)
        out["metodo"].append("api.fxtwitter.com")
        media = s.pop("media")
        out.update({k: v for k, v in s.items() if v not in (None, "", {}, [])})
        if t.get("quote"):
            q = _fx_tweet_summary(t["quote"])
            out["cita"] = q
            media += [dict(m, de="tuit citado") for m in q.get("media", [])]
        return media
    except (HttpError, ValueError) as e:
        out["avisos"].append(f"fxtwitter falló: {e}")
    try:
        data = http_json(f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&lang=es&token={syndication_token(tid)}")
        (raw_dir / "syndication.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        out["metodo"].append("cdn.syndication.twimg.com")
        u = data.get("user") or {}
        out.update({
            "texto": data.get("text"), "fecha_publicacion": data.get("created_at"), "idioma": data.get("lang"),
            "autor": {"nombre": u.get("name"), "usuario": u.get("screen_name"),
                      "verificado_azul": u.get("is_blue_verified")},
            "metricas": {"likes": data.get("favorite_count"), "replies": data.get("conversation_count")},
        })
        if data.get("birdwatch_pivot"):
            out["nota_de_la_comunidad"] = data["birdwatch_pivot"]
        if data.get("quoted_tweet"):
            qt = data["quoted_tweet"]
            out["cita"] = {"texto": qt.get("text"), "autor": (qt.get("user") or {}).get("screen_name"),
                           "fecha_publicacion": qt.get("created_at")}
        media = []
        for md in data.get("mediaDetails") or []:
            if md.get("type") == "photo":
                media.append({"tipo": "imagen", "url": _orig_photo(md.get("media_url_https", ""))})
            else:
                variants = [v for v in (md.get("video_info") or {}).get("variants", [])
                            if v.get("content_type") == "video/mp4"]
                variants.sort(key=lambda v: v.get("bitrate", 0))
                media.append({"tipo": "video", "url": variants[-1]["url"] if variants else None,
                              "miniatura": md.get("media_url_https")})
        return media
    except (HttpError, ValueError) as e:
        out["avisos"].append(f"syndication falló: {e}")
    out["avisos"].append("No se pudo leer el tuit sin sesión. Pide al usuario el texto o una captura de pantalla, "
                         "o usa un navegador (MCP) si está disponible.")
    return []


def capture_bluesky(url: str, out: dict, raw_dir: Path) -> list[dict]:
    m = re.search(r"/profile/([^/]+)/post/([^/?#]+)", url)
    if not m:
        out["avisos"].append("URL de Bluesky no reconocida")
        return []
    actor, rkey = m.groups()
    api = "https://public.api.bsky.app/xrpc"
    did = actor
    if not actor.startswith("did:"):
        did = http_json(f"{api}/com.atproto.identity.resolveHandle?handle={urllib.parse.quote(actor)}")["did"]
    uri = f"at://{did}/app.bsky.feed.post/{rkey}"
    data = http_json(f"{api}/app.bsky.feed.getPostThread?uri={urllib.parse.quote(uri)}&depth=0&parentHeight=1")
    (raw_dir / "bluesky.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    post = data["thread"]["post"]
    rec = post.get("record", {})
    a = post.get("author", {})
    out["metodo"].append("public.api.bsky.app")
    out.update({
        "id": uri, "texto": rec.get("text"), "fecha_publicacion": rec.get("createdAt"),
        "idioma": ",".join(rec.get("langs") or []),
        "autor": {"nombre": a.get("displayName"), "usuario": a.get("handle"), "did": a.get("did"),
                  "alta_en_la_red": a.get("createdAt")},
        "metricas": {k: post.get(k) for k in ("likeCount", "repostCount", "replyCount", "quoteCount")},
    })
    media = []

    def walk(embed):
        if not isinstance(embed, dict):
            return
        for img in embed.get("images") or []:
            media.append({"tipo": "imagen", "url": img.get("fullsize"), "texto_alternativo": img.get("alt")})
        if embed.get("playlist"):
            media.append({"tipo": "video", "url": embed["playlist"], "miniatura": embed.get("thumbnail"),
                          "requiere": "yt-dlp o ffmpeg (HLS)"})
        if embed.get("external"):
            out.setdefault("enlaces_salientes", []).append({"url": embed["external"].get("uri"),
                                                            "texto": embed["external"].get("title")})
        if embed.get("record"):
            rec2 = embed["record"]
            if rec2.get("value"):
                out["cita"] = {"texto": rec2["value"].get("text"),
                               "autor": (rec2.get("author") or {}).get("handle"),
                               "fecha_publicacion": rec2["value"].get("createdAt")}
            for e in rec2.get("embeds") or []:
                walk(e)
        if embed.get("media"):
            walk(embed["media"])

    walk(post.get("embed"))
    return media


def capture_telegram(url: str, out: dict, raw_dir: Path) -> list[dict]:
    m = re.search(r"t(?:elegram)?\.me/(?:s/)?([\w]+)/(\d+)", url)
    channel, msg = m.groups()
    embed = f"https://t.me/{channel}/{msg}?embed=1&mode=tme"
    _, _, h, raw = http_get(embed)
    page = decode_body(raw, h)
    (raw_dir / "telegram.html").write_text(page, encoding="utf-8")
    out["metodo"].append("t.me embed")
    tm = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', page, re.S)
    text = ""
    if tm:
        text = re.sub(r"<br\s*/?>", "\n", tm.group(1))
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    date = re.search(r'<time[^>]+datetime="([^"]+)"', page)
    views = re.search(r'tgme_widget_message_views">([^<]+)<', page)
    author = re.search(r'tgme_widget_message_owner_name"[^>]*>(?:<span[^>]*>)?([^<]+)<', page)
    fwd = re.search(r'tgme_widget_message_forwarded_from_name"[^>]*>(?:<span[^>]*>)?([^<]+)<', page)
    out.update({"texto": text, "fecha_publicacion": date.group(1) if date else None,
                "autor": {"nombre": html.unescape(author.group(1)) if author else None, "usuario": channel},
                "metricas": {"vistas": views.group(1) if views else None}})
    if fwd:
        out["reenviado_de"] = html.unescape(fwd.group(1))
    media = []
    for u in re.findall(r"tgme_widget_message_photo_wrap[^>]+background-image:url\('([^']+)'\)", page):
        media.append({"tipo": "imagen", "url": u})
    for u in re.findall(r'<video[^>]+src="([^"]+)"', page):
        media.append({"tipo": "video", "url": html.unescape(u)})
    if not text and not media:
        out["avisos"].append("El mensaje de Telegram no es público o no se pudo leer.")
    return media


def capture_mastodon(url: str, out: dict, raw_dir: Path) -> list[dict]:
    parts = urllib.parse.urlsplit(url)
    sid = parts.path.rstrip("/").split("/")[-1]
    data = http_json(f"{parts.scheme}://{parts.netloc}/api/v1/statuses/{sid}")
    (raw_dir / "mastodon.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    a = data.get("account", {})
    out["metodo"].append("mastodon api v1")
    out.update({
        "texto": html.unescape(re.sub(r"<[^>]+>", " ", data.get("content", ""))).strip(),
        "fecha_publicacion": data.get("created_at"), "idioma": data.get("language"),
        "autor": {"nombre": a.get("display_name"), "usuario": a.get("acct"), "url": a.get("url"),
                  "alta_en_la_red": a.get("created_at"), "seguidores": a.get("followers_count"),
                  "publicaciones": a.get("statuses_count"), "bot": a.get("bot")},
        "metricas": {"favoritos": data.get("favourites_count"), "impulsos": data.get("reblogs_count"),
                     "respuestas": data.get("replies_count")},
    })
    return [{"tipo": "imagen" if m.get("type") == "image" else "video", "url": m.get("url"),
             "texto_alternativo": m.get("description")} for m in data.get("media_attachments", [])]


def capture_reddit(url: str, out: dict, raw_dir: Path) -> list[dict]:
    base = url.split("?")[0].rstrip("/")
    data = http_json(base + ".json?raw_json=1")
    (raw_dir / "reddit.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    post = data[0]["data"]["children"][0]["data"]
    out["metodo"].append("reddit .json")
    out.update({
        "titulo": post.get("title"), "texto": post.get("selftext"),
        "fecha_publicacion": _ts_to_iso(post.get("created_utc")),
        "autor": {"usuario": post.get("author"), "comunidad": post.get("subreddit_name_prefixed")},
        "metricas": {"puntos": post.get("score"), "comentarios": post.get("num_comments")},
    })
    media = []
    if post.get("url_overridden_by_dest"):
        dest = post["url_overridden_by_dest"]
        if re.search(r"\.(jpe?g|png|gif|webp)$", dest, re.I):
            media.append({"tipo": "imagen", "url": dest})
        else:
            out.setdefault("enlaces_salientes", []).append({"url": dest, "texto": "enlace del post"})
    for item in (post.get("media_metadata") or {}).values():
        if item.get("s", {}).get("u"):
            media.append({"tipo": "imagen", "url": item["s"]["u"]})
    if post.get("is_video"):
        media.append({"tipo": "video", "url": url, "requiere": "yt-dlp"})
    return media


def _strip_ytdlp(info: dict) -> dict:
    drop = {"formats", "requested_formats", "thumbnails", "automatic_captions", "subtitles", "http_headers",
            "requested_downloads", "fragments", "heatmap"}
    return {k: v for k, v in info.items() if k not in drop}


def capture_ytdlp(url: str, out: dict, raw_dir: Path, media_dir: Path, download_media: bool) -> bool:
    if not shutil.which("yt-dlp"):
        out["avisos"].append("yt-dlp no está instalado: no se pueden descargar vídeos de esta plataforma.")
        return False
    rc, so, se = run(["yt-dlp", "-J", "--no-playlist", "--no-warnings", url], timeout=180)
    if rc != 0 or not so.strip():
        out["avisos"].append(f"yt-dlp no pudo leer los metadatos: {tail(se, 300)}")
        return False
    try:
        info = json.loads(so)
    except ValueError:
        out["avisos"].append("yt-dlp devolvió metadatos ilegibles")
        return False
    subs = sorted(set(list((info.get("subtitles") or {}).keys())))
    autosubs = [k for k in (info.get("automatic_captions") or {}).keys() if re.match(r"(es|en|ca|gl|eu|pt|fr)(-|$)", k)]
    (raw_dir / "yt-dlp.json").write_text(json.dumps(_strip_ytdlp(info), ensure_ascii=False, indent=2), encoding="utf-8")
    out["metodo"].append("yt-dlp")
    ts = info.get("timestamp") or info.get("release_timestamp")
    upload = info.get("upload_date")
    out.update({k: v for k, v in {
        "id": info.get("id"),
        "titulo": info.get("title"),
        "texto": info.get("description"),
        "fecha_publicacion": _ts_to_iso(ts) or (f"{upload[:4]}-{upload[4:6]}-{upload[6:]}" if upload else None),
        "autor": {"nombre": info.get("uploader") or info.get("channel"),
                  "usuario": info.get("uploader_id") or info.get("channel_id"),
                  "url": info.get("uploader_url") or info.get("channel_url"),
                  "seguidores": info.get("channel_follower_count")},
        "duracion_s": info.get("duration"),
        "metricas": {k: info.get(k) for k in ("view_count", "like_count", "comment_count", "repost_count")
                     if info.get(k) is not None},
        "etiquetas": info.get("tags") or None,
        "ubicacion": info.get("location"),
        "subtitulos_disponibles": subs or None,
        "subtitulos_automaticos": autosubs or None,
    }.items() if v not in (None, "", {}, [])})
    if not download_media:
        return True
    stem = slugify(f"{info.get('extractor_key', 'video')}-{info.get('id', 'x')}", 60)
    tmpl = str(media_dir / f"{stem}.%(ext)s")
    rc, so, se = run(["yt-dlp", "--no-playlist", "--no-warnings", "--no-progress",
                      "-f", "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b", "--merge-output-format", "mp4",
                      "--max-filesize", "500M", "--write-thumbnail", "-o", tmpl,
                      "--print", "after_move:filepath", url], timeout=900)
    paths = [line.strip() for line in so.splitlines() if line.strip() and os.path.exists(line.strip())]
    if rc != 0 and not paths:
        out["avisos"].append(f"yt-dlp no pudo descargar el vídeo: {tail(se, 300)}")
    for pth in paths:
        out["media"].append({"tipo": "video", "url": url, "archivo": pth, "sha256": sha256_file(Path(pth)),
                             "bytes": os.path.getsize(pth), "descargado_con": "yt-dlp"})
    for thumb in sorted(media_dir.glob(f"{stem}.*")):
        if thumb.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            out["media"].append({"tipo": "imagen", "rol": "miniatura", "archivo": str(thumb),
                                 "sha256": sha256_file(thumb)})
    if subs or autosubs:
        langs = ",".join(sorted({*(s for s in subs if re.match(r"(es|en|ca|gl|eu)", s)), *autosubs})) or "es.*,en.*"
        run(["yt-dlp", "--no-playlist", "--no-warnings", "--skip-download", "--write-subs", "--write-auto-subs",
             "--sub-langs", langs, "--sub-format", "vtt/srt/best", "-o", tmpl, url], timeout=180)
        for sub in sorted(media_dir.glob(f"{stem}*.vtt")) + sorted(media_dir.glob(f"{stem}*.srt")):
            out["media"].append({"tipo": "subtitulos", "archivo": str(sub)})
    return True


MEDIA_EXT = re.compile(r"\.(jpe?g|png|gif|webp|avif|heic|mp4|mov|webm|m4v|mp3|m4a|ogg|opus|wav|pdf)$", re.I)


def capture_web(url: str, out: dict, raw_dir: Path, media_dir: Path, download_media: bool,
                max_media: int) -> list[dict]:
    if MEDIA_EXT.search(urllib.parse.urlsplit(url).path):
        info = download(url, media_dir, "archivo-enlazado")
        ext = Path(info["archivo"]).suffix.lower()
        kind = ("imagen" if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic"} else
                "documento" if ext == ".pdf" else
                "audio" if ext in {".mp3", ".m4a", ".ogg", ".opus", ".wav"} else "video")
        out["metodo"].append("descarga directa")
        out["media"].append(dict(info, tipo=kind, url=url))
        return []
    status, final, h, raw = http_get(url)
    out["url_final"] = final
    out["http"] = {"estado": status, "content_type": h.get("content-type"), "servidor": h.get("server"),
                   "ultima_modificacion": h.get("last-modified")}
    ctype = (h.get("content-type") or "").split(";")[0].lower()
    if ctype.startswith(("image/", "video/", "audio/")) or ctype == "application/pdf":
        stem = "documento" if ctype == "application/pdf" else "archivo-enlazado"
        dest = media_dir / (stem + guess_ext(final, ctype))
        dest.write_bytes(raw)
        kind = {"image": "imagen", "video": "video", "audio": "audio"}.get(ctype.split("/")[0], "documento")
        out["metodo"].append("descarga directa")
        out["media"].append({"tipo": kind, "url": final, "archivo": str(dest), "sha256": hashlib.sha256(raw).hexdigest(),
                             "bytes": len(raw)})
        return []
    page = decode_body(raw, h)
    (raw_dir / "pagina.html").write_text(page, encoding="utf-8")
    info = extract_page(final, page)
    out["metodo"].append("html")
    for k in ("titulo", "descripcion", "texto", "medio", "fecha_publicacion", "fecha_modificacion", "idioma",
              "canonica", "tipo_og", "incrustados", "enlaces_salientes", "meta", "jsonld_tipo"):
        if info.get(k):
            out[k] = info[k]
    if info["autor"]:
        out["autor"] = {"nombre": ", ".join(info["autor"])}
    if len(info["texto"]) < 300:
        out["avisos"].append("Se extrajo poco texto: la página puede cargarse con JavaScript, tener muro de pago "
                             "o requerir sesión. Prueba WebFetch, un navegador (MCP) o pide el texto al usuario.")
    media = [{"tipo": "imagen", "url": i["url"], "texto_alternativo": i.get("alt"), "origen": i["origen"]}
             for i in info["imagenes"][:max_media]]
    media += [{"tipo": "video", "url": v} for v in info["videos"][:3]]
    return media


def wayback_info(url: str) -> dict:
    res: dict = {"enlace_archive_today": f"https://archive.ph/newest/{url}"}
    try:
        j = http_json("https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=""), timeout=25)
        closest = (j.get("archived_snapshots") or {}).get("closest")
        if closest:
            res["copia_mas_reciente"] = {"url": closest.get("url"), "fecha": closest.get("timestamp")}
    except (HttpError, ValueError) as e:
        res["error_disponibilidad"] = str(e)
    try:
        q = urllib.parse.urlencode({"url": url, "output": "json", "limit": "1", "fl": "timestamp,original,statuscode"})
        rows = http_json("https://web.archive.org/cdx/search/cdx?" + q, timeout=40)
        if isinstance(rows, list) and len(rows) > 1:
            ts, orig, code = rows[1]
            res["primera_copia"] = {"fecha": ts, "url": f"https://web.archive.org/web/{ts}/{orig}", "estado": code}
    except (HttpError, ValueError) as e:
        res["error_cdx"] = str(e)
    return res


def wayback_save(url: str) -> dict:
    try:
        _, final, h, _ = http_get("https://web.archive.org/save/" + url, timeout=150, max_bytes=50 * 1024 * 1024)
        loc = h.get("content-location")
        snap = final if "/web/" in final else (f"https://web.archive.org{loc}" if loc else None)
        return {"guardado": bool(snap), "url": snap}
    except HttpError as e:
        return {"guardado": False, "error": str(e)}


def cmd_capturar(args) -> int:
    entrada = args.entrada.strip()
    case = Path(args.dir).expanduser().resolve()
    name = slugify(args.nombre, 40) if args.nombre else "captura"
    media_dir, raw_dir = case / "media", case / "captura_raw" / name
    media_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out: dict = {"entrada": entrada, "capturado_en": now_iso(), "herramienta": f"bulonator.py {VERSION}",
                 "metodo": [], "media": [], "avisos": []}

    local = Path(entrada).expanduser()
    if not re.match(r"^https?://", entrada, re.I):
        if local.exists():
            out["plataforma"] = "archivo_local"
            dest = media_dir / local.name
            if local.resolve() != dest.resolve():
                shutil.copy2(local, dest)
            out["media"].append({"tipo": "pendiente_de_analisis", "archivo": str(dest), "sha256": sha256_file(dest)})
        else:
            out["plataforma"] = "texto"
            out["texto"] = entrada
        (case / f"{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        emit(out)
        return 0

    url = entrada
    plat = detect_platform(url)
    out["plataforma"] = plat
    out["dominio"] = registered_domain(host_of(url))
    pending: list[dict] = []
    try:
        if plat == "x":
            pending = capture_x(url, out, raw_dir)
        elif plat == "bluesky":
            pending = capture_bluesky(url, out, raw_dir)
        elif plat == "telegram":
            pending = capture_telegram(url, out, raw_dir)
        elif plat == "mastodon":
            pending = capture_mastodon(url, out, raw_dir)
        elif plat == "reddit":
            pending = capture_reddit(url, out, raw_dir)
    except (HttpError, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        out["avisos"].append(f"La captura específica de {plat} falló ({type(e).__name__}: {e}); "
                             "se intenta como página web.")
        plat = "web"

    if plat in {"youtube", "tiktok", "instagram", "facebook", "video"}:
        ok = capture_ytdlp(url, out, raw_dir, media_dir, not args.sin_media)
        if not ok:
            plat = "web"
    if plat == "web" or (plat in {"instagram", "facebook", "tiktok"} and not out.get("texto")):
        try:
            pending += capture_web(url, out, raw_dir, media_dir, not args.sin_media, args.max_media)
        except HttpError as e:
            out["avisos"].append(f"No se pudo descargar la página: {e}")

    # Descarga de multimedia pendiente
    for i, item in enumerate(pending, 1):
        entry = dict(item)
        if args.sin_media or not item.get("url"):
            out["media"].append(entry)
            continue
        stem = f"{'' if name == 'captura' else name + '-'}m{i:02d}-{item.get('tipo', 'media')}"
        try:
            if item.get("requiere") and "yt-dlp" in item["requiere"] and shutil.which("yt-dlp"):
                tmpl = str(media_dir / f"{stem}.%(ext)s")
                rc, so, se = run(["yt-dlp", "--no-warnings", "--no-progress", "--merge-output-format", "mp4",
                                  "-o", tmpl, "--print", "after_move:filepath", item["url"]], timeout=900)
                pth = next((ln.strip() for ln in so.splitlines() if ln.strip() and os.path.exists(ln.strip())), None)
                if not pth:
                    raise HttpError(tail(se, 300))
                entry.update({"archivo": pth, "sha256": sha256_file(Path(pth)), "descargado_con": "yt-dlp"})
            else:
                entry.update(download(item["url"], media_dir, stem))
                if entry.get("tipo") == "imagen" and entry["bytes"] < 2048:
                    Path(entry["archivo"]).unlink(missing_ok=True)
                    continue  # píxel de seguimiento o icono: no aporta nada
        except HttpError as e:
            if item.get("tipo") == "video" and shutil.which("yt-dlp") and plat == "x":
                tmpl = str(media_dir / f"{stem}.%(ext)s")
                rc, so, se = run(["yt-dlp", "--no-warnings", "--no-progress", "-o", tmpl,
                                  "--print", "after_move:filepath", url], timeout=900)
                pth = next((ln.strip() for ln in so.splitlines() if ln.strip() and os.path.exists(ln.strip())), None)
                if pth:
                    entry.update({"archivo": pth, "sha256": sha256_file(Path(pth)), "descargado_con": "yt-dlp"})
                else:
                    entry["error"] = f"{e}; yt-dlp: {tail(se, 200)}"
            else:
                entry["error"] = str(e)
        out["media"].append(entry)

    if not args.sin_archivo:
        out["archivo_web"] = wayback_info(url)
        if args.archivar:
            out["archivo_web"]["nueva_copia"] = wayback_save(url)
    if not out.get("texto") and not out.get("titulo") and not any(m.get("archivo") for m in out["media"]):
        out["avisos"].append("CAPTURA VACÍA: no se obtuvo contenido. No se debe emitir veredicto sin el contenido.")
    out_file = case / f"{name}.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = dict(out, archivo_captura=str(out_file))
    if summary.get("texto") and len(summary["texto"]) > args.max_texto:
        summary["texto"] = summary["texto"][: args.max_texto] + f"… [recortado; texto completo en {out_file}]"
    summary.pop("meta", None)
    if len(summary.get("enlaces_salientes", [])) > 15:
        summary["enlaces_salientes"] = summary["enlaces_salientes"][:15] + [{"nota": "más enlaces en captura.json"}]
    emit(summary)
    return 0


# ---------------------------------------------------------------------------
# media: análisis forense básico
# ---------------------------------------------------------------------------

EXIF_TAGS = {
    0x010E: "ImageDescription", 0x010F: "Make", 0x0110: "Model", 0x0112: "Orientation", 0x0131: "Software",
    0x0132: "DateTime", 0x013B: "Artist", 0x8298: "Copyright", 0x8769: "_ExifIFD", 0x8825: "_GPSIFD",
    0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized", 0x9010: "OffsetTime", 0x9011: "OffsetTimeOriginal",
    0x9286: "UserComment", 0xA002: "PixelXDimension", 0xA003: "PixelYDimension", 0xA420: "ImageUniqueID",
    0xA430: "CameraOwnerName", 0xA431: "BodySerialNumber", 0xA433: "LensMake", 0xA434: "LensModel",
}
GPS_TAGS = {1: "GPSLatitudeRef", 2: "GPSLatitude", 3: "GPSLongitudeRef", 4: "GPSLongitude", 6: "GPSAltitude",
            7: "GPSTimeStamp", 29: "GPSDateStamp"}
TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


def parse_tiff_exif(b: bytes) -> dict:
    """Lector mínimo de EXIF (estructura TIFF). Tolerante a datos corruptos."""
    if len(b) < 8 or b[:2] not in (b"II", b"MM"):
        return {}
    e = "<" if b[:2] == b"II" else ">"

    def u16(o):
        return struct.unpack_from(e + "H", b, o)[0]

    def u32(o):
        return struct.unpack_from(e + "I", b, o)[0]

    def value(typ, cnt, off):
        if typ == 2:
            return b[off:off + cnt].rstrip(b"\0").decode("utf-8", "replace").strip()
        if typ == 7:
            raw = b[off:off + cnt]
            return raw[8:].decode("utf-8", "replace").strip("\0 ") if raw[:8] in (b"ASCII\0\0\0", b"UNICODE\0") else raw[:64].hex()
        fmt = {1: "B", 3: "H", 4: "I", 9: "i"}.get(typ)
        if fmt:
            vals = list(struct.unpack_from(e + fmt * cnt, b, off))
        elif typ in (5, 10):
            f = "I" if typ == 5 else "i"
            pairs = struct.unpack_from(e + f * (2 * cnt), b, off)
            vals = [round(pairs[i] / pairs[i + 1], 6) if pairs[i + 1] else 0 for i in range(0, len(pairs), 2)]
        else:
            return None
        return vals[0] if cnt == 1 else vals

    def ifd(off, names):
        res = {}
        if off <= 0 or off + 2 > len(b):
            return res
        for i in range(min(u16(off), 512)):
            ent = off + 2 + i * 12
            if ent + 12 > len(b):
                break
            tag, typ, cnt = u16(ent), u16(ent + 2), u32(ent + 4)
            name = names.get(tag)
            if not name or typ not in TYPE_SIZES or cnt > 100000:
                continue
            size = TYPE_SIZES[typ] * cnt
            voff = ent + 8 if size <= 4 else u32(ent + 8)
            if voff + size > len(b):
                continue
            try:
                res[name] = value(typ, cnt, voff)
            except struct.error:
                continue
        return res

    try:
        out = ifd(u32(4), EXIF_TAGS)
        exif_ptr, gps_ptr = out.pop("_ExifIFD", None), out.pop("_GPSIFD", None)
        if exif_ptr:
            sub = ifd(exif_ptr, EXIF_TAGS)
            sub.pop("_ExifIFD", None)
            sub.pop("_GPSIFD", None)
            out.update(sub)
        if gps_ptr:
            gps = ifd(gps_ptr, GPS_TAGS)

            def deg(v, ref):
                if isinstance(v, list) and len(v) == 3:
                    d = v[0] + v[1] / 60 + v[2] / 3600
                    return round(-d if ref in ("S", "W") else d, 6)
                return None

            lat = deg(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
            lon = deg(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
            if lat is not None and lon is not None:
                out["GPS"] = {"lat": lat, "lon": lon,
                              "mapa": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"}
            if gps.get("GPSDateStamp"):
                out["GPSDateStamp"] = gps["GPSDateStamp"]
        return out
    except struct.error:
        return {}


AI_MARKERS = {
    b"trainedalgorithmicmedia": "IPTC DigitalSourceType: generado por IA (trainedAlgorithmicMedia)",
    b"compositewithtrainedalgorithmicmedia": "IPTC DigitalSourceType: composición con elementos generados por IA",
    b"compositesynthetic": "IPTC DigitalSourceType: composición sintética",
    b"algorithmicmedia": "IPTC DigitalSourceType: medio algorítmico",
    b"midjourney": "Midjourney", b"dall-e": "DALL-E", b"dall\xc2\xb7e": "DALL-E", b"openai": "OpenAI",
    b"chatgpt": "ChatGPT", b"stable diffusion": "Stable Diffusion", b"stable-diffusion": "Stable Diffusion",
    b"stability ai": "Stability AI", b"comfyui": "ComfyUI", b"automatic1111": "AUTOMATIC1111",
    b"firefly": "Adobe Firefly", b"google ai": "Google AI", b"synthid": "SynthID", b"gemini": "Google Gemini",
    b"ideogram": "Ideogram", b"leonardo.ai": "Leonardo.ai", b"novelai": "NovelAI",
    b"black forest labs": "FLUX (Black Forest Labs)", b"flux": "FLUX", b"grok": "Grok (xAI)",
    b"runwayml": "Runway", b"sora": "Sora (OpenAI)", b"kling": "Kling", b"bing image creator": "Bing Image Creator",
    b"microsoft designer": "Microsoft Designer", b"copilot": "Microsoft Copilot", b"meta ai": "Meta AI",
    b"imagine with meta": "Meta AI", b"google veo": "Google Veo", b"hailuo": "Hailuo/MiniMax",
    b"pika labs": "Pika",
}
_AI_RE = re.compile(rb"(?<![a-z0-9])(" + b"|".join(re.escape(k) for k in sorted(AI_MARKERS, key=len, reverse=True))
                    + rb")(?![a-z0-9])")


def head_bytes(path: Path, n: int = 64) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def read_image_metadata(path: Path) -> dict:
    """EXIF, XMP, bloques de texto PNG y marcas C2PA/IA.

    Solo se examinan los bloques de metadatos (segmentos APPn de JPEG, fragmentos no gráficos de PNG
    y WebP), nunca los datos de píxeles, para evitar coincidencias casuales.
    """
    data = path.read_bytes()
    res: dict = {}
    exif_blob = None
    meta = bytearray()
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if marker == 0xDA or marker == 0xD9:
                break
            if 0xD0 <= marker <= 0xD7 or marker in (0x01, 0xFF):
                i += 2 if marker != 0xFF else 1
                continue
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            seg = data[i + 4:i + 2 + seglen]
            if 0xE0 <= marker <= 0xEF or marker == 0xFE:
                meta += seg
            if marker == 0xE1 and seg.startswith(b"Exif\0\0"):
                exif_blob = seg[6:]
            elif marker == 0xEB and (b"jumb" in seg or b"c2pa" in seg):
                res["c2pa"] = "Hay un manifiesto C2PA (Content Credentials) incrustado"
            i += 2 + seglen
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        i, texts = 8, {}
        while i + 8 <= len(data):
            ln, ctype = struct.unpack(">I4s", data[i:i + 8])
            chunk = data[i + 8:i + 8 + ln]
            if ctype not in (b"IDAT", b"fdAT", b"PLTE", b"tRNS"):
                meta += chunk
            if ctype == b"eXIf":
                exif_blob = chunk
            elif ctype in (b"tEXt", b"iTXt", b"zTXt"):
                key, _, val = chunk.partition(b"\0")
                if ctype == b"zTXt":
                    try:
                        val = zlib.decompress(val[1:])
                    except zlib.error:
                        val = b""
                elif ctype == b"iTXt":
                    flag = val[:1]
                    rest = val[2:].split(b"\0", 2)
                    val = rest[2] if len(rest) == 3 else b""
                    if flag == b"\x01":
                        try:
                            val = zlib.decompress(val)
                        except zlib.error:
                            val = b""
                meta += val
                texts[key.decode("latin-1", "replace")] = val.decode("utf-8", "replace")[:1500]
            elif ctype == b"caBX":
                res["c2pa"] = "Hay un manifiesto C2PA (Content Credentials) incrustado"
            if ctype == b"IEND":
                break
            i += 12 + ln
        if texts:
            res["png_texto"] = texts
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        i = 12
        while i + 8 <= len(data):
            fourcc, ln = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
            chunk = data[i + 8:i + 8 + ln]
            if fourcc not in (b"VP8 ", b"VP8L", b"ANMF", b"ALPH"):
                meta += chunk
            if fourcc == b"EXIF":
                exif_blob = chunk[6:] if chunk.startswith(b"Exif\0\0") else chunk
            i += 8 + ln + (ln & 1)
    else:
        meta += data[:262144]
    if exif_blob:
        res["exif"] = parse_tiff_exif(exif_blob)
    meta_b = bytes(meta)
    xs, xe = meta_b.find(b"<x:xmpmeta"), meta_b.find(b"</x:xmpmeta>")
    if xs >= 0 and xe > xs:
        xmp = meta_b[xs:xe + 12].decode("utf-8", "replace")
        fields = {}
        for key in ("xmp:CreatorTool", "xmp:CreateDate", "xmp:ModifyDate", "photoshop:DateCreated",
                    "exif:DateTimeOriginal", "Iptc4xmpExt:DigitalSourceType", "dc:creator", "dc:rights",
                    "photoshop:Credit", "photoshop:Source", "stEvt:softwareAgent", "tiff:Make", "tiff:Model"):
            vals = re.findall(rf'{re.escape(key)}="([^"]*)"', xmp) + re.findall(
                rf"<{re.escape(key)}>(.*?)</{re.escape(key)}>", xmp, re.S)
            vals = [re.sub(r"<[^>]+>", " ", v).strip() for v in vals if v.strip()]
            if vals:
                fields[key] = list(dict.fromkeys(vals))[:5]
        res["xmp"] = fields or {"nota": "XMP presente sin campos reconocidos", "extracto": xmp[:800]}
    if b"c2pa" in meta_b and "c2pa" not in res:
        res["c2pa"] = "Aparece la cadena 'c2pa' en los metadatos: posible manifiesto de Content Credentials"
    found = sorted({AI_MARKERS[m.group(1)] for m in _AI_RE.finditer(meta_b.lower())})
    if found:
        res["indicios_ia_en_metadatos"] = found
        res["nota_ia"] = ("Son cadenas encontradas en los metadatos (generador, software, credenciales). Indican "
                          "procedencia probable pero pueden faltar o haberse añadido a mano: confírmalo con otras pruebas.")
    return res


def ffprobe(path: Path) -> dict:
    rc, so, se = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], 60)
    if rc != 0:
        return {"error": tail(se, 300)}
    try:
        return json.loads(so)
    except ValueError:
        return {"error": "salida de ffprobe ilegible"}


def sniff_kind(path: Path) -> str:
    head = head_bytes(path)
    if head[:3] == b"\xff\xd8\xff" or head[:8] == b"\x89PNG\r\n\x1a\n" or head[:2] == b"BM":
        return "imagen"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "imagen_o_animacion"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "imagen_o_animacion"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"mif1", b"avif", b"msf1"):
        return "imagen"
    if head[:4] == b"%PDF":
        return "documento"
    return "audiovisual"


def ela(path: Path, outdir: Path) -> dict:
    if not shutil.which("ffmpeg"):
        return {"error": "ffmpeg no disponible"}
    recomp = outdir / "ela_recomprimida.jpg"
    out = outdir / "ela.png"
    rc, _, se = run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-q:v", "4", str(recomp)], 60)
    if rc != 0:
        return {"error": tail(se, 200)}
    amp = "clip(val*20,0,255)"
    fg = (f"[0:v]format=rgb24[a];[1:v]format=rgb24[b];[a][b]blend=all_mode=difference,"
          f"lutrgb=r='{amp}':g='{amp}':b='{amp}'")
    rc, _, se = run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-i", str(recomp), "-filter_complex", fg,
                     "-frames:v", "1", str(out)], 60)
    recomp.unlink(missing_ok=True)
    if rc != 0:
        return {"error": tail(se, 200)}
    return {"archivo": str(out),
            "como_leerla": "Zonas mucho más brillantes o con textura distinta al resto pueden indicar edición local. "
                           "Es una señal débil: bordes, texto y recompresiones también brillan. Nunca es prueba por sí sola."}


def transcribe(audio: Path, outdir: Path, lang: str | None) -> dict:
    custom = os.environ.get("BULONATOR_TRANSCRIBE_CMD")
    if custom:
        cmd = [c.replace("{audio}", str(audio)).replace("{outdir}", str(outdir)) for c in custom.split()]
    elif shutil.which("whisper"):
        cmd = ["whisper", str(audio), "--model", os.environ.get("BULONATOR_WHISPER_SIZE", "small"),
               "--output_format", "txt", "--output_dir", str(outdir)] + (["--language", lang] if lang else [])
    elif shutil.which("mlx_whisper"):
        cmd = ["mlx_whisper", str(audio), "--output-format", "txt", "--output-dir", str(outdir)] + (
            ["--language", lang] if lang else [])
    elif shutil.which("whisper-cli") and os.environ.get("BULONATOR_WHISPER_MODEL"):
        cmd = ["whisper-cli", "-m", os.environ["BULONATOR_WHISPER_MODEL"], "-f", str(audio), "-otxt",
               "-of", str(outdir / audio.stem)] + (["-l", lang] if lang else ["-l", "auto"])
    else:
        return {"disponible": False,
                "nota": "No hay transcriptor instalado (whisper, mlx_whisper o whisper-cli). El audio no se ha "
                        "podido escuchar: indícalo como limitación o pide al usuario una transcripción."}
    rc, so, se = run(cmd, timeout=1800)
    txts = sorted(outdir.glob(f"{audio.stem}*.txt"))
    if rc != 0 or not txts:
        return {"disponible": True, "error": tail(se or so, 300)}
    text = txts[0].read_text(encoding="utf-8", errors="replace").strip()
    return {"disponible": True, "archivo": str(txts[0]), "texto": text[:6000],
            "aviso": "Transcripción automática: puede contener errores. Comprueba los fragmentos clave."}


def analyze_audiovisual(path: Path, outdir: Path, probe: dict, n_frames: int, lang: str | None) -> dict:
    res: dict = {}
    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    has_video = any(s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1
                    for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    try:
        duration = float(fmt.get("duration") or 0)
    except ValueError:
        duration = 0.0
    res["duracion_s"] = round(duration, 2)
    tags = dict(fmt.get("tags") or {})
    for s in streams:
        for k, v in (s.get("tags") or {}).items():
            if k.lower() in {"creation_time", "handler_name", "encoder", "vendor_id"}:
                tags.setdefault(f"{s.get('codec_type')}:{k}", v)
    res["etiquetas_contenedor"] = tags
    res["pistas"] = [{"tipo": s.get("codec_type"), "codec": s.get("codec_name"), "ancho": s.get("width"),
                      "alto": s.get("height"), "fps": s.get("avg_frame_rate"), "canales": s.get("channels")}
                     for s in streams]
    if has_video and shutil.which("ffmpeg"):
        fdir = outdir / "fotogramas"
        fdir.mkdir(exist_ok=True)
        frames = []
        n = max(1, n_frames if duration > 2 else 1)
        for i in range(n):
            t = duration * (i + 0.5) / n if duration else 0
            dest = fdir / f"uniforme_{i + 1:02d}.jpg"
            rc, _, _ = run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                            "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", str(dest)], 60)
            if rc == 0 and dest.exists():
                frames.append({"archivo": str(dest), "segundo": round(t, 2)})
        res["fotogramas_uniformes"] = frames
        rc, _, se = run(["ffmpeg", "-v", "info", "-y", "-i", str(path), "-vf",
                         "select='gt(scene,0.35)',showinfo,scale='min(1280,iw)':-2", "-vsync", "vfr",
                         "-frames:v", str(n_frames), "-q:v", "3", str(fdir / "escena_%02d.jpg")], 300)
        times = re.findall(r"pts_time:([\d.]+)", se)
        scenes = sorted(fdir.glob("escena_*.jpg"))
        res["cambios_de_escena"] = [{"archivo": str(p), "segundo": round(float(times[i]), 2) if i < len(times) else None}
                                    for i, p in enumerate(scenes)]
        if len(frames) > 1:
            cols = 4
            rows = math.ceil(len(frames) / cols)
            sheet = outdir / "hoja_de_contactos.jpg"
            rc, _, _ = run(["ffmpeg", "-v", "error", "-y", "-i", str(fdir / "uniforme_%02d.jpg"), "-vf",
                            f"scale=360:-2,tile={cols}x{rows}:padding=4:color=white", "-frames:v", "1", str(sheet)], 60)
            if rc == 0 and sheet.exists():
                res["hoja_de_contactos"] = str(sheet)
    if has_audio and shutil.which("ffmpeg"):
        audio = outdir / "audio.wav"
        rc, _, se = run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                         str(audio)], 300)
        if rc == 0:
            res["audio"] = str(audio)
            res["transcripcion"] = transcribe(audio, outdir, lang)
        else:
            res["audio_error"] = tail(se, 200)
    elif not has_audio:
        res["audio"] = None
    return res


def cmd_media(args) -> int:
    path = Path(args.archivo).expanduser().resolve()
    if not path.exists():
        emit({"error": f"no existe {path}"})
        return 1
    outdir = Path(args.dir).expanduser().resolve() if args.dir else path.parent / "analisis" / slugify(path.stem, 40)
    outdir.mkdir(parents=True, exist_ok=True)
    kind = sniff_kind(path)
    res: dict = {"archivo": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size,
                 "tipo_detectado": kind, "carpeta_analisis": str(outdir), "avisos": []}
    probe = ffprobe(path) if shutil.which("ffprobe") else {"error": "ffprobe no disponible"}
    if "error" in probe:
        res["avisos"].append(f"ffprobe: {probe['error']}")
    vs = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    if vs:
        res["dimensiones"] = {"ancho": vs.get("width"), "alto": vs.get("height")}
    if kind.startswith("imagen"):
        res["metadatos"] = read_image_metadata(path)
        if not res["metadatos"].get("exif"):
            res["avisos"].append("Sin EXIF: habitual en imágenes que han pasado por redes sociales o mensajería. "
                                 "La ausencia de metadatos no prueba nada.")
        if shutil.which("exiftool"):
            rc, so, _ = run(["exiftool", "-json", "-G1", "-a", "-s", str(path)], 60)
            if rc == 0:
                (outdir / "exiftool.json").write_text(so, encoding="utf-8")
                res["exiftool"] = str(outdir / "exiftool.json")
        if head_bytes(path, 3) == b"\xff\xd8\xff":
            res["ela"] = ela(path, outdir)
    frames = 1
    try:
        frames = int((vs or {}).get("nb_frames") or 0)
    except ValueError:
        frames = 0
    is_anim = kind == "imagen_o_animacion" and (frames > 1 or float(probe.get("format", {}).get("duration") or 0) > 0.2)
    if kind == "audiovisual" or is_anim:
        res.update(analyze_audiovisual(path, outdir, probe, args.fotogramas, args.idioma))
    if kind == "documento":
        res["avisos"].append("Es un PDF: léelo con la herramienta Read y revisa sus metadatos de autoría y fechas.")
    if shutil.which("c2patool"):
        rc, so, _ = run(["c2patool", str(path)], 60)
        if rc == 0 and so.strip():
            res["c2patool"] = so[:4000]
    res["busqueda_inversa"] = "Para buscar el origen de esta imagen sube el archivo a Google Lens, Bing, Yandex o TinEye, " \
                              "o usa 'buscar-imagen' con la URL original de la imagen."
    (outdir / "analisis.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    emit(res)
    return 0


# ---------------------------------------------------------------------------
# wayback, dominio
# ---------------------------------------------------------------------------


def cmd_wayback(args) -> int:
    res = wayback_info(args.url)
    if args.guardar:
        res["nueva_copia"] = wayback_save(args.url)
    emit(res)
    return 0


def cmd_dominio(args) -> int:
    target = args.dominio
    dom = registered_domain(host_of(target) if "://" in target else target)
    res: dict = {"dominio": dom}
    try:
        j = http_json(f"https://rdap.org/domain/{dom}", timeout=25)
        if j.get("errorCode"):
            raise HttpError(j.get("title", "sin RDAP"))
        res["fuente"] = "RDAP"
        res["eventos"] = {ev.get("eventAction"): ev.get("eventDate") for ev in j.get("events", [])}
        for ent in j.get("entities", []):
            if "registrar" in ent.get("roles", []):
                vc = ent.get("vcardArray", [None, []])[1]
                res["registrador"] = next((x[3] for x in vc if x[0] == "fn"), None)
        res["estado"] = j.get("status")
        res["servidores_nombre"] = [ns.get("ldhName") for ns in j.get("nameservers", [])]
    except (HttpError, ValueError) as e:
        res["rdap_error"] = str(e)
        if dom.endswith(".es"):
            res["nota"] = ("Los .es no tienen RDAP público y el whois de dominios.es suele bloquear consultas "
                           "automáticas: consulta https://www.dominios.es/es/consultar-dominio (navegador).")
        rc, so, se = run(["whois", dom], 20)
        if rc == 0 and so:
            res["fuente"] = "whois"
            pats = {"creado": r"(?im)^\s*(?:creation date|created(?: on)?|registered(?: on)?|registration time|"
                              r"fecha de (?:alta|creaci[oó]n)|domain record activated)\s*[:.]+\s*(.+)$",
                    "expira": r"(?im)^\s*(?:registry expiry date|expir\w* (?:date|on)|paid-till|fecha de expiraci[oó]n)\s*[:.]+\s*(.+)$",
                    "registrador": r"(?im)^\s*(?:registrar|sponsoring registrar)\s*:\s*(.+)$",
                    "pais_titular": r"(?im)^\s*registrant country\s*:\s*(.+)$"}
            for key, pat in pats.items():
                m = re.search(pat, so)
                if m:
                    res[key] = m.group(1).strip()
            if len(res) <= 3:
                res["whois_extracto"] = so[:1500]
        else:
            res["whois_error"] = tail(se, 200) or "whois no disponible"
    emit(res)
    return 0


# ---------------------------------------------------------------------------
# BOE e INE
# ---------------------------------------------------------------------------

BOE_API = "https://www.boe.es/datosabiertos/api"


def _boe_items(node, out):
    if isinstance(node, list):
        for x in node:
            _boe_items(x, out)
    elif isinstance(node, dict):
        if "identificador" in node and "titulo" in node and ("url_html" in node or "url_pdf" in node):
            pdf = node.get("url_pdf")
            out.append({"identificador": node["identificador"], "titulo": node["titulo"],
                        "url_html": node.get("url_html"),
                        "url_pdf": pdf.get("texto") if isinstance(pdf, dict) else pdf})
            return
        for v in node.values():
            _boe_items(v, out)


def cmd_boe(args) -> int:
    if args.sumario:
        data = http_json(f"{BOE_API}/boe/sumario/{args.sumario}")
        items: list = []
        _boe_items(data.get("data", {}), items)
        if args.texto:
            words = [w.lower() for w in args.texto.split()]
            items = [i for i in items if all(w in i["titulo"].lower() for w in words)]
        emit({"fecha": args.sumario, "total": len(items), "resultados": items[: args.limite]})
        return 0
    if not args.texto:
        emit({"error": "indica un texto a buscar o --sumario AAAAMMDD"})
        return 1
    q = f"titulo:({args.texto})"
    if args.desde or args.hasta:
        q += f" AND fecha_publicacion:[{args.desde or '18000101'} TO {args.hasta or '29991231'}]"
    query = {"query": {"query_string": {"query": q}}, "sort": [{"fecha_publicacion": "desc"}]}
    url = f"{BOE_API}/legislacion-consolidada?" + urllib.parse.urlencode(
        {"query": json.dumps(query, ensure_ascii=False), "limit": args.limite})
    data = http_json(url)
    rows = []
    for x in data.get("data") or []:
        rows.append({"identificador": x.get("identificador"), "titulo": x.get("titulo"),
                     "rango": (x.get("rango") or {}).get("texto"), "ambito": (x.get("ambito") or {}).get("texto"),
                     "departamento": (x.get("departamento") or {}).get("texto"),
                     "fecha_disposicion": x.get("fecha_disposicion"), "fecha_publicacion": x.get("fecha_publicacion"),
                     "vigencia_agotada": x.get("vigencia_agotada"), "url": x.get("url_html_consolidada"),
                     "eli": x.get("url_eli")})
    emit({"consulta": q, "nota": "Busca en el TÍTULO de la legislación consolidada. Para anuncios, nombramientos, "
                                 "convocatorias o el texto completo usa WebSearch con allowed_domains=['boe.es'] "
                                 "o el sumario diario (--sumario).", "resultados": rows})
    return 0


INE_API = "https://servicios.ine.es/wstempus/js/ES"


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def cmd_ine(args) -> int:
    if args.datos:
        data = http_json(f"{INE_API}/DATOS_TABLA/{args.datos}?nult={args.nult}&tip=A", timeout=60)
        rows = []
        for serie in data:
            name = serie.get("Nombre", "")
            if args.texto and not all(w in _fold(name) for w in _fold(args.texto).split()):
                continue
            rows.append({"serie": name, "unidad": (serie.get("Unidad") or {}).get("Nombre"),
                         "datos": [{"periodo": d.get("NombrePeriodo") or f"{d.get('Anyo')}-{d.get('FK_Periodo')}",
                                    "valor": d.get("Valor"), "fecha": _ts_to_iso((d.get("Fecha") or 0) / 1000)}
                                   for d in serie.get("Data", [])]})
        emit({"tabla": args.datos, "url_tabla": f"https://www.ine.es/jaxiT3/Tabla.htm?t={args.datos}",
              "series": rows[: args.limite], "total_series": len(rows)})
        return 0
    if args.tablas:
        data = http_json(f"{INE_API}/TABLAS_OPERACION/{args.tablas}", timeout=60)
        rows = [{"id": t.get("Id"), "nombre": t.get("Nombre"), "ultima_modificacion": _ts_to_iso((t.get("Ultima_Modificacion") or 0) / 1000),
                 "url": f"https://www.ine.es/jaxiT3/Tabla.htm?t={t.get('Id')}"}
                for t in data if not args.texto or all(w in _fold(t.get("Nombre", "")) for w in _fold(args.texto).split())]
        emit({"operacion": args.tablas, "tablas": rows[: args.limite], "total": len(rows)})
        return 0
    if not args.texto:
        emit({"error": "indica un texto, --tablas CODIGO_OPERACION o --datos ID_TABLA"})
        return 1
    data = http_json(f"{INE_API}/OPERACIONES_DISPONIBLES", timeout=60)
    words = _fold(args.texto).split()
    rows = [{"codigo": o.get("Codigo"), "id": o.get("Id"), "nombre": o.get("Nombre"),
             "url": "https://www.ine.es" + o["Url"] if o.get("Url") else None}
            for o in data if all(w in _fold(o.get("Nombre", "")) for w in words)]
    emit({"operaciones": rows[: args.limite],
          "siguiente_paso": "python3 bulonator.py ine --tablas <codigo> [texto]  y luego  --datos <id_tabla> --nult 5"})
    return 0


# ---------------------------------------------------------------------------
# Búsqueda inversa y verificaciones previas
# ---------------------------------------------------------------------------


def cmd_buscar_imagen(args) -> int:
    u = urllib.parse.quote(args.url, safe="")
    res: dict = {"imagen": args.url, "enlaces_manual": {
        "google_lens": f"https://lens.google.com/uploadbyurl?url={u}",
        "bing": f"https://www.bing.com/images/search?view=detailv2&iss=sbi&form=SBIVSP&sbisrc=UrlPaste&q=imgurl:{u}",
        "yandex": f"https://yandex.com/images/search?rpt=imageview&url={u}",
        "tineye": f"https://tineye.com/search?url={u}",
    }, "nota": "Estos buscadores requieren navegador. Ábrelos con un navegador MCP si está disponible o "
               "entrégalos al usuario. TinEye permite ordenar por fecha ('oldest') para encontrar la primera aparición."}
    key = os.environ.get("SERPAPI_API_KEY")
    if key:
        try:
            q = urllib.parse.urlencode({"engine": "google_lens", "url": args.url, "api_key": key, "hl": "es"})
            data = http_json(f"https://serpapi.com/search.json?{q}", timeout=90)
            res["coincidencias_google_lens"] = [
                {"titulo": m.get("title"), "url": m.get("link"), "fuente": m.get("source"), "fecha": m.get("date")}
                for m in (data.get("visual_matches") or [])[: args.limite]]
        except (HttpError, ValueError) as e:
            res["serpapi_error"] = str(e)
    else:
        res["api"] = "Define SERPAPI_API_KEY para obtener coincidencias de Google Lens automáticamente."
    emit(res)
    return 0


def cmd_factcheck(args) -> int:
    q = urllib.parse.quote(args.texto)
    res: dict = {"consulta": args.texto, "enlaces_manual": {
        "google_fact_check_explorer": f"https://toolbox.google.com/factcheck/explorer/search/{q};hl={args.idioma}",
    }}
    key = os.environ.get("GOOGLE_FACTCHECK_API_KEY")
    if key:
        try:
            params = urllib.parse.urlencode({"query": args.texto, "languageCode": args.idioma, "pageSize": args.limite,
                                             "key": key})
            data = http_json(f"https://factchecktools.googleapis.com/v1alpha1/claims:search?{params}")
            res["verificaciones"] = [
                {"afirmacion": c.get("text"), "quien": c.get("claimant"), "fecha": c.get("claimDate"),
                 "revisiones": [{"verificador": (r.get("publisher") or {}).get("name"), "url": r.get("url"),
                                 "titulo": r.get("title"), "calificacion": r.get("textualRating"),
                                 "fecha": r.get("reviewDate")} for r in c.get("claimReview", [])]}
                for c in data.get("claims", [])]
        except (HttpError, ValueError) as e:
            res["api_error"] = str(e)
    else:
        res["api"] = "Define GOOGLE_FACTCHECK_API_KEY (gratuita en Google Cloud) para consultar ClaimReview. " \
                     "Mientras tanto usa WebSearch restringido a los dominios de verificadores (ver references/verificadores.md)."
    emit(res)
    return 0


# ---------------------------------------------------------------------------
# contar: longitud de los textos para redes
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://\S+|\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|es|org|net|gob\.es|eu|cat|gal|eus|info|io|me|ly)(?:/\S*)?",
                    re.I)
LIMITS = {"x": 280, "bluesky": 300, "threads": 500, "mastodon": 500}


def x_weight(text: str) -> int:
    """Longitud ponderada según las reglas de X: cada URL cuenta 23, emojis y CJK cuentan 2."""
    total = 0
    pos = 0
    for m in URL_RE.finditer(text):
        total += _x_chars(text[pos:m.start()]) + 23
        pos = m.end()
    return total + _x_chars(text[pos:])


def _x_chars(text: str) -> int:
    n = 0
    for ch in unicodedata.normalize("NFC", text):
        cp = ord(ch)
        if cp in (0x200D, 0xFE0F) or 0x1F3FB <= cp <= 0x1F3FF:
            continue  # unión de emojis, selector de variación, tono de piel
        light = (cp <= 0x10FF or 0x2000 <= cp <= 0x200D or 0x2010 <= cp <= 0x201F or 0x2032 <= cp <= 0x2037)
        n += 1 if light else 2
    return n


def cmd_contar(args) -> int:
    text = Path(args.archivo).read_text(encoding="utf-8") if args.archivo else sys.stdin.read()
    blocks = re.findall(r"```(?:text|txt|post)?\n(.*?)```", text, re.S) if args.bloques else [text]
    rows = []
    for i, b in enumerate(blocks, 1):
        b = b.strip("\n")
        w = x_weight(b)
        graphemes = len(unicodedata.normalize("NFC", b))
        rows.append({"bloque": i, "inicio": b[:60], "x_ponderado": w, "caracteres": graphemes,
                     "cabe_en": [k for k, lim in LIMITS.items() if (w if k == "x" else graphemes) <= lim]})
    emit({"limites": LIMITS, "bloques": rows,
          "nota": "X cuenta cada enlace como 23 caracteres y los emojis como 2. Bluesky, Threads y Mastodon "
                  "cuentan caracteres (aproximado)."})
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bulonator.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("deps", help="comprueba herramientas externas")
    s.set_defaults(func=cmd_deps)

    s = sub.add_parser("caso", help="crea la carpeta de un caso")
    s.add_argument("entrada", help="URL, ruta o texto (se usa para nombrar la carpeta)")
    s.add_argument("--base", default="bulonator-casos", help="carpeta base (por defecto ./bulonator-casos)")
    s.set_defaults(func=cmd_caso)

    s = sub.add_parser("capturar", help="captura una URL, archivo local o texto")
    s.add_argument("entrada")
    s.add_argument("--dir", required=True, help="carpeta del caso")
    s.add_argument("--sin-media", action="store_true", help="no descargar imágenes ni vídeos")
    s.add_argument("--max-media", type=int, default=8, help="máximo de imágenes de una página web")
    s.add_argument("--sin-archivo", action="store_true", help="no consultar la Wayback Machine")
    s.add_argument("--archivar", action="store_true", help="solicitar una copia nueva en la Wayback Machine")
    s.add_argument("--max-texto", type=int, default=6000, help="caracteres de texto a mostrar en la salida")
    s.add_argument("--nombre", help="nombre para una captura secundaria (p. ej. 'tuit-incrustado'): "
                                    "se guarda en <nombre>.json sin sobrescribir captura.json")
    s.set_defaults(func=cmd_capturar)

    s = sub.add_parser("media", help="analiza una imagen, vídeo o audio")
    s.add_argument("archivo")
    s.add_argument("--dir", help="carpeta de salida (por defecto <carpeta del archivo>/analisis/<nombre>)")
    s.add_argument("--fotogramas", type=int, default=12, help="número de fotogramas uniformes y de escena")
    s.add_argument("--idioma", help="idioma del audio para la transcripción (es, en, ca...)")
    s.set_defaults(func=cmd_media)

    s = sub.add_parser("wayback", help="consulta copias en la Wayback Machine")
    s.add_argument("url")
    s.add_argument("--guardar", action="store_true", help="solicitar una copia nueva")
    s.set_defaults(func=cmd_wayback)

    s = sub.add_parser("dominio", help="datos de registro de un dominio")
    s.add_argument("dominio", help="dominio o URL")
    s.set_defaults(func=cmd_dominio)

    s = sub.add_parser("boe", help="busca en el BOE")
    s.add_argument("texto", nargs="?", help="palabras del título (sintaxis Lucene: AND, OR, comillas)")
    s.add_argument("--desde", help="AAAAMMDD")
    s.add_argument("--hasta", help="AAAAMMDD")
    s.add_argument("--sumario", help="AAAAMMDD: lista las disposiciones publicadas ese día")
    s.add_argument("--limite", type=int, default=15)
    s.set_defaults(func=cmd_boe)

    s = sub.add_parser("ine", help="busca operaciones, tablas y datos del INE")
    s.add_argument("texto", nargs="?", help="palabras a buscar en el nombre")
    s.add_argument("--tablas", metavar="CODIGO_OPERACION", help="lista las tablas de una operación (p. ej. EPA, IPC)")
    s.add_argument("--datos", metavar="ID_TABLA", help="descarga los últimos datos de una tabla")
    s.add_argument("--nult", type=int, default=5, help="número de periodos más recientes")
    s.add_argument("--limite", type=int, default=25)
    s.set_defaults(func=cmd_ine)

    s = sub.add_parser("buscar-imagen", help="búsqueda inversa de imagen")
    s.add_argument("url", help="URL pública de la imagen")
    s.add_argument("--limite", type=int, default=15)
    s.set_defaults(func=cmd_buscar_imagen)

    s = sub.add_parser("contar", help="longitud de textos para redes (reglas de X)")
    s.add_argument("archivo", nargs="?", help="archivo de texto (por defecto, la entrada estándar)")
    s.add_argument("--bloques", action="store_true",
                   help="cuenta por separado cada bloque ```text ... ``` del archivo (p. ej. publicacion.md)")
    s.set_defaults(func=cmd_contar)

    s = sub.add_parser("factcheck", help="busca verificaciones previas")
    s.add_argument("texto")
    s.add_argument("--idioma", default="es")
    s.add_argument("--limite", type=int, default=10)
    s.set_defaults(func=cmd_factcheck)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except HttpError as e:
        emit({"error": str(e)})
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
