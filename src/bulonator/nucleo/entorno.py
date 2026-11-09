"""Comprobación de las herramientas externas disponibles."""
from __future__ import annotations

import os
import shutil
import sys

from .busqueda import buscador_configurado
from .util import VERSION

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


def deps() -> dict:
    """Herramientas externas encontradas y capacidades que dependen de ellas."""
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
        "buscador": buscador_configurado(),
        "extraccion_pdf": _hay_pypdf(),
    }
    missing = [f"{n}: {d}" for n, d in TOOLS.items() if not found[n]]
    return {
        "python": sys.version.split()[0],
        "bulonator": VERSION,
        "herramientas": {n: (p or None) for n, p in found.items()},
        "capacidades": caps,
        "faltan": missing,
        "sugerencia_instalacion": "macOS: brew install yt-dlp ffmpeg exiftool | "
                                  "Linux: pipx install yt-dlp; apt install ffmpeg libimage-exiftool-perl | "
                                  "Transcripción: pipx install openai-whisper",
    }


def _hay_pypdf() -> bool:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True
