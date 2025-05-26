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

class TitleRequest(BaseModel):
    url: str  # URL del vídeo o noticia

class SubsRequest(BaseModel):
    url: str          # URL del vídeo
    idioma: str       # Código ISO 639-1 del idioma deseado

@app.post("/extract_title")
async def extract_title(req: TitleRequest):
    """
    Extrae el título y el posible idioma del vídeo sin descargar nada.
    """
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()
        video_lang = info.get("language")

    # Fallback: detectamos idioma del título si no viene en metadata
    if not video_lang:
        try:
            video_lang = detect(title)
        except Exception:
            video_lang = None

    return {"title": title, "video_lang": video_lang}

@app.post("/download_subs")
async def download_subs(req: SubsRequest):
    """
    Descarga sólo subtítulos automáticos en el idioma solicitado.
    """
    # Opciones de descarga: sólo subtítulos automáticos
    opts = {
        "skip_download": True,         # --skip-download
        "writeautomaticsub": True,     # --write-auto-sub
        "subtitleslangs": [req.idioma],# Filtrar por idioma
        "outtmpl": "%(_title_)s.%(ext)s"
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = os.path.join(tmpdir, "%(_title_)s.%(ext)s")
        with YoutubeDL(opts) as ydl:
            ydl.download([req.url])

        files = [f for f in os.listdir(tmpdir) if f.lower().endswith((".srt", ".vtt"))]
        if not files:
            raise HTTPException(
                status_code=404,
                detail="No se generó ningún archivo de subtítulos (.srt ni .vtt)."
            )

        subtitle_file = files[0]
        subtitle_path = os.path.join(tmpdir, subtitle_file)

        # Extraer el código de idioma del nombre de archivo
        parts = subtitle_file.rsplit(".", 2)
        used_lang = parts[1] if len(parts) == 3 else None

        try:
            raw = open(subtitle_path, encoding="utf-8").read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al leer el archivo: {e}")

        # Limpiar contenido
        clean = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", raw)
        clean = re.sub(r"</?c>", "", clean)
        clean = re.sub(r"EBVTT.*?\n", "", clean)
        clean = re.sub(r"\[.*?\]", "", clean)
        lines = clean.splitlines()
        filtered = [ln.strip() for ln in lines if ln.strip() and not re.match(r"^\d+$", ln.strip()) and "-->" not in ln]
        content = " ".join(filtered)

        return {
            "filename": subtitle_file,
            "requested": req.idioma,
            "used_lang": used_lang,
            "content": content
        }
