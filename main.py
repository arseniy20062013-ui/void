import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# --- КОНФИГ ---
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
MY_ID = 7173827114

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Состояние системы
SYSTEM_STATE = {
    "is_active": True,
    "total_visits": 0,
    "current_repo": "None"
}
active_connections = set()

# Состояния для FSM (скачивание с GitHub)
class SetupStates(StatesGroup):
    waiting_for_url = State()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- ФУНКЦИЯ УСТАНОВКИ С GITHUB ---
def setup_github_project(url):
    try:
        repo_name = url.split('/')[-1].replace('.git', '')
        # Клонирование
        subprocess.run(f"git clone {url}", shell=True, check=True)
        # Установка зависимостей
        if os.path.exists(f"{repo_name}/requirements.txt"):
            subprocess.run(f"{sys.executable} -m pip install -r {repo_name}/requirements.txt", shell=True)
        SYSTEM_STATE["current_repo"] = repo_name
        return True
    except Exception as e:
        print(f"Ошибка установки: {e}")
        return False

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---
def get_main_kb():
    status = "🔴 ВЫКЛЮЧИТЬ САЙТ" if SYSTEM_STATE["is_active"] else "🟢 ВКЛЮЧИТЬ САЙТ"
    kb = [
        [types.KeyboardButton(text=status)],
        [types.KeyboardButton(text="📊 Статистика")],
        [types.KeyboardButton(text="📥 Скачать проект с GitHub")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(F.from_user.id == MY_ID, Command("start"))
async def start_cmd(m: types.Message):
    await m.answer("🕹 **VOID CORE**: Система управления запущена.", reply_markup=get_main_kb(), parse_mode="Markdown")

@dp.message(F.from_user.id == MY_ID, F.text.contains("САЙТ"))
async def toggle_site(m: types.Message):
    SYSTEM_STATE["is_active"] = not SYSTEM_STATE["is_active"]
    status = "ОНЛАЙН" if SYSTEM_STATE["is_active"] else "ОФФЛАЙН"
    await m.answer(f"🌐 Статус сайта изменен на: **{status}**", reply_markup=get_main_kb(), parse_mode="Markdown")

@dp.message(F.from_user.id == MY_ID, F.text == "📊 Статистика")
async def send_stats(m: types.Message):
    msg = (f"📈 **VOID STATS**\n\n"
           f"👥 Онлайн: `{len(active_connections)}` чел.\n"
           f"🚀 Всего визитов: `{SYSTEM_STATE['total_visits']}`\n"
           f"📦 Репозиторий: `{SYSTEM_STATE['current_repo']}`\n"
           f"🌐 Доступ: {'✅ Открыт' if SYSTEM_STATE['is_active'] else '❌ Закрыт'}")
    await m.answer(msg, parse_mode="Markdown")

@dp.message(F.from_user.id == MY_ID, F.text == "📥 Скачать проект с GitHub")
async def ask_repo(m: types.Message, state: FSMContext):
    await m.answer("🔗 Пришли ссылку на GitHub репозиторий (.git):")
    await state.set_state(SetupStates.waiting_for_url)

@dp.message(SetupStates.waiting_for_url)
async def process_repo(m: types.Message, state: FSMContext):
    url = m.text
    await m.answer("⏳ Начинаю клонирование и установку библиотек...")
    
    success = await asyncio.to_thread(setup_github_project, url)
    
    if success:
        await m.answer(f"✅ Проект `{SYSTEM_STATE['current_repo']}` успешно скачан и настроен!")
    else:
        await m.answer("❌ Ошибка при скачивании. Проверь ссылку или наличие Git.")
    await state.clear()

# --- API И WEBSOCKET ДЛЯ САЙТА ---
@app.websocket("/ws/void")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    SYSTEM_STATE["total_visits"] += 1
    try:
        while True:
            # Каждую секунду шлем инфо на сайт
            await websocket.send_text(json.dumps({
                "is_active": SYSTEM_STATE["is_active"],
                "online": len(active_connections),
                "time": datetime.now().strftime("%H:%M:%S")
            }))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# --- ЕДИНЫЙ ЗАПУСК ---
async def run_system():
    # Запуск сервера на порту 7066
    config = uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio")
    server = uvicorn.Server(config)
    
    print("💎 VOID CORE IS LIVE ON PORT 7066")
    # Запускаем бота и сервер одновременно
    await asyncio.gather(server.serve(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(run_system())
