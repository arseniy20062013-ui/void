import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# --- КОНФИГ ---
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
MY_ID = 7173827114

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# Состояние системы (управляется ботом)
VOID_CORE = {
    "is_active": True,  # Главный рубильник
    "visits": 0
}
active_sessions = set()

# Чтобы сайт мог подключаться без ошибок
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- ТЕЛЕГРАМ ПУЛЬТ ---
def get_kb():
    label = "🔴 ВЫКЛЮЧИТЬ САЙТ" if VOID_CORE["is_active"] else "🟢 ВКЛЮЧИТЬ САЙТ"
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=label)],
        [types.KeyboardButton(text="📊 СТАТИСТИКА")]
    ], resize_keyboard=True)

@dp.message(Command("start"), F.from_user.id == MY_ID)
async def start(m: types.Message):
    await m.answer("🕹 VOID CORE ACTIVE", reply_markup=get_kb())

@dp.message(F.from_user.id == MY_ID, F.text.contains("САЙТ"))
async def toggle(m: types.Message):
    VOID_CORE["is_active"] = not VOID_CORE["is_active"]
    status = "ОНЛАЙН" if VOID_CORE["is_active"] else "ОФФЛАЙН (ЗАБЛОКИРОВАН)"
    await m.answer(f"📢 Статус изменен: {status}", reply_markup=get_kb())

@dp.message(F.text == "📊 СТАТИСТИКА")
async def stats(m: types.Message):
    await m.answer(f"👥 Онлайн: {len(active_sessions)}\n🚀 Всего заходов: {VOID_CORE['visits']}")

# --- УПРАВЛЕНИЕ САЙТОМ (WebSocket) ---
@app.websocket("/ws/void")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_sessions.add(websocket)
    VOID_CORE["visits"] += 1
    try:
        while True:
            # Отправляем на сайт статус: если active=False, сайт должен "выключиться"
            await websocket.send_json({
                "active": VOID_CORE["is_active"],
                "online": len(active_sessions)
            })
            await asyncio.sleep(1) # Обновление раз в секунду
    except WebSocketDisconnect:
        active_sessions.remove(websocket)

# --- ЗАПУСК ---
async def main():
    # Запускаем сервер на 7066 и бота одновременно
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=7066, loop="asyncio"))
    await asyncio.gather(server.serve(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
