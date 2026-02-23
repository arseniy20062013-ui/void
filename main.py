import asyncio
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# --- КОНФИГ (ТВОИ ДАННЫЕ) ---
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
MY_ID = 7173827114

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Глобальное состояние системы
SYSTEM_STATE = {
    "is_active": True,       # Статус сайта (Вкл/Выкл)
    "total_visits": 0,      # Общее кол-во заходов
    "power_mode": "STABLE"   # Режим мощности
}
active_connections = set()

# Настройка CORS для работы с твоим фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ЛОГИКА ТЕЛЕГРАМ БОТА (ПУЛЬТ) ---
def get_admin_kb():
    # Динамическая кнопка в зависимости от статуса
    status_btn = "🔴 ВЫКЛЮЧИТЬ САЙТ" if SYSTEM_STATE["is_active"] else "🟢 ВКЛЮЧИТЬ САЙТ"
    kb = [
        [types.KeyboardButton(text=status_btn)],
        [types.KeyboardButton(text="📊 Статистика системы")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(F.from_user.id == MY_ID, Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("💎 **VOID CORE** запущен.\nУправление сайтом активно.", 
                   reply_markup=get_admin_kb(), parse_mode="Markdown")

@dp.message(F.from_user.id == MY_ID, F.text.contains("САЙТ"))
async def toggle_system(m: types.Message):
    SYSTEM_STATE["is_active"] = not SYSTEM_STATE["is_active"]
    status = "✅ РАБОТАЕТ" if SYSTEM_STATE["is_active"] else "❌ ЗАБЛОКИРОВАН"
    await m.answer(f"Статус системы изменен: {status}", reply_markup=get_admin_kb())

@dp.message(F.from_user.id == MY_ID, F.text == "📊 Статистика системы")
async def send_stats(m: types.Message):
    online = len(active_connections)
    # Автоматическая балансировка: если народу много, меняем режим
    SYSTEM_STATE["power_mode"] = "CLIENT_BOOST" if online > 5 else "STABLE"
    
    msg = (f"📈 **VOID STATS**\n\n"
           f"👥 Онлайн сейчас: `{online}`\n"
           f"🚀 Всего заходов: `{SYSTEM_STATE['total_visits']}`\n"
           f"⚡ Режим мощности: `{SYSTEM_STATE['power_mode']}`\n"
           f"🌐 Статус: {'ВКЛ' if SYSTEM_STATE['is_active'] else 'ВЫКЛ'}")
    await m.answer(msg, parse_mode="Markdown")

# --- WEBSOCKET ДЛЯ САЙТА (СВЯЗЬ В РЕАЛЬНОМ ВРЕМЕНИ) ---
@app.websocket("/ws/void")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    SYSTEM_STATE["total_visits"] += 1
    
    try:
        while True:
            # Каждую секунду шлем сайту актуальное состояние
            payload = {
                "active": SYSTEM_STATE["is_active"],
                "online_count": len(active_connections),
                "power": SYSTEM_STATE["power_mode"],
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# --- ЗАПУСК ---
async def start_app():
    # Запускаем сервер на порту 7066
    config = uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio")
    server = uvicorn.Server(config)
    
    print("🚀 СЕРВЕР И БОТ ЗАПУЩЕНЫ...")
    await asyncio.gather(server.serve(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(start_app())
