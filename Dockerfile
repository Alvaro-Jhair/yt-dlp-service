# ./yt-dlp-service/Dockerfile

FROM python:3.11-alpine

# Instalamos git, ffmpeg y deps para conversión
RUN apk add --no-cache \
      git \
      ffmpeg \
      build-base \
      libffi-dev \
      openssl-dev

WORKDIR /app

# Copiamos tu aplicación
COPY main.py .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Instalamos FastAPI, Uvicorn, yt-dlp y langdetect
RUN pip install --no-cache-dir \
      fastapi \
      uvicorn \
      yt-dlp \
      langdetect

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
