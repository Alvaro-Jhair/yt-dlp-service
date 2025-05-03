import os, tempfile, subprocess
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
            "--write-subs",
            "--sub-lang", req.lang,
            "-o", out,
            req.url
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=proc.stderr)
        subs = [f for f in os.listdir(tmp) if f.endswith((".vtt",".srt"))]
        if not subs:
            raise HTTPException(status_code=404, detail="No subtitles found")
        path = os.path.join(tmp, subs[0])
        with open(path, encoding="utf-8") as f:
            contenido = f.read()
    return {"filename": subs[0], "content": contenido}
