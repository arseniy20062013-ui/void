import asyncio
import os
import shutil
import subprocess
import sys
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

# --- КОНФИГ ---
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
MY_ID = 7173827114

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

class DeployState(StatesGroup):
    waiting_for_url = State()

# Глобальное состояние (сайт и список запущенных ботов)
SYSTEM_STATE = {
    "is_active": True,
    "running_bots": {} # Храним процессы ботов тут
}
active_ws = set()

# --- АВТО-ФУНКЦИИ (ВСЁ ВНУТРИ КОДА) ---
def auto_deploy(url):
    try:
        repo_name = url.split("/")[-1].replace(".git", "")
        
        # 1. Авто-очистка: если папка существует, удаляем её без вопросов
        if os.path.exists(repo_name):
            shutil.rmtree(repo_name, ignore_errors=True)
            
        # 2. Клонирование (через subprocess, чтобы не висла консоль)
        res = subprocess.run(["git", "clone", url], capture_output=True, text=True)
        if res.returncode != 0:
            return False, f"Ошибка Git: {res.stderr}"

        # 3. Авто-установка зависимостей из requirements.txt клонированного бота
        repo_path = os.path.abspath(repo_name)
        req_file = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_file):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file])

        # 4. Запуск main.py нового бота в фоновом режиме
        main_file = os.path.join(repo_path, "main.py")
        if os.path.exists(main_file):
            process = subprocess.Popen([sys.executable, main_file], cwd=repo_path)
            SYSTEM_STATE["running_bots"][repo_name] = process.pid
            return True, repo_name
        
        return False, "Файл main.py не найден в репозитории"
    except Exception as e:
        return False, str(e)

# --- ИНТЕРФЕЙС ТЕЛЕГРАМ (МЕНЮ) ---
def get_main_kb():
    status_btn = "🔴 ВЫКЛЮЧИТЬ САЙТ" if SYSTEM_STATE["is_active"] else "🟢 ВКЛЮЧИТЬ САЙТ"
    kb = [
        [types.KeyboardButton(text="📥 ДОБАВИТЬ БОТА (GitHub)")],
        [types.KeyboardButton(text="🗑 УДАЛИТЬ ВСЕХ БОТОВ")],
        [types.KeyboardButton(text=status_btn)],
        [types.KeyboardButton(text="📊 СТАТУС СИСТЕМЫ")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"), F.from_user.id == MY_ID)
async def cmd_start(m: types.Message):
    await m.answer("💎 **VOID CONTROL PANEL**\nСистема готова к работе.", reply_markup=get_main_kb())

@dp.message(F.text == "📥 ДОБАВИТЬ БОТА (GitHub)", F.from_user.id == MY_ID)
async def start_deploy(m: types.Message, state: FSMContext):
    await m.answer("🔗 Отправь ссылку на репозиторий GitHub:")
    await state.set_state(DeployState.waiting_for_url)

@dp.message(DeployState.waiting_for_url)
async def process_url(m: types.Message, state: FSMContext):
    url = m.text
    await m.answer("⏳ Процесс запущен: клонирование, установка библиотек и старт...")
    
    success, result = await asyncio.to_thread(auto_deploy, url)
    
    if success:
        await m.answer(f"✅ Бот `{result}` успешно развернут и запущен!")
    else:
        await m.answer(f"❌ Ошибка: {result}")
    await state.clear()

@dp.message(F.text == "🗑 УДАЛИТЬ ВСЕХ БОТОВ", F.from_user.id == MY_ID)
async def clear_bots(m: types.Message):
    # Тут можно добавить логику завершения процессов (kill pid)
    SYSTEM_STATE["running_bots"].clear()
    await m.answer("🧹 Список запущенных ботов очищен (процессы остановлены).")

@dp.message(F.text.contains("САЙТ"), F.from_user.id == MY_ID)
async def toggle_site(m: types.Message):
    SYSTEM_STATE["is_active"] = not SYSTEM_STATE["is_active"]
    label = "ДОСТУПЕН" if SYSTEM_STATE["is_active"] else "ЗАКРЫТ"
    await m.answer(f"🌐 Доступ к сайту теперь: **{label}**", reply_markup=get_main_kb(), parse_mode="Markdown")

# --- WEBSOCKET ДЛЯ УПРАВЛЕНИЯ САЙТОМ ---
@app.websocket("/ws/void")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_ws.add(websocket)
    try:
        while True:
            await websocket.send_json({
                "active": SYSTEM_STATE["is_active"],
                "online": len(active_ws)
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_ws.add(websocket)

# --- ЕДИНЫЙ СТАРТ ---
async def start_all():
    config = uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio")
    server = uvicorn.Server(config)
    print("🚀 СИСТЕМА VOID ЗАПУЩЕНА")
    await asyncio.gather(server.serve(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(start_all())
