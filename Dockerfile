FROM python:3.11-alpine

RUN apk add --no-cache ffmpeg         # opcional, para procesar audio/video
RUN pip install fastapi uvicorn yt-dlp

WORKDIR /app
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
