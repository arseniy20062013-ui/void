import asyncio
import logging
import sqlite3
import re
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# ТВОЙ ТОКЕН
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- СОБСТВЕННАЯ БАЗА ЗНАНИЙ (ЭКОСИСТЕМА) ---
class PrivateDatabase:
    def __init__(self):
        self.conn = sqlite3.connect("vortex_base.db")
        self.create_tables()

    def create_tables(self):
        # Таблица для хранения связей: номер -> фио -> почта -> вк
        self.conn.execute('''CREATE TABLE IF NOT EXISTS intelligence (
            target TEXT PRIMARY KEY, 
            full_data TEXT, 
            tags TEXT,
            discovery_date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        self.conn.commit()

    def update_intel(self, target, data):
        self.conn.execute("INSERT OR REPLACE INTO intelligence (target, full_data) VALUES (?, ?)", (target, data))
        self.conn.commit()

    def get_intel(self, target):
        cursor = self.conn.execute("SELECT full_data FROM intelligence WHERE target=?", (target,))
        res = cursor.fetchone()
        return res[0] if res else None

db = PrivateDatabase()

# --- АВТОНОМНЫЙ ПАУК (SEARCH ENGINE) ---
async def autonomous_crawl(target):
    """
    Система сама анализирует выдачу и ищет паттерны (регулярками)
    без сторонних API.
    """
    results = {"phone": target, "found": []}
    search_urls = [
        f"https://www.bing.com/search?q={target}",
        f"https://duckduckgo.com/html/?q={target}+vk+ok+facebook"
    ]
    
    async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'}) as session:
        for url in search_urls:
            async with session.get(url) as resp:
                html = await resp.text()
                # Ищем почты
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
                # Ищем упоминания соцсетей
                socials = re.findall(r'(vk\.com\/[a-zA-Z0-9._]+|t\.me\/[a-zA-Z0-9._]+)', html)
                
                results['found'].extend(list(set(emails + socials)))

    return results

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🌑 **VORTEX AUTONOMOUS OSINT**\nСистема развернута. База данных готова к наполнению.")

@dp.message()
async def handle_request(message: Message):
    target = message.text.strip()
    
    # 1. Сначала ищем в СВОЕЙ накопленной системе
    existing = db.get_intel(target)
    if existing:
        return await message.answer(f"🗄 **ИЗ СОБСТВЕННОЙ БАЗЫ:**\n{existing}")

    status = await message.answer("📡 *Запуск автономного поиска и индексации...*")
    
    # 2. Сама ищет и анализирует
    data = await autonomous_crawl(target)
    
    report = f"🎯 **НОВЫЙ ОБЪЕКТ ИДЕНТИФИЦИРОВАН**\n"
    report += f"📱 Цель: {target}\n"
    report += f"🌐 Найдено связей: {len(data['found'])}\n"
    report += f"📑 Данные: {', '.join(data['found']) if data['found'] else 'В открытом слое нет, жду логов'}\n"
    report += f"💾 Объект добавлен в вашу личную экосистему."

    # 3. Запоминает навсегда
    db.update_intel(target, report)
    
    await status.edit_text(report)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
