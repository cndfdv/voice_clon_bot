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
NUM_WORKERS = int(os.getenv("NUM_WORKERS", "2"))

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
    keyboard=[[KeyboardButton(text="\U0001f399 \u0421\u043a\u043b\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0433\u043e\u043b\u043e\u0441")]], resize_keyboard=True
)

def kb_after_generation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="\U0001f504 \u0421 \u0442\u0435\u043c \u0436\u0435 \u0433\u043e\u043b\u043e\u0441\u043e\u043c", callback_data="repeat_same"),
                InlineKeyboardButton(text="\U0001f399 \u0421 \u0434\u0440\u0443\u0433\u0438\u043c \u0433\u043e\u043b\u043e\u0441\u043e\u043c", callback_data="repeat_new"),
            ]
        ]
    )

HELP_TEXT = (
    "<b>\U0001f4d6 \u041f\u043e\u043c\u043e\u0449\u044c \u043f\u043e \u0431\u043e\u0442\u0443</b>\n\n"
    "\u042d\u0442\u043e\u0442 \u0431\u043e\u0442 \u043f\u043e\u0437\u0432\u043e\u043b\u044f\u0435\u0442 \u043a\u043b\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0433\u043e\u043b\u043e\u0441 \u0438 \u043e\u0437\u0432\u0443\u0447\u0438\u0432\u0430\u0442\u044c \u0442\u0435\u043a\u0441\u0442.\n\n"
    "<b>\u0418\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f:</b>\n"
    "1. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 <b>\u00ab\U0001f399 \u0421\u043a\u043b\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0433\u043e\u043b\u043e\u0441\u00bb</b> \u0434\u043b\u044f \u0437\u0430\u043f\u0438\u0441\u0438 \u043d\u043e\u0432\u043e\u0433\u043e \u0433\u043e\u043b\u043e\u0441\u0430.\n"
    "2. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0433\u043e\u043b\u043e\u0441\u043e\u0432\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 (voice) \u0434\u043b\u0438\u043d\u043e\u0439 \u226512 \u0441\u0435\u043a\u0443\u043d\u0434 \u0438\u043b\u0438 mp3 \u0444\u0430\u0439\u043b.\n"
    "3. \u041f\u043e\u0441\u043b\u0435 \u044d\u0442\u043e\u0433\u043e \u043e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0442\u0435\u043a\u0441\u0442 \u0434\u043b\u044f \u0441\u0438\u043d\u0442\u0435\u0437\u0430.\n"
    "4. \u041f\u043e\u0441\u043b\u0435 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438 \u043f\u043e\u044f\u0432\u044f\u0442\u0441\u044f \u043a\u043d\u043e\u043f\u043a\u0438 \u0434\u043b\u044f \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e\u0433\u043e \u0441\u0438\u043d\u0442\u0435\u0437\u0430.\n"
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
    device="cuda",
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

async def generation_worker(bot: Bot, worker_id: int):
    while True:
        user_id, wav_path, text = await queue.get()
        try:
            logging.info("[worker-%s] Генерация для пользователя %s", worker_id, user_id)
            generated_path = await asyncio.to_thread(generate_audio, wav_path, text)
            await bot.send_document(
                chat_id=user_id,
                document=FSInputFile(generated_path),
                caption="\U0001f50a Сгенерировано аудио для текста:\n" + text,
            )
            Path(generated_path).unlink(missing_ok=True)
            Path(wav_path).unlink(missing_ok=True)
            await bot.send_message(
                chat_id=user_id,
                text="Выберите вариант для следующего синтеза:",
                reply_markup=kb_after_generation(),
            )
        except Exception as e:
            logging.exception("[worker-%s] Ошибка генерации", worker_id)
            await bot.send_message(user_id, "\u26a0\ufe0f Ошибка генерации: " + str(e))
        finally:
            queue.task_done()
            logging.info("[worker-%s] Готово. В очереди: %s", worker_id, queue.qsize())

@dp.message(Command(commands=("start", "help")))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я бот для клонирования голоса.\n\n" + HELP_TEXT, reply_markup=kb_main)

@dp.message(F.text == "\U0001f399 Склонировать голос")
async def start_clone_flow(message: types.Message, state: FSMContext):
    data = await state.get_data()
    old_voice = data.get("voice_path")
    if old_voice and Path(old_voice).exists():
        Path(old_voice).unlink()
    await state.clear()
    await state.set_state(CloneStates.waiting_voice)
    await message.answer("Отправьте голосовое сообщение (voice) \u226512 секунд или mp3 файл.")

@dp.message(StateFilter(CloneStates.waiting_voice), F.voice)
async def receive_voice(message: types.Message, state: FSMContext):
    voice = message.voice
    duration = getattr(voice, "duration", 0)
    if duration < 12:
        await message.answer("\u26a0\ufe0f Голосовое слишком короткое. Нужно \u226512 секунд.")
        return
    file_path = TMP_DIR / ("voice_" + str(message.from_user.id) + "_" + str(message.message_id) + ".ogg")
    file_info = await bot.get_file(voice.file_id)
    await bot.download_file(file_info.file_path, destination=file_path)
    await state.update_data(voice_path=str(file_path))
    await state.set_state(CloneStates.waiting_text)
    await message.answer(
        "\u2705 Голосовое получено. Теперь отправьте текст для синтеза.\n"
        "Все цифры и символы, например '<>*$%' \u2014 пишите словами для качественной генерации.",
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
        await message.answer("\u26a0\ufe0f Аудиофайл слишком короткий. Нужно \u226512 секунд.")
        return
    await state.update_data(voice_path=str(file_path))
    await state.set_state(CloneStates.waiting_text)
    await message.answer(
        "\u2705 Голосовое получено. Теперь отправьте текст для синтеза.\n"
        "Все цифры и символы, например '<>*$%' \u2014 пишите словами для качественной генерации.",
        parse_mode=None,
    )

@dp.message(StateFilter(CloneStates.waiting_text))
async def receive_text(message: types.Message, state: FSMContext):
    text = message.text
    await message.answer("\u2705 Текст получен. Добавляю в очередь на генерацию...")
    data = await state.get_data()
    voice_path = data.get("voice_path")
    if not voice_path or not Path(voice_path).exists():
        await message.answer("\u274c Голосовое не найдено. Сначала отправьте голосовое или mp3.")
        await state.set_state(CloneStates.waiting_voice)
        return
    if not voice_path.endswith(".wav"):
        wav_path = convert_to_wav(voice_path)
    else:
        wav_path = voice_path
    await queue.put((message.from_user.id, wav_path, text))
    queue_size = queue.qsize()
    if queue_size > 1:
        await message.answer("\U0001f553 Ваша генерация поставлена в очередь. Перед вами " + str(queue_size - 1) + " запрос(ов).")
    else:
        await message.answer("\u23f3 Идёт генерация аудио, подождите немного...")

@dp.callback_query(F.data == "repeat_same")
async def repeat_same(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    voice_path = data.get("voice_path")
    if voice_path and Path(voice_path).exists():
        await state.set_state(CloneStates.waiting_text)
        await call.message.answer("Используем существующий голос. Отправьте текст для синтеза.")
    else:
        await call.message.answer("\u274c Голосовое не найдено. Сначала отправьте новое.")
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
    await call.message.answer("Отправьте новое голосовое сообщение (voice) \u226512 секунд или mp3 файл.")
    await call.answer()

async def on_startup(bot: Bot):
    for i in range(NUM_WORKERS):
        asyncio.create_task(generation_worker(bot, i))
    logging.info("Запущено %s воркеров генерации", NUM_WORKERS)

if __name__ == "__main__":
    try:
        dp.startup.register(on_startup)
        asyncio.run(dp.start_polling(bot))
    finally:
        asyncio.run(bot.session.close())
