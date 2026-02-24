import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from fastapi import FastAPI
import uvicorn

# Настройка логов (увидишь ошибки в консоли)
logging.basicConfig(level=logging.INFO)

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
MY_ID = 7173827114

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Состояние сайта
site_enabled = True

# --- КНОПКИ ---
def get_kb():
    label = "🔴 ВЫКЛЮЧИТЬ" if site_enabled else "🟢 ВКЛЮЧИТЬ"
    kb = [[types.KeyboardButton(text=label)]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ОБРАБОТЧИКИ БОТА ---
@dp.message(Command("start"), F.from_user.id == MY_ID)
async def cmd_start(m: types.Message):
    print(f"Пользователь {m.from_user.id} нажал старт")
    await m.answer("🕹 Пульт управления сайтом VOID активен.", reply_markup=get_kb())

@dp.message(F.from_user.id == MY_ID)
async def handle_all(m: types.Message):
    global site_enabled
    if "ВКЛЮЧИТЬ" in m.text or "ВЫКЛЮЧИТЬ" in m.text:
        site_enabled = not site_enabled
        status = "РАБОТАЕТ" if site_enabled else "ВЫКЛЮЧЕН"
        await m.answer(f"Сайт теперь {status}", reply_markup=get_kb())
    else:
        await m.answer("Используй кнопки меню.")

# --- ЗАПУСК ---
async def main():
    # Настройка сервера
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, loop="asyncio")
    server = uvicorn.Server(config)
    
    print("--- ЗАПУСК СИСТЕМЫ ---")
    # Запускаем бота и сервер параллельно без конфликтов
    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Критическая ошибка: {e}")
