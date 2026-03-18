# Voice Clone Bot

Telegram-бот для клонирования голоса с помощью модели F5-TTS.

## Возможности

- Принимает голосовое сообщение (voice) или MP3-файл (от 15 секунд)
- Синтезирует речь по тексту с клонированным голосом
- Очередь генерации для обработки нескольких запросов
- Повторная генерация с тем же или новым голосом

## Стек

- **Python 3.11** + **aiogram 3** — Telegram Bot API
- **F5-TTS** — модель синтеза речи
- **RUAccent** — расстановка ударений для русского текста
- **pydub / librosa** — обработка аудио

## Быстрый старт

### 1. Подготовка модели F5-TTS

```bash
chmod +x setup_f5tts.sh
./setup_f5tts.sh
```

Скрипт скачает и распакует директорию `F5TTS/` с чекпоинтами модели.

### 2. Запуск через Docker

```bash
# Сборка образа
docker build -t voice-clone-bot .

# Запуск
docker run -d \
  --name voice-clone-bot \
  -e TELEGRAM_BOT_TOKEN=<ваш_токен> \
  voice-clone-bot
```

### 3. Запуск без Docker

```bash
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=<ваш_токен> python bot.py
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота от [@BotFather](https://t.me/BotFather) |

## Структура проекта

```
├── bot.py              # Основной код бота
├── requirements.txt    # Python-зависимости
├── setup_f5tts.sh      # Скрипт загрузки модели F5-TTS
├── Dockerfile          # Образ Docker
├── .dockerignore       # Исключения для Docker-сборки
└── F5TTS/              # Модель F5-TTS (не в git)
    └── ckpts/          # Чекпоинты модели
```
