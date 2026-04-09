#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
F5TTS_DIR="${SCRIPT_DIR}/F5TTS"
ARCHIVE="F5TTS.tar.gz"
GDRIVE_ID="1j1i_L4el5xDGOfkMSrJBX2UWlDcIrqu3"

if [ -d "$F5TTS_DIR" ] && [ -f "$F5TTS_DIR/ckpts/model_212000.safetensors" ]; then
    echo "F5TTS уже существует. Пропускаем загрузку."
    exit 0
fi

echo "Скачиваем F5TTS с Google Drive..."

PIP="${HOME}/miniforge3/bin/pip"
GDOWN="${HOME}/miniforge3/bin/gdown"

if [ ! -f "$GDOWN" ]; then
    echo "Устанавливаем gdown..."
    "$PIP" install --quiet gdown
fi

cd "$SCRIPT_DIR"
rm -f "$ARCHIVE"
"$GDOWN" "$GDRIVE_ID" -O "$ARCHIVE"

echo "Распаковываем F5TTS..."
tar -xzf "$ARCHIVE"
rm -f "$ARCHIVE"

echo "F5TTS готов."

