import os
import tempfile
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yt_dlp import YoutubeDL

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str  # sólo la URL, sin lang

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # 1. Extraer sólo el título
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()

    # 2. Opciones fijas: auto-sub en el idioma del vídeo, sin filtrar
    opts = {
        "skip_download": True,         # --skip-download
        "writeautomaticsub": True,     # --write-auto-sub
        "convert_subtitles": "srt",    # --convert-subs srt
        "outtmpl": "%(title)s.%(ext)s"
    }

    # 3. Descargar en un tempdir
    with tempfile.TemporaryDirectory() as tmpdir:
        opts["outtmpl"] = os.path.join(tmpdir, "%(title)s.%(ext)s")
        with YoutubeDL(opts) as ydl:
            ydl.download([req.url])

        # 4. Encuentra el .srt generado
        subs = [f for f in os.listdir(tmpdir) if f.lower().endswith(".srt")]
        if not subs:
            raise HTTPException(500, "No se generó ningún .srt.")
        subtitle_file = subs[0]

        # 5. Derivar el código de idioma si viene en el nombre (p.ej. "video.en.srt")
        parts = subtitle_file.rsplit(".", 2)
        used_lang = parts[1] if len(parts) == 3 else None

        path = os.path.join(tmpdir, subtitle_file)
        try:
            raw = open(path, encoding="utf-8").read()
        except Exception as e:
            raise HTTPException(500, f"Error al leer subtítulo: {e}")

        # 6. Limpieza básica del texto
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
            "used_lang": used_lang,
            "content": content
        }