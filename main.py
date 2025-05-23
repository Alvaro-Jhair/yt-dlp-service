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
    lang: Optional[str] = None  # Si se deja None, detecta el idioma automáticamente

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # 1. Extraer metadata sin descargar vídeo
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()
        available_subs: Set[str] = set(info.get("subtitles", {}).keys())
        available_auto: Set[str] = set(info.get("automatic_captions", {}).keys())

    # 2. Determinar idioma a usar: prioridad de auto-captions (idioma hablado), luego manual
    if req.lang:
        selected_lang = req.lang
    elif available_auto:
        # Primer idioma de captions automáticos refleja el idioma hablado
        selected_lang = next(iter(available_auto))
    elif available_subs:
        # Si no hay auto, usar primer subtítulo manual
        selected_lang = next(iter(available_subs))
    else:
        raise HTTPException(
            status_code=404,
            detail="No hay subtítulos disponibles para este vídeo."
        )

    write_auto = selected_lang in available_auto
    write_manual = selected_lang in available_subs
    if not (write_auto or write_manual):
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron subtítulos ni automáticos en '{selected_lang}'"
        )

    # 3. Descargar sólo el idioma seleccionado
    opts = {
        "skip_download": True,
        "writesubtitles": write_manual,
        "writeautomaticsub": write_auto,
        "subtitleslangs": [selected_lang],
        "convert_subtitles": "srt",
        # El template se ajustará al directorio temporal
        "outtmpl": os.path.join("%(title)s.%(ext)s"),
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        with YoutubeDL(opts) as ydl:
            ydl.download([req.url])

        # Buscar fichero de subtítulos
        files = [f for f in os.listdir(tmpdir) if f.lower().endswith((".srt", ".vtt"))]
        if not files:
            raise HTTPException(
                status_code=500,
                detail="El proceso de yt-dlp no generó ningún archivo de subtítulos."
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
