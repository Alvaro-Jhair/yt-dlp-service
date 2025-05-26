import os
import tempfile
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yt_dlp import YoutubeDL
from langdetect import detect, DetectorFactory
from typing import Optional

# Aseguramos reproducibilidad en langdetect
DetectorFactory.seed = 0

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str                 # URL del vídeo
    idioma: Optional[str]    # Código ISO 639-1 del idioma deseado

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # 1. Extraer metadata (título y posible idioma del vídeo)
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()
        video_lang = info.get("language")

    # 1.1 Fallback: si no hay video_lang, lo detectamos sobre el título
    if not video_lang:
        try:
            video_lang = detect(title)
        except Exception:
            video_lang = None

    # 2. Opciones de descarga: sólo subtítulos automáticos en el idioma solicitado
    opts = {
        "skip_download": True,         # --skip-download
        "writeautomaticsub": True,     # --write-auto-sub
        # Filtramos por el idioma que vino en la petición
        # Si no vino, dejamos que baje cualquier auto-sub disponible
        **({"subtitleslangs": [req.idioma]} if req.idioma else {}),
        "outtmpl": "%(title)s.%(ext)s"
    }

    # 3. Descargar dentro de un tempdir
    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        with YoutubeDL(opts) as ydl:
            ydl.download([req.url])

        # 4. Buscar tanto .vtt como .srt en el directorio
        files = [
            f for f in os.listdir(tmpdir)
            if f.lower().endswith((".srt", ".vtt"))
        ]
        if not files:
            raise HTTPException(
                status_code=500,
                detail="No se generó ningún archivo de subtítulos (.srt ni .vtt)."
            )

        subtitle_file = files[0]
        subtitle_path = os.path.join(tmpdir, subtitle_file)

        # 5. Extraer el código de idioma del nombre del archivo (p.ej. "... .es.vtt")
        parts = subtitle_file.rsplit(".", 2)
        used_lang = parts[1] if len(parts) == 3 else None

        # 6. Leer y limpiar el contenido
        try:
            raw = open(subtitle_path, encoding="utf-8").read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al leer el archivo: {e}")

        clean = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", raw)
        clean = re.sub(r"</?c>", "", clean)
        clean = re.sub(r"EBVTT.*?\n", "", clean)
        clean = re.sub(r"\[.*?\]", "", clean)
        lines = clean.splitlines()
        filtered = [
            ln.strip() for ln in lines
            if ln.strip() and not re.match(r"^\d+$", ln.strip()) and "-->" not in ln
        ]
        content = " ".join(filtered)

        return {
            "title":       title,
            "filename":    subtitle_file,
            "requested":   req.idioma,
            "used_lang":   used_lang,
            "video_lang":  video_lang,
            "content":     content
        }
