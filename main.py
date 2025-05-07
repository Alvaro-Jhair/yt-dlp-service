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
        "outtmpl": "%(title)s.%(ext)s",  # se ajustará al tempdir
    }

    # directorio temporal para subtítulos
    with tempfile.TemporaryDirectory() as tmp:
        opts["outtmpl"] = os.path.join(tmp, "%(title)s.%(ext)s")

        # extraemos info y generamos subtítulos
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown")

        # buscamos archivos .srt o .vtt
        subs_files = [
            f for f in os.listdir(tmp)
            if f.lower().endswith((".srt", ".vtt"))
        ]
        if not subs_files:
            raise HTTPException(status_code=404, detail="No subtitles found")
        subs_filename = subs_files[0]
        subs_path = os.path.join(tmp, subs_filename)

        # leemos el raw
        try:
            with open(subs_path, encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading subtitle file: {e}")

    # limpiamos timestamps, números y cabecera WEBVTT
    lines = raw.splitlines()
    clean_lines = []
    for line in lines:
        text = line.strip()
        if (
            not text
            or text.isdigit()
            or "-->" in text
            or text.upper().startswith("WEBVTT")
        ):
            continue
        clean_lines.append(text)

    clean_text = " ".join(clean_lines)

    return {
        "title": title,
        "filename": subs_filename,
        "content": clean_text
    }
