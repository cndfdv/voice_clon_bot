FROM python:3.11-slim

RUN apt-get update &&     apt-get install -y --no-install-recommends ffmpeg libsndfile1 &&     rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN mkdir -p tmp generate

COPY F5TTS/ F5TTS/

ENV TG_BOT_TOKEN=""
ENV TG_PROXY=""

CMD ["python", "bot.py"]
