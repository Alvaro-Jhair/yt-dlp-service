import os
import re
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
            "--write-auto-sub",
            "--sub-lang", req.lang,
            "--convert-subs", "srt",
            "-o", out,
            req.url
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=proc.stderr)

        # buscamos el .srt generado
        subs_files = [f for f in os.listdir(tmp) if f.endswith(".srt")]
        if not subs_files:
            raise HTTPException(status_code=404, detail="No subtitles found")

        path = os.path.join(tmp, subs_files[0])
        with open(path, encoding="utf-8") as f:
            raw = f.read()

    # limpiamos el SRT: quitamos números de secuencia, timestamps y líneas vacías
    lines = raw.splitlines()
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # descartamos líneas que sólo son números o contienen flechas de timestamp
        if line.isdigit() or "-->" in line:
            continue
        clean_lines.append(line)

    # unimos todo en un solo párrafo (o usa "\n".join(...) si prefieres mantener saltos)
    clean_text = " ".join(clean_lines)

    return {
        "filename": subs_files[0],
        "content": clean_text
    }
