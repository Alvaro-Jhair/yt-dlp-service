import os
import tempfile
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yt_dlp import YoutubeDL

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str
    lang: str = "es"

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # Opciones para yt_dlp
    opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "subtitleslangs": [req.lang],
        "subtitlesformat": "srt",
        # el template se rellenará tras crear el tempdir
        "outtmpl": "%(title)s.%(ext)s",
    }

    # directorio temporal para descargar sólo los .srt
    with tempfile.TemporaryDirectory() as tmp:
        opts["outtmpl"] = os.path.join(tmp, "%(title)s.%(ext)s")

        # extraemos info y generamos los subtítulos
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown")

        # buscamos el .srt generado
        subs_files = [f for f in os.listdir(tmp) if f.lower().endswith(".srt")]
        if not subs_files:
            raise HTTPException(status_code=404, detail="No subtitles found")
        subs_filename = subs_files[0]
        subs_path = os.path.join(tmp, subs_filename)

        # leemos el SRT en bruto
        try:
            with open(subs_path, encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading subtitle file: {e}")

    # limpiamos el SRT: quitamos números de secuencia, timestamps y líneas vacías
    lines = raw.splitlines()
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        clean_lines.append(line)

    # unimos todo en un solo bloque de texto
    clean_text = " ".join(clean_lines)

    return {
        "title": title,
        "filename": subs_filename,
        "content": clean_text
    }
