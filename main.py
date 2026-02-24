import asyncio
import os
import shutil
import subprocess
import sys
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

SYSTEM_STATE = {"is_active": True}
active_ws = set()

# --- ФУНКЦИЯ КЛОНИРОВАНИЯ (БЕЗ ОШИБОК) ---
def safe_deploy(url):
    try:
        repo_name = url.split("/")[-1].replace(".git", "")
        
        # Если папка есть — удаляем её полностью
        if os.path.exists(repo_name):
            shutil.rmtree(repo_name)
            
        # Клонируем
        result = subprocess.run(["git", "clone", url], capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"Git error: {result.stderr}"

        # Ставим зависимости
        req_path = os.path.join(repo_name, "requirements.txt")
        if os.path.exists(req_path):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path])
            
        return True, repo_name
    except Exception as e:
        return False, str(e)

# --- МЕНЮ БОТА ---
def get_kb():
    status_text = "🔴 ВЫКЛ САЙТ" if SYSTEM_STATE["is_active"] else "🟢 ВКЛ САЙТ"
    kb = [
        [types.KeyboardButton(text="📥 СКАЧАТЬ С GITHUB")],
        [types.KeyboardButton(text=status_text)],
        [types.KeyboardButton(text="📊 СТАТУС")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"), F.from_user.id == MY_ID)
async def start(m: types.Message):
    await m.answer("🕹 VOID CORE: Управление запущено", reply_markup=get_kb())

@dp.message(F.text == "📥 СКАЧАТЬ С GITHUB", F.from_user.id == MY_ID)
async def ask_url(m: types.Message, state: FSMContext):
    await m.answer("🔗 Пришли ссылку на .git репозиторий:")
    await state.set_state(DeployState.waiting_for_url)

@dp.message(DeployState.waiting_for_url)
async def process_url(m: types.Message, state: FSMContext):
    url = m.text
    await m.answer("⏳ Клонирую и настраиваю... подожди.")
    
    success, res = await asyncio.to_thread(safe_deploy, url)
    
    if success:
        await m.answer(f"✅ Готово! Проект `{res}` скачан.")
    else:
        await m.answer(f"❌ Ошибка клонирования: {res}")
    await state.clear()

@dp.message(F.text.contains("САЙТ"))
async def toggle(m: types.Message):
    SYSTEM_STATE["is_active"] = not SYSTEM_STATE["is_active"]
    msg = "Сайт ВКЛЮЧЕН" if SYSTEM_STATE["is_active"] else "Сайт ВЫКЛЮЧЕН"
    await m.answer(f"📢 {msg}", reply_markup=get_kb())

# --- SERVER ---
@app.websocket("/ws/void")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_ws.add(websocket)
    try:
        while True:
            await websocket.send_json({"active": SYSTEM_STATE["is_active"], "online": len(active_ws)})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_ws.remove(websocket)

async def main():
    # Запуск сервера на 7066 и бота
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio"))
    print("💎 СИСТЕМА ЗАПУЩЕНА")
    await asyncio.gather(server.serve(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
