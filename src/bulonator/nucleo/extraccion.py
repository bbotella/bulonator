"""Extracción de texto, metadatos, multimedia y enlaces de páginas HTML."""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from .red import host_of, registered_domain

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
