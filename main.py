import asyncio
import json
import sqlite3
import uvicorn
from typing import List
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- КОНФИГ (Токены те же) ---
TOKEN_MAIN = "8423667056:AAFxOF1jkteghG6PSK3vccwuI54xlbPmmjA"
TOKEN_ORDERS = "8495993622:AAFZMy4dedK8DE0qMD3siNSvulqj78qDyzU"
MY_ID = 7173827114
DONAT_LINK = "https://www.donationalerts.com/r/normiscp"

# Инициализация
main_bot = Bot(token=TOKEN_MAIN)
order_bot = Bot(token=TOKEN_ORDERS)
dp = Dispatcher()
app = FastAPI()

# Состояние рассылки для балансировки мощи
IS_BROADCASTING = False

# CORS для твоего домена
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
active_connections: List[WebSocket] = []

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()

# --- ОПТИМИЗИРОВАННАЯ БД ---
db = sqlite3.connect('shop.db', check_same_thread=False)
db.row_factory = sqlite3.Row # Чтобы обращаться к данным по именам колонок
cur = db.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)')
cur.execute('CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value INTEGER)')
cur.execute('INSERT OR IGNORE INTO settings VALUES ("total_orders", 0), ("active", 1)')
db.commit()

# --- МОЗГ БАЛАНСИРОВКИ ---
def get_power_config():
    online = len(active_connections)
    # Если идет рассылка или на сайте > 7 человек — сервер "отдыхает", клиент "пашет"
    if IS_BROADCASTING or online > 7:
        return {"mode": "VOID_CLIENT", "power": "LOW", "ui_fx": "basic"}
    return {"mode": "VOID_SERVER", "power": "ULTRA", "ui_fx": "premium"}

# --- ЛОГИКА БОТОВ (Оптимизирована) ---
@dp.message(F.bot.token == TOKEN_ORDERS)
async def admin_handler(m: types.Message, state: FSMContext):
    global IS_BROADCASTING
    if m.from_user.id != MY_ID: return

    if await state.get_state() == AdminStates.waiting_for_broadcast:
        IS_BROADCASTING = True
        cur.execute('SELECT id FROM users'); users = cur.fetchall()
        await m.answer(f"🚀 Мощность перераспределена. Рассылка на {len(users)} чел...")
        
        for user in users:
            try:
                if m.photo: await main_bot.send_photo(user[0], m.photo[-1].file_id, caption=m.caption)
                else: await main_bot.send_message(user[0], m.text)
                await asyncio.sleep(0.05) # Защита от спам-фильтра ТГ
            except: pass
            
        IS_BROADCASTING = False
        await state.clear()
        await m.answer("✅ Рассылка окончена. Мощность сервера восстановлена.")

    # Быстрые команды через простые условия (быстрее чем F.text)
    if m.text == "📈 Статистика":
        cur.execute('SELECT (SELECT COUNT(*) FROM users), (SELECT value FROM settings WHERE name="total_orders")')
        u, o = cur.fetchone()
        await m.answer(f"📊 Юзеров: {u} | Заказов: {o}")

@dp.message(F.bot.token == TOKEN_MAIN)
async def client_handler(m: types.Message):
    if m.text == "/start":
        cur.execute('INSERT OR REPLACE INTO users VALUES (?, ?)', (m.from_user.id, m.from_user.username))
        db.commit()
        await m.answer("Добро пожаловать в систему VOID.")
    elif "руб" in (m.text or "") or "поддержать" in (m.text or ""):
        cur.execute('UPDATE settings SET value = value + 1 WHERE name="total_orders"')
        db.commit()
        await m.answer(f"Реквизиты: {DONAT_LINK}")
        await order_bot.send_message(MY_ID, f"🎁 НОВЫЙ ЗАКАЗ: {m.text}\nОт: @{m.from_user.username}")

# --- API СЕРВЕРА (Для твоего React сайта) ---
@app.websocket("/ws/void")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Передаем состояние системы на сайт
            status = {
                "type": "BALANCE_UPDATE",
                "config": get_power_config(),
                "server_time": datetime.now().strftime("%H:%M:%S"),
                "clients_online": len(active_connections)
            }
            await websocket.send_text(json.dumps(status))
            await asyncio.sleep(3) # Обновление каждые 3 сек
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# --- ГЛАВНЫЙ ЗАПУСК ---
async def main():
    # Запускаем всё параллельно
    server_task = asyncio.create_task(
        uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio")).serve()
    )
    bot_task = asyncio.create_task(dp.start_polling(main_bot, order_bot))
    
    print("💎 VOID SERVER STARTED ON PORT 7066")
    await asyncio.gather(server_task, bot_task)

if __name__ == "__main__":
    asyncio.run(main())
