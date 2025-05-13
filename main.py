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
    # Opciones para yt_dlp: escribimos auto-sub, forzamos conversión a SRT
    opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "subtitleslangs": [req.lang],
        "convert_subtitles": "srt",            # << clave para convertir vtt→srt
        "outtmpl": "%(title)s.%(ext)s",        # aquí sólo template, lo cambiamos dentro de tmpdir
    }

    # Directorio temporal
    with tempfile.TemporaryDirectory() as tmp:
        opts["outtmpl"] = os.path.join(tmp, "%(title)s.%(ext)s")

        # Descargamos sólo subtítulos y extraemos metadata
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()

        # Ahora buscamos sólo archivos .srt (ya convertidos)
        subs_files = [f for f in os.listdir(tmp) if f.lower().endswith(".srt")]
        if not subs_files:
            # Si no hay SRT, listamos idiomas disponibles para que el usuario lo sepa
            available = set(
                list(info.get("subtitles", {}).keys()) +
                list(info.get("automatic_captions", {}).keys())
            )
            raise HTTPException(
                status_code=404,
                detail=f"No subtitles found for '{req.lang}'. Available: {', '.join(sorted(available)) or 'none'}"
            )

        subs_filename = subs_files[0]
        subs_path = os.path.join(tmp, subs_filename)

        try:
            with open(subs_path, encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading subtitle file: {e}")

    # Limpiamos SRT: quitamos números, timestamps y líneas vacías
    lines = raw.splitlines()
    clean_lines = [
        line.strip() for line in lines
        if line.strip() and not line.strip().isdigit() and "-->" not in line
    ]
    clean_text = " ".join(clean_lines)

    return {
        "title": title,
        "filename": subs_filename,
        "content": clean_text
    }
