import os
import tempfile
import re
from typing import Optional, List, Set
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yt_dlp import YoutubeDL

app = FastAPI()

class DownloadSubsRequest(BaseModel):
    url: str
    lang: Optional[str] = None  # Si no se especifica, se detectará automáticamente

@app.post("/download_subs")
async def download_subs(req: DownloadSubsRequest):
    # Extraer metadata de subtítulos y posible idioma del vídeo
    with YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(req.url, download=False)
        title = info.get("title", "unknown").strip()
        available_subs: Set[str] = set(info.get("subtitles", {}).keys())
        available_auto: Set[str] = set(info.get("automatic_captions", {}).keys())
        video_lang: Optional[str] = info.get("language")  # ISO 639-1 si está presente

    all_avail = list(available_subs | available_auto)
    if not all_avail:
        raise HTTPException(
            status_code=404,
            detail="No hay subtítulos disponibles para este vídeo."
        )

    # Construir lista de idiomas a intentar
    try_langs: List[str] = []
    # 1. Si detectamos idioma del vídeo y hay subtítulos en ese idioma
    if video_lang and video_lang in all_avail:
        try_langs.append(video_lang)

    # 2. Si el usuario pidió un idioma específico
    if req.lang:
        if req.lang not in try_langs:
            try_langs.append(req.lang)
        # Añadir sus posibles variantes de origen
        if req.lang == "es" and "es-orig" in all_avail and "es-orig" not in try_langs:
            try_langs.append("es-orig")
        if req.lang == "en" and "en-orig" in all_avail and "en-orig" not in try_langs:
            try_langs.append("en-orig")

    # 3. Si no se especificó idioma o tras lo anterior no hay entradas
    #    y sólo hay un idioma disponible, usarlo
    if not try_langs and len(all_avail) == 1:
        try_langs.append(all_avail[0])

    # 4. Finalmente, incluir todos los demás disponibles como último recurso
    for lang in all_avail:
        if lang not in try_langs:
            try_langs.append(lang)

    # Intentar descargar en orden de prioridad
    for lang in try_langs:
        write_manual = lang in available_subs
        write_auto = lang in available_auto
        if not (write_manual or write_auto):
            continue

        opts = {
            "skip_download": True,
            "writesubtitles": write_manual,
            "writeautomaticsub": write_auto,
            "subtitleslangs": [lang],
            "convert_subtitles": "srt",
            "outtmpl": os.path.join("%(title)s.%(ext)s"),
        }

        with tempfile.TemporaryDirectory() as tmp:
            opts["outtmpl"] = os.path.join(tmp, "%(title)s.%(ext)s")
            with YoutubeDL(opts) as ydl:
                ydl.download([req.url])

            subs_files = [f for f in os.listdir(tmp) if f.lower().endswith((".srt", ".vtt"))]
            if not subs_files:
                continue

            subs_path = os.path.join(tmp, subs_files[0])
            try:
                with open(subs_path, encoding="utf-8") as f:
                    raw = f.read()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error al leer subtítulos: {e}")

            # Limpieza
            raw = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", raw)
            raw = re.sub(r"</?c>", "", raw)
            raw = re.sub(r"EBVTT.*?\n", "", raw)
            raw = re.sub(r"\[.*?\]", "", raw)

            lines = raw.splitlines()
            clean_lines = [
                ln.strip() for ln in lines
                if ln.strip()
                and not re.match(r"^\d+$", ln.strip())
                and "-->" not in ln
            ]
            clean_text = " ".join(clean_lines)

            return {
                "title": title,
                "filename": subs_files[0],
                "used_lang": lang,
                "content": clean_text
            }

    # Si no encontró nada, respondemos con los disponibles
    raise HTTPException(
        status_code=404,
        detail=f"No se pudieron descargar subtítulos. Idiomas disponibles: {', '.join(all_avail)}"
    )
