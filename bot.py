# bot.py
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from pydub import AudioSegment
from ruaccent import RUAccent

from F5TTS.f5_tts.api import F5TTS

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", "8248132968:AAFl22P5TJhBH_4XdEzMJ2EXXQmaxzN2epA"
)
TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)

# ---------- Бот и Dispatcher ----------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ---------- FSM ----------
class CloneStates(StatesGroup):
    waiting_voice = State()
    waiting_text = State()


# ---------- Клавиатура ----------
kb_main = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🎙 Склонировать голос")]], resize_keyboard=True
)


def kb_after_generation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 С тем же голосом", callback_data="repeat_same"
                ),
                InlineKeyboardButton(
                    text="🎙 С другим голосом", callback_data="repeat_new"
                ),
            ]
        ]
    )


HELP_TEXT = """
<b>📖 Помощь по боту</b>

Этот бот позволяет клонировать голос и озвучивать текст.

<b>Инструкция:</b>
1. Нажмите <b>«🎙 Склонировать голос»</b> для записи нового голоса.
2. Отправьте голосовое сообщение (voice) длиной ≥15 секунд или mp3 файл.
3. После этого отправьте текст для синтеза.
4. После генерации появятся кнопки для повторного синтеза.
"""


# ---------- Вспомогательная функция ----------
def get_audio_duration(file_path: str) -> float:
    """Возвращает длительность аудио в секундах"""
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000


def convert_to_wav(audio_path: str) -> str:
    """convert audio to wav

    Args:
        audio_path (str): path to audio w ogg or mp3 format

    Returns:
        str: path to wav
    """
    audio = AudioSegment.from_file(audio_path)

    wav_path = audio_path[: audio_path.rindex(".")] + ".wav"
    audio.export(wav_path, format="wav")
    return wav_path


f5tts = F5TTS(
    ckpt_file="F5TTS/ckpts/model_last_inference.safetensors",
    vocab_file="F5TTS/ckpts/vocab.txt",
    device="cuda",
)
accentizer = RUAccent()
accentizer.load(omograph_model_size="turbo3.1", use_dictionary=True, tiny_mode=False)


def generate_audio(wav_path: str, text: str) -> str:
    """Generate audio

    Args:
        wav_path (str): path to audio
        text (str): text to clone

    Returns:
        str: path to generated audio
    """
    wav_path = Path(wav_path)
    out_dir = Path("generate")
    out_dir.mkdir(exist_ok=True)

    generated_audio_path = out_dir / f"gen_{wav_path.stem}.wav"

    wav, sr, spec = f5tts.infer(
        ref_file=wav_path,
        ref_text="",
        gen_text=accentizer.process_all(text),
        file_wave=generated_audio_path,
        seed=None,
        remove_silence=True,
    )
    return generated_audio_path


# ---------- Старт / Help ----------
@dp.message(Command(commands=("start", "help")))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для клонирования голоса.\n\n" + HELP_TEXT, reply_markup=kb_main
    )


# ---------- Кнопка Склонировать голос ----------
@dp.message(F.text == "🎙 Склонировать голос")
async def start_clone_flow(message: types.Message, state: FSMContext):
    # Удаляем старое голосовое, если есть
    data = await state.get_data()
    old_voice = data.get("voice_path")
    if old_voice and Path(old_voice).exists():
        Path(old_voice).unlink()
    await state.clear()
    await state.set_state(CloneStates.waiting_voice)
    await message.answer(
        "Отправьте голосовое сообщение (voice) ≥15 секунд или mp3 файл."
    )


# ---------- Обработка голосового ----------
@dp.message(StateFilter(CloneStates.waiting_voice), F.voice)
async def receive_voice(message: types.Message, state: FSMContext):
    voice = message.voice
    duration = getattr(voice, "duration", 0)
    if duration < 15:
        await message.answer("⚠️ Голосовое слишком короткое. Нужно ≥15 секунд.")
        return

    file_path = TMP_DIR / f"voice_{message.from_user.id}_{message.message_id}.ogg"
    file_info = await bot.get_file(voice.file_id)
    await bot.download_file(file_info.file_path, destination=file_path)

    await state.update_data(voice_path=str(file_path))
    await state.set_state(CloneStates.waiting_text)
    await message.answer("✅ Голосовое получено. Теперь отправьте текст для синтеза.")


# ---------- Обработка mp3 ----------
@dp.message(StateFilter(CloneStates.waiting_voice), F.audio)
async def receive_audio(message: types.Message, state: FSMContext):
    audio = message.audio
    file_path = TMP_DIR / f"voice_{message.from_user.id}_{message.message_id}.mp3"
    file_info = await bot.get_file(audio.file_id)
    await bot.download_file(file_info.file_path, destination=file_path)

    duration = get_audio_duration(file_path)
    if duration < 15:
        file_path.unlink()
        await message.answer("⚠️ Аудиофайл слишком короткий. Нужно ≥15 секунд.")
        return

    await state.update_data(voice_path=str(file_path))
    await state.set_state(CloneStates.waiting_text)
    await message.answer("✅ Аудиофайл получен. Теперь отправьте текст для синтеза.")


# ---------- Обработка текста ----------
@dp.message(StateFilter(CloneStates.waiting_text))
async def receive_text(message: types.Message, state: FSMContext):
    text = message.text
    await message.answer(
        "✅ Текст получен. Начинаю генерацию аудио. Это займет некоторое время"
    )
    data = await state.get_data()
    voice_path = data.get("voice_path")

    if not voice_path or not Path(voice_path).exists():
        await message.answer(
            "❌ Голосовое не найдено. Сначала отправьте голосовое или mp3."
        )
        await state.set_state(CloneStates.waiting_voice)
        return

    # --- Конвертация в wav, если нужно ---
    if not voice_path.endswith(".wav"):
        wav_path = convert_to_wav(voice_path)
    else:
        wav_path = voice_path

    # --- Генерация ---
    try:
        generated_path = generate_audio(wav_path, text)

        await message.answer_document(
            FSInputFile(generated_path),
            caption=f"🔊 Сгенерировано аудио для текста:\n{text}",
        )
        os.remove(generated_path)
    except Exception as e:
        logging.exception("Ошибка генерации")
        await message.answer(f"⚠️ Ошибка генерации: {e}")
        return

    # --- Клавиатура после генерации ---
    await message.answer(
        "Выберите вариант для следующего синтеза:",
        reply_markup=kb_after_generation(),
    )


# ---------- Callback для кнопок повторить ----------
@dp.callback_query(F.data == "repeat_same")
async def repeat_same(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    voice_path = data.get("voice_path")
    if voice_path and Path(voice_path).exists():
        await state.set_state(CloneStates.waiting_text)
        await call.message.answer(
            "Используем существующий голос. Отправьте текст для синтеза."
        )
    else:
        await call.message.answer("❌ Голосовое не найдено. Сначала отправьте новое.")
        await state.set_state(CloneStates.waiting_voice)
    await call.answer()


@dp.callback_query(F.data == "repeat_new")
async def repeat_new(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    old_voice = data.get("voice_path")
    if old_voice and Path(old_voice).exists():
        Path(old_voice).unlink()

    # очищаем только voice_path, но FSM оставляем в состоянии waiting_voice
    await state.update_data(voice_path=None)
    await state.set_state(CloneStates.waiting_voice)
    await call.message.answer(
        "Отправьте новое голосовое сообщение (voice) ≥15 секунд или mp3 файл."
    )
    await call.answer()


# ---------- Запуск ----------
if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(dp.start_polling(bot))
    finally:
        asyncio.run(bot.session.close())
