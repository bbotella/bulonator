"""Captura de publicaciones y páginas: redes sociales, vídeo y web."""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .archivo_web import wayback_info, wayback_save
from .extraccion import extract_page
from .caso import RegistroPaginas
from .red import (comprobar_destino, decode_body, download, guess_ext, host_of, http_get, http_json,
                  registered_domain)
from .util import VERSION, HttpError, now_iso, run, sha256_file, slugify, tail, texto_plano

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


def capturar(entrada: str, carpeta, sin_media: bool = False, max_media: int = 8, sin_archivo: bool = False,
             archivar: bool = False, nombre: str | None = None) -> dict:
    """Captura una URL, un archivo local o un texto en la carpeta de un caso.

    Guarda ``<nombre>.json`` (por defecto ``captura.json``), las respuestas brutas en
    ``captura_raw/<nombre>/`` y la multimedia en ``media/``. El texto capturado se registra en
    ``evidencias/paginas/`` para que las evidencias ``E-C-…`` se puedan validar.
    """
    entrada = entrada.strip()
    case = Path(carpeta).expanduser().resolve()
    name = slugify(nombre, 40) if nombre else "captura"
    media_dir, raw_dir = case / "media", case / "captura_raw" / name
    media_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out: dict = {"entrada": entrada, "capturado_en": now_iso(), "herramienta": f"bulonator {VERSION}",
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
        out_file = case / f"{name}.json"
        out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        if out.get("texto"):
            RegistroPaginas(case).registrar(f"captura://{name}", out["texto"], "captura", titulo="Texto aportado")
        return dict(out, archivo_captura=str(out_file))

    url = entrada
    comprobar_destino(url)
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
        ok = capture_ytdlp(url, out, raw_dir, media_dir, not sin_media)
        if not ok:
            plat = "web"
    if plat == "web" or (plat in {"instagram", "facebook", "tiktok"} and not out.get("texto")):
        try:
            pending += capture_web(url, out, raw_dir, media_dir, not sin_media, max_media)
        except HttpError as e:
            out["avisos"].append(f"No se pudo descargar la página: {e}")

    # Descarga de multimedia pendiente
    for i, item in enumerate(pending, 1):
        entry = dict(item)
        if sin_media or not item.get("url"):
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

    if not sin_archivo:
        out["archivo_web"] = wayback_info(url)
        if archivar:
            out["archivo_web"]["nueva_copia"] = wayback_save(url)
    if not out.get("texto") and not out.get("titulo") and not any(m.get("archivo") for m in out["media"]):
        out["avisos"].append("CAPTURA VACÍA: no se obtuvo contenido. No se debe emitir veredicto sin el contenido.")
    out_file = case / f"{name}.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    RegistroPaginas(case).registrar(url, texto_de_captura(out), "captura", titulo=out.get("titulo"),
                                    url_final=out.get("url_final"))
    return dict(out, archivo_captura=str(out_file))


def resumen_captura(captura: dict, max_texto: int = 6000) -> dict:
    """Versión recortada de una captura para mostrarla (el JSON completo queda en el caso)."""
    summary = dict(captura)
    out_file = captura.get("archivo_captura", "captura.json")
    if summary.get("texto") and len(summary["texto"]) > max_texto:
        summary["texto"] = summary["texto"][:max_texto] + f"… [recortado; texto completo en {out_file}]"
    summary.pop("meta", None)
    if len(summary.get("enlaces_salientes", [])) > 15:
        summary["enlaces_salientes"] = summary["enlaces_salientes"][:15] + [{"nota": "más enlaces en captura.json"}]
    return summary


_SIN_REGISTRO = {"avisos", "metodo", "http", "meta", "capturado_en", "herramienta", "archivo_web"}


def texto_de_captura(captura: dict) -> str:
    """Texto plano de una captura (``clave: valor``), que es lo que citan las evidencias ``E-C-…``."""
    resto = texto_plano({k: v for k, v in captura.items() if k != "texto"}, _SIN_REGISTRO)
    return "\n".join(x for x in (str(captura.get("texto") or ""), resto) if x)
