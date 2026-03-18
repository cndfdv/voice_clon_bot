FROM python:3.11-slim

# Системные зависимости (ffmpeg для pydub)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код бота
COPY bot.py .

# Директории для временных и сгенерированных файлов
RUN mkdir -p tmp generate

# F5TTS копируется отдельно (большой размер)
# Убедитесь, что директория F5TTS/ с чекпоинтами существует перед сборкой
COPY F5TTS/ F5TTS/

ENV TELEGRAM_BOT_TOKEN=""

CMD ["python", "bot.py"]
