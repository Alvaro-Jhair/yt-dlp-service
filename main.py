import os
import tempfile
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yt_dlp import YoutubeDL

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str
    lang: str = "es"

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # Obtener metadata para ver qué subtítulos existen y detectar idioma principal
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()
        available_subs = set(info.get("subtitles", {}).keys())
        available_auto = set(info.get("automatic_captions", {}).keys())
        video_lang = info.get("language")  # ISO 639-1 si está presente

    # Construir lista de idiomas a intentar, priorizando el idioma detectado del vídeo
    try_langs = []
    if video_lang:
        try_langs.append(video_lang)
    if req.lang not in try_langs:
        try_langs.append(req.lang)
    # Añadir fallbacks específicos si el usuario pidió "es" o "en"
    if req.lang == "es":
        for l in ["es-orig"]:
            if l not in try_langs:
                try_langs.append(l)
    elif req.lang == "en":
        for l in ["en-orig"]:
            if l not in try_langs:
                try_langs.append(l)

    # Intentar descargar subtítulos en cada idioma de la lista
    for lang in try_langs:
        write_auto = lang in available_auto
        write_manual = lang in available_subs

        if not write_auto and not write_manual:
            continue

        opts = {
            "skip_download": True,
            "writeautomaticsub": write_auto,
            "writesubtitles": write_manual,
            "subtitleslangs": [lang],
            "convert_subtitles": "srt",
            "outtmpl": "%(title)s.%(ext)s",
        }

        with tempfile.TemporaryDirectory() as tmp:
            opts["outtmpl"] = os.path.join(tmp, "%(title)s.%(ext)s")
            with YoutubeDL(opts) as ydl:
                ydl.download([req.url])

            subs_files = [f for f in os.listdir(tmp) if f.lower().endswith((".srt", ".vtt"))]
            if subs_files:
                subs_path = os.path.join(tmp, subs_files[0])
                try:
                    with open(subs_path, encoding="utf-8") as f:
                        raw = f.read()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error reading subtitle file: {e}")

                # Limpieza avanzada del contenido
                raw_cleaned = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", raw)
                raw_cleaned = re.sub(r"</?c>", "", raw_cleaned)
                raw_cleaned = re.sub(r"EBVTT.*?\n", "", raw_cleaned)
                raw_cleaned = re.sub(r"\[.*?\]", "", raw_cleaned)

                lines = raw_cleaned.splitlines()
                clean_lines = [
                    line.strip()
                    for line in lines
                    if line.strip()
                    and not re.match(r"^\d+$", line.strip())
                    and not re.match(r"^\d{2}:\d{2}:\d{2}", line)
                    and "-->" not in line
                ]
                clean_text = " ".join(clean_lines)

                return {
                    "title": title,
                    "filename": subs_files[0],
                    "used_lang": lang,
                    "content": clean_text
                }

    # Si no encontró nada, informar idiomas disponibles
    all_available = sorted(available_subs.union(available_auto))
    raise HTTPException(
        status_code=404,
        detail=f"No subtitles found for requested languages. Available: {', '.join(all_available) or 'none'}",
    )
