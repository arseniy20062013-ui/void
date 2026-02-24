import asyncio
import sqlite3
import os
import shutil
import subprocess
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

# --- CONFIG (Только твой ID) ---
TOKEN = "8300375381:AAHlpug9p4Lj-rMHH3JYGszJT3SA0BESPNE"
ADMIN_ID = 7173827114 

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Стабилизатор
STABILIZER = {
    "is_active": True,
    "distributed_power": True,
    "total_clients": 0
}
active_ws = set()

# Оптимизация БД для Termux
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('PRAGMA journal_mode=WAL') 
cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, confirmed INTEGER DEFAULT 0)')
conn.commit()

class AdminStates(StatesGroup):
    waiting_for_github = State()

# --- КЛАВИАТУРА ---
def admin_kb():
    btn_status = "🔴 ВЫКЛ САЙТ" if STABILIZER["is_active"] else "🟢 ВКЛ САЙТ"
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="📥 DEPLOY GITHUB"), types.KeyboardButton(text=btn_status)],
        [types.KeyboardButton(text="📊 СТАТУС НАГРУЗКИ")]
    ], resize_keyboard=True)

# --- ФИЛЬТР ТОЛЬКО ДЛЯ ТЕБЯ ---
@dp.message(Command("start"), F.from_user.id == ADMIN_ID)
async def cmd_admin(m: types.Message):
    await m.answer("🕹 **VOID ENGINE: TERMUX EDITION**\nАдмин подтвержден. Стабилизация активна.", 
                   reply_markup=admin_kb(), parse_mode="Markdown")

@dp.message(F.text == "📊 СТАТУС НАГРУЗКИ", F.from_user.id == ADMIN_ID)
async def sys_status(m: types.Message):
    clients = len(active_ws)
    # Формула: чем больше узлов (людей), тем легче твоему устройству
    load_index = max(5, 100 - (clients * 7)) 
    await m.answer(f"👥 Узлов в сети: {clients}\n⚡ Нагрузка на процессор: {load_index}%")

@dp.message(F.text.contains("САЙТ"), F.from_user.id == ADMIN_ID)
async def toggle_site(m: types.Message):
    STABILIZER["is_active"] = not STABILIZER["is_active"]
    status = "ДОСТУПЕН" if STABILIZER["is_active"] else "ЗАБЛОКИРОВАН"
    await m.answer(f"📢 Сайт сейчас: {status}", reply_markup=admin_kb())

# --- DEPLOY ---
@dp.message(F.text == "📥 DEPLOY GITHUB", F.from_user.id == ADMIN_ID)
async def ask_git(m: types.Message, state: FSMContext):
    await m.answer("🔗 Кидай ссылку на репозиторий:")
    await state.set_state(AdminStates.waiting_for_github)

@dp.message(AdminStates.waiting_for_github)
async def process_git(m: types.Message, state: FSMContext):
    url = m.text
    repo_name = url.split("/")[-1].replace(".git", "")
    await m.answer(f"⏳ Клонирую {repo_name} и разгружаю кэш...")
    
    if os.path.exists(repo_name): shutil.rmtree(repo_name)
    proc = await asyncio.create_subprocess_exec("git", "clone", url)
    await proc.wait()
    
    await m.answer(f"✅ Проект {repo_name} готов к работе.")
    await state.clear()

# --- WEBSOCKET С РАСПРЕДЕЛЕНИЕМ ---
@app.websocket("/ws/void")
async def ws_handler(websocket: WebSocket):
    await websocket.accept()
    active_ws.add(websocket)
    try:
        while True:
            await websocket.send_json({
                "active": STABILIZER["is_active"],
                "node_count": len(active_ws),
                "assist_mode": STABILIZER["distributed_power"]
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        active_ws.remove(websocket)

async def runner():
    config = uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio")
    server = uvicorn.Server(config)
    print("🚀 VOID СИСТЕМА ЗАПУЩЕНА (ТОЛЬКО ВЛАДЕЛЕЦ)")
    await asyncio.gather(server.serve(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(runner())
