import os
import tempfile
import re
from typing import Optional, Set
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yt_dlp import YoutubeDL

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str
    lang: Optional[str] = None  # Si es None, usa auto-captions del idioma hablado

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # 1. Extraer metadata sin descargar vídeo
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()
        available_subs: Set[str] = set(info.get("subtitles", {}).keys())
        available_auto: Set[str] = set(info.get("automatic_captions", {}).keys())

    # 2. Determinar qué descargar y en qué idioma
    if req.lang:
        # Si el usuario pidió un lang específico, intentamos manual primero
        selected_lang = req.lang
        download_auto = selected_lang in available_auto
        download_manual = selected_lang in available_subs
    elif available_auto:
        # Default: usar auto-captions en idioma hablado
        selected_lang = next(iter(available_auto))
        download_auto = True
        download_manual = False
    elif available_subs:
        # Fallback: si no hay auto, usar manual
        selected_lang = next(iter(available_subs))
        download_auto = False
        download_manual = True
    else:
        raise HTTPException(
            status_code=404,
            detail="No hay subtítulos disponibles para este vídeo."
        )

    if not (download_auto or download_manual):
        raise HTTPException(
            status_code=404,
            detail=(
                f"No se encontraron subtítulos automáticos ni manuales "
                f"para el idioma '{selected_lang}'."
            )
        )

    # 3. Construir opciones para yt-dlp
    opts = {
        "skip_download": True,
        "convert_subtitles": "srt",
        "writeautomaticsub": download_auto,   # --write-auto-sub
        "writesubtitles": download_manual,    # --write-sub
        # Sólo restringir al idioma elegido:
        "subtitleslangs": [selected_lang],
        "outtmpl": os.path.join("%(title)s.%(ext)s"),
    }

    # 4. Descargar y procesar subtítulos
    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        with YoutubeDL(opts) as ydl:
            ydl.download([req.url])

        # Localizar el .srt o .vtt generado
        files = [f for f in os.listdir(tmpdir) if f.lower().endswith((".srt", ".vtt"))]
        if not files:
            raise HTTPException(
                status_code=500,
                detail="yt-dlp no generó ningún archivo de subtítulos."
            )
        subtitle_file = files[0]
        subtitle_path = os.path.join(tmpdir, subtitle_file)

        # Leer y limpiar contenido
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
            "title": title,
            "filename": subtitle_file,
            "used_lang": selected_lang,
            "content": content
        }
