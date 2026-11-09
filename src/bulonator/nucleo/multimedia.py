"""Análisis forense básico de imágenes, vídeos y audios."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import zlib
from pathlib import Path

from .util import run, sha256_file, slugify, tail

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


def analizar_media(archivo, carpeta=None, fotogramas: int = 12, idioma: str | None = None) -> dict:
    """Metadatos, marcas de IA y C2PA, ELA, fotogramas, hoja de contactos, audio y transcripción.

    Escribe los resultados en ``carpeta`` (por defecto ``<carpeta del archivo>/analisis/<nombre>``)
    y devuelve el resumen, que también queda en ``analisis.json``.
    """
    path = Path(archivo).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"no existe {path}")
    outdir = Path(carpeta).expanduser().resolve() if carpeta else path.parent / "analisis" / slugify(path.stem, 40)
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
        res.update(analyze_audiovisual(path, outdir, probe, fotogramas, idioma))
    if kind == "documento":
        res["avisos"].append("Es un PDF: ábrelo con `leer` (o léelo y registra su texto) y revisa sus metadatos de autoría y fechas.")
    if shutil.which("c2patool"):
        rc, so, _ = run(["c2patool", str(path)], 60)
        if rc == 0 and so.strip():
            res["c2patool"] = so[:4000]
    res["busqueda_inversa"] = "Para buscar el origen de esta imagen sube el archivo a Google Lens, Bing, Yandex o TinEye, " \
                              "o usa 'buscar-imagen' con la URL original de la imagen."
    (outdir / "analisis.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res
