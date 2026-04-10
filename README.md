# Voice Clone Bot

Telegram-бот для клонирования голоса с помощью модели F5-TTS.

## Возможности

- Принимает голосовое сообщение (voice) или MP3-файл (от 12 секунд)
- Синтезирует речь по тексту с клонированным голосом
- Очередь генерации для обработки нескольких запросов
- Повторная генерация с тем же или новым голосом
- Поддержка SOCKS5-прокси для обхода блокировок Telegram

## Стек

- **Python 3.11** + **aiogram 3** — Telegram Bot API
- **F5-TTS** — модель синтеза речи (кастомный чекпоинт)
- **RUAccent** — расстановка ударений для русского текста
- **pydub / librosa** — обработка аудио
- **Docker** — контейнеризация

## Быстрый старт

### 1. Подготовка модели F5-TTS

```bash
chmod +x setup_f5tts.sh
./setup_f5tts.sh
```

Скрипт скачает и распакует `F5TTS/` с чекпоинтами модели с Google Drive.

### 2. Настройка `.env`

```bash
cp .env.example .env
# Отредактируйте .env — укажите токен бота
```

### 3. Сборка и запуск Docker

```bash
# Сборка образа (версионирование: clon_bot:1, clon_bot:2, ...)
docker build -t clon_bot:1 .

# Запуск
docker run -d \
  --name voice-clone-bot \
  --network host \
  --env-file .env \
  clon_bot:1
```

### 4. Запуск без Docker

```bash
pip install -r requirements.txt
export $(cat .env | xargs)
python bot.py
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `TG_BOT_TOKEN` | Да | Токен Telegram-бота от [@BotFather](https://t.me/BotFather) |
| `TG_PROXY` | Нет | SOCKS5-прокси для Telegram: `socks5://host:port` |
| `HTTP_PROXY` | Нет | Прокси для HTTP-запросов (HuggingFace и др.) |
| `HTTPS_PROXY` | Нет | Прокси для HTTPS-запросов |
| `HF_HUB_DISABLE_XET` | Нет | Поставить `1` при использовании SOCKS5-прокси |

## Настройка прокси (если Telegram заблокирован)

Если в вашей сети заблокирован доступ к Telegram и/или HuggingFace,
можно пробросить трафик через VPS по SSH.

### Шаг 1. Создайте SSH-ключ (если ещё нет)

```bash
ssh-keygen -t ed25519
ssh-copy-id root@<ваш_VPS_IP>
```

### Шаг 2. Поднимите SOCKS5-тоннель

Вручную:

```bash
ssh -N -D 127.0.0.1:1080 root@<ваш_VPS_IP>
```

Или через systemd-сервис (автозапуск):

```bash
sudo tee /etc/systemd/system/socks5_tunnel.service << 'EOF'
[Unit]
Description=SOCKS5 proxy tunnel to VPS
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<ваш_пользователь>
ExecStart=/usr/bin/ssh -N -D 127.0.0.1:1080 \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -o StrictHostKeyChecking=no \
    root@<ваш_VPS_IP>
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now socks5_tunnel.service
```

### Шаг 3. Настройте `.env`

```env
TG_BOT_TOKEN=<ваш_токен>
TG_PROXY=socks5://127.0.0.1:1080
HTTP_PROXY=socks5h://127.0.0.1:1080
HTTPS_PROXY=socks5h://127.0.0.1:1080
HF_HUB_DISABLE_XET=1
```

- `TG_PROXY` — прокси для aiogram (Telegram API)
- `HTTP_PROXY` / `HTTPS_PROXY` — прокси для скачивания моделей с HuggingFace
- `socks5h://` — DNS-резолв через прокси (важно при блокировке по DNS)
- `HF_HUB_DISABLE_XET=1` — отключает XetHub-протокол HuggingFace, который не поддерживает SOCKS5

### Шаг 4. Запустите контейнер с `--network host`

```bash
docker run -d \
  --name voice-clone-bot \
  --network host \
  --env-file .env \
  clon_bot:1
```

`--network host` нужен, чтобы контейнер видел SOCKS5-тоннель на `127.0.0.1:1080`.

## Управление версиями образа

```bash
# Первая версия
docker build -t clon_bot:1 .

# После обновлений — новая версия
docker build -t clon_bot:2 .

# Откат на старую версию
docker run -d --name voice-clone-bot --network host --env-file .env clon_bot:1
```

## Структура проекта

```
├── bot.py              # Основной код бота
├── requirements.txt    # Python-зависимости
├── setup_f5tts.sh      # Скрипт загрузки модели F5-TTS
├── Dockerfile          # Образ Docker
├── .dockerignore       # Исключения для Docker-сборки
├── .env.example        # Шаблон переменных окружения
└── F5TTS/              # Модель F5-TTS (не в git)
    └── ckpts/          # Чекпоинты модели
```
