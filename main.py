import os
import tempfile
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str
    lang: str = "es"

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "%(title)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",       # subtítulos automáticos
            "--sub-lang", req.lang,   # idioma (por defecto "es")
            "--convert-subs", "srt",  # convertir a SRT
            "-o", out,
            req.url
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=proc.stderr)

        # Buscar el .srt generado
        subs_files = [f for f in os.listdir(tmp) if f.endswith(".srt")]
        if not subs_files:
            raise HTTPException(status_code=404, detail="No subtitles found")

        path = os.path.join(tmp, subs_files[0])
        with open(path, encoding="utf-8") as f:
            content = f.read()

    return {
        "filename": subs_files[0],
        "content": content
    }
