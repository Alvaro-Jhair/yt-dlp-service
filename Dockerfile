# ./yt-dlp-service/Dockerfile

FROM python:3.11-alpine

# Git es necesario para pip instalar desde el repo
RUN apk add --no-cache git ffmpeg

# Instalamos FastAPI, Uvicorn y el propio yt-dlp desde GitHub
RUN pip install \
    fastapi uvicorn \
    "git+https://github.com/yt-dlp/yt-dlp.git@master#egg=yt-dlp"

WORKDIR /app
COPY main.py .

# Exponemos el endpoint en el puerto 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
