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

# Copiamos tu aplicación actualizada
COPY main.py .

# Instalamos FastAPI, Uvicorn y yt-dlp
RUN pip install --no-cache-dir \
      fastapi \
      uvicorn \
      yt-dlp

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
