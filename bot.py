# bot.py
import logging
import os
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
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

BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_PROXY  = os.getenv("TG_PROXY", "")

TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)
GENERATE_DIR = Path("generate")
GENERATE_DIR.mkdir(exist_ok=True)

session = AiohttpSession(proxy=TG_PROXY) if TG_PROXY else None
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session,
)
dp = Dispatcher(storage=MemoryStorage())

class CloneStates(StatesGroup):
    waiting_voice = State()
    waiting_text = State()

kb_main = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🎙 Склонировать голос")]], resize_keyboard=True
)

def kb_after_generation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 С тем же голосом", callback_data="repeat_same"),
                InlineKeyboardButton(text="🎙 С другим голосом", callback_data="repeat_new"),
            ]
        ]
    )

HELP_TEXT = (
    "<b>📖 Помощь по боту</b>\n\n"
    "Этот бот позволяет клонировать голос и озвучивать текст.\n\n"
    "<b>Инструкция:</b>\n"
    "1. Нажмите <b>«🎙 Склонировать голос»</b> для записи нового голоса.\n"
    "2. Отправьте голосовое сообщение (voice) длиной ≥12 секунд или mp3 файл.\n"
    "3. После этого отправьте текст для синтеза.\n"
    "4. После генерации появятся кнопки для повторного синтеза.\n"
)

def get_audio_duration(file_path: str) -> float:
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000

def convert_to_wav(audio_path: str) -> str:
    audio = AudioSegment.from_file(audio_path)
    wav_path = audio_path[: audio_path.rindex(".")] + ".wav"
    audio.export(wav_path, format="wav")
    return wav_path

f5tts = F5TTS(
    ckpt_file="F5TTS/ckpts/model_v4.safetensors",
    vocab_file="F5TTS/ckpts/vocab.txt",
    device="cpu",
)
accentizer = RUAccent()
accentizer.load(omograph_model_size="turbo3.1", use_dictionary=True, tiny_mode=False)

def generate_audio(wav_path: str, text: str) -> str:
    wav_path = Path(wav_path)
    generated_audio_path = GENERATE_DIR / ("gen_" + wav_path.stem + ".wav")
    wav, sr, spec = f5tts.infer(
        ref_file=wav_path,
        ref_text="",
        gen_text=accentizer.process_all(text),
        file_wave=generated_audio_path,
        seed=None,
        remove_silence=True,
    )
    return generated_audio_path

queue = asyncio.Queue()

async def generation_worker(bot: Bot):
    while True:
        user_id, wav_path, text = await queue.get()
        try:
            logging.info("Начинаю генерацию для пользователя %s", user_id)
            generated_path = generate_audio(wav_path, text)
            await bot.send_document(
                chat_id=user_id,
                document=FSInputFile(generated_path),
                caption="🔊 Сгенерировано аудио для текста:\n" + text,
            )
            Path(generated_path).unlink(missing_ok=True)
            Path(wav_path).unlink(missing_ok=True)
            await bot.send_message(
                chat_id=user_id,
                text="Выберите вариант для следующего синтеза:",
                reply_markup=kb_after_generation(),
            )
        except Exception as e:
            logging.exception("Ошибка генерации")
            await bot.send_message(user_id, "⚠️ Ошибка генерации: " + str(e))
        finally:
            queue.task_done()
            logging.info("Генерация завершена для %s. В очереди: %s", user_id, queue.qsize())

@dp.message(Command(commands=("start", "help")))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот для клонирования голоса.\n\n" + HELP_TEXT, reply_markup=kb_main)

@dp.message(F.text == "🎙 Склонировать голос")
async def start_clone_flow(message: types.Message, state: FSMContext):
    data = await state.get_data()
    old_voice = data.get("voice_path")
    if old_voice and Path(old_voice).exists():
        Path(old_voice).unlink()
    await state.clear()
    await state.set_state(CloneStates.waiting_voice)
    await message.answer("Отправьте голосовое сообщение (voice) ≥12 секунд или mp3 файл.")

@dp.message(StateFilter(CloneStates.waiting_voice), F.voice)
async def receive_voice(message: types.Message, state: FSMContext):
    voice = message.voice
    duration = getattr(voice, "duration", 0)
    if duration < 12:
        await message.answer("⚠️ Голосовое слишком короткое. Нужно ≥12 секунд.")
        return
    file_path = TMP_DIR / ("voice_" + str(message.from_user.id) + "_" + str(message.message_id) + ".ogg")
    file_info = await bot.get_file(voice.file_id)
    await bot.download_file(file_info.file_path, destination=file_path)
    await state.update_data(voice_path=str(file_path))
    await state.set_state(CloneStates.waiting_text)
    await message.answer(
        "✅ Голосовое получено. Теперь отправьте текст для синтеза.\n"
        "Все цифры и символы, например '<>*$%' — пишите словами для качественной генерации.",
        parse_mode=None,
    )

@dp.message(StateFilter(CloneStates.waiting_voice), F.audio)
async def receive_audio(message: types.Message, state: FSMContext):
    audio = message.audio
    file_path = TMP_DIR / ("voice_" + str(message.from_user.id) + "_" + str(message.message_id) + ".mp3")
    file_info = await bot.get_file(audio.file_id)
    await bot.download_file(file_info.file_path, destination=file_path)
    duration = get_audio_duration(str(file_path))
    if duration < 12:
        file_path.unlink()
        await message.answer("⚠️ Аудиофайл слишком короткий. Нужно ≥12 секунд.")
        return
    await state.update_data(voice_path=str(file_path))
    await state.set_state(CloneStates.waiting_text)
    await message.answer(
        "✅ Голосовое получено. Теперь отправьте текст для синтеза.\n"
        "Все цифры и символы, например '<>*$%' — пишите словами для качественной генерации.",
        parse_mode=None,
    )

@dp.message(StateFilter(CloneStates.waiting_text))
async def receive_text(message: types.Message, state: FSMContext):
    text = message.text
    await message.answer("✅ Текст получен. Добавляю в очередь на генерацию...")
    data = await state.get_data()
    voice_path = data.get("voice_path")
    if not voice_path or not Path(voice_path).exists():
        await message.answer("❌ Голосовое не найдено. Сначала отправьте голосовое или mp3.")
        await state.set_state(CloneStates.waiting_voice)
        return
    if not voice_path.endswith(".wav"):
        wav_path = convert_to_wav(voice_path)
    else:
        wav_path = voice_path
    await queue.put((message.from_user.id, wav_path, text))
    queue_size = queue.qsize()
    if queue_size > 1:
        await message.answer("🕓 Ваша генерация поставлена в очередь. Перед вами " + str(queue_size - 1) + " запрос(ов).")
    else:
        await message.answer("⏳ Идёт генерация аудио, подождите немного...")

@dp.callback_query(F.data == "repeat_same")
async def repeat_same(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    voice_path = data.get("voice_path")
    if voice_path and Path(voice_path).exists():
        await state.set_state(CloneStates.waiting_text)
        await call.message.answer("Используем существующий голос. Отправьте текст для синтеза.")
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
    await state.update_data(voice_path=None)
    await state.set_state(CloneStates.waiting_voice)
    await call.message.answer("Отправьте новое голосовое сообщение (voice) ≥12 секунд или mp3 файл.")
    await call.answer()

async def on_startup(bot: Bot):
    asyncio.create_task(generation_worker(bot))
    logging.info("Воркер генерации запущен")

if __name__ == "__main__":
    try:
        dp.startup.register(on_startup)
        asyncio.run(dp.start_polling(bot))
    finally:
        asyncio.run(bot.session.close())
