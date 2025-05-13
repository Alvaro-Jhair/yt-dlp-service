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
    fallback_langs = [req.lang]
    if req.lang == "es":
        fallback_langs = ["es-orig", "es"]
    elif req.lang == "en":
        fallback_langs = ["en-orig", "en"]

    title = "unknown"

    for lang in fallback_langs:
        opts = {
            "skip_download": True,
            "writeautomaticsub": True,
            "subtitleslangs": [lang],
            "convert_subtitles": "srt",
            "outtmpl": "%(title)s.%(ext)s",
        }

        with tempfile.TemporaryDirectory() as tmp:
            opts["outtmpl"] = os.path.join(tmp, "%(title)s.%(ext)s")
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(req.url, download=False)
            title = info.get("title", "unknown").strip()

            subs_files = [f for f in os.listdir(tmp) if f.lower().endswith(".srt")]
            if subs_files:
                subs_path = os.path.join(tmp, subs_files[0])
                try:
                    with open(subs_path, encoding="utf-8") as f:
                        raw = f.read()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Error reading subtitle file: {e}")

                # Limpieza del SRT
                lines = raw.splitlines()
                clean_lines = [
                    line.strip()
                    for line in lines
                    if line.strip() and not line.strip().isdigit() and "-->" not in line
                ]
                clean_text = " ".join(clean_lines)

                return {
                    "title": title,
                    "filename": subs_files[0],
                    "used_lang": lang,
                    "content": clean_text
                }

    # No se encontraron subtítulos
    available = set(
        list(info.get("subtitles", {}).keys()) +
        list(info.get("automatic_captions", {}).keys())
    )
    raise HTTPException(
        status_code=404,
        detail=f"No subtitles found for '{req.lang}'. Available: {', '.join(sorted(available)) or 'none'}",
    )
