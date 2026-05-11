import asyncio
import logging
import sqlite3
import re
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- ИНТЕЛЛЕКТУАЛЬНАЯ БАЗА ЭКОСИСТЕМЫ ---
class IntelCore:
    def __init__(self):
        self.conn = sqlite3.connect("vortex_v9.db")
        self.conn.execute("CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, info TEXT)")
        self.conn.commit()

    def save(self, key, info):
        self.conn.execute("INSERT OR REPLACE INTO data VALUES (?, ?)", (key, info))
        self.conn.commit()

    def get(self, key):
        res = self.conn.execute("SELECT info FROM data WHERE key=?", (key,)).fetchone()
        return res[0] if res else None

db = IntelCore()

# --- ЯДРО ГЛУБОКОГО ВЫДИРАНИЯ ДАННЫХ ---
async def deep_scan(target):
    extracted = []
    # Цели для глубокого парсинга (архивы, реестры, соц-префиксы)
    sources = [
        f"https://www.google.com/search?q=site:vk.com+{target}",
        f"https://www.google.com/search?q=site:ok.ru+{target}",
        f"https://www.google.com/search?q=intext:\"{target}\"+contact+info"
    ]
    
    async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
        for url in sources:
            async with session.get(url) as resp:
                text = await resp.text()
                
                # 1. Выдираем реальные ID пользователей
                ids = re.findall(r'id(\d{5,15})', text)
                # 2. Выдираем ФИО (паттерн: заглавные буквы рядом с целью)
                names = re.findall(r'[А-Я][а-я]+\s[А-Я][а-я]+', text)
                # 3. Выдираем упоминания городов и почт
                locations = re.findall(r'г\.\s?[А-Я][а-я]+', text)
                
                if ids: extracted.append(f"🆔 VK ID: {ids[0]}")
                if names: extracted.append(f"👤 Вероятное имя: {names[0]}")
                if locations: extracted.append(f"📍 Локация: {locations[0]}")

    return list(set(extracted))

@dp.message(Command("start"))
async def welcome(m: Message):
    await m.answer("💀 **VORTEX DEEP SCAN v9.0**\nРежим прямого извлечения данных активирован. Введите цель.")

@dp.message()
async def work(m: Message):
    target = m.text.strip()
    
    # Проверка своей базы
    cache = db.get(target)
    if cache: return await m.answer(f"📦 **НАЙДЕНО В ВАШЕЙ БАЗЕ:**\n{cache}")

    status = await m.answer("📡 *Вскрываю пакеты данных, ищу прямые совпадения...*")
    
    # Глубокий парсинг
    found_data = await deep_scan(target)
    
    if not found_data:
        res = "❌ Прямых данных в открытых слоях не найдено. Объект чист или скрыт."
    else:
        res = f"🔥 **ОБЪЕКТ ПРОБИТ:**\n" + "\n".join(found_data)
        res += f"\n\n💾 Данные занесены в вашу экосистему."

    db.save(target, res)
    await status.edit_text(res)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
