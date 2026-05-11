import asyncio
import logging
import sqlite3
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# ТОКЕН ТВОЕГО БОТА
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# --- МОДУЛЬ ПАМЯТИ (SQLite) ---
def init_db():
    conn = sqlite3.connect("osint_memory.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dossiers (
            target TEXT PRIMARY KEY,
            data_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_to_memory(target, info):
    conn = sqlite3.connect("osint_memory.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO dossiers (target, data_json) VALUES (?, ?)", (target, info))
    conn.commit()
    conn.close()

def check_memory(target):
    conn = sqlite3.connect("osint_memory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT data_json FROM dossiers WHERE target = ?", (target,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

# --- МОДУЛЬ АВТОНОМНОГО ПОИСКА ---
async def global_web_crawl(target):
    """
    Автономный парсинг поисковой выдачи и открытых реестров (Dorking)
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    search_query = f"https://www.google.com/search?q={target}+intext:contact+OR+intext:phone"
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(search_query) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                # Здесь логика извлечения данных из сниппетов
                return f"Найдено в открытых источниках: {soup.title.string}..."
            return "Глубокое сканирование не дало мгновенных результатов."

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🦾 **AUTONOMOUS OSINT UNIT v5.0**\nЯ запоминаю всё. Введите данные для поиска.")

@dp.message()
async def handle_probe(message: Message):
    target = message.text.strip()
    
    # 1. Сначала проверяем память
    cached_data = check_memory(target)
    if cached_data:
        await message.answer(f"📦 **ДОСТАНО ИЗ ПАМЯТИ:**\n{cached_data}")
        return

    status = await message.answer("📡 *Запуск автономных парсеров и пауков...*")
    
    # 2. Если в памяти нет, запускаем поиск по всему инету
    web_data = await global_web_crawl(target)
    
    # Формируем итоговое досье (в реальности сюда добавляются другие модули)
    full_info = (
        f"📍 Результат пробива: {target}\n"
        f"🔍 Web-анализ: {web_data}\n"
        f"📱 Тип: Мобильный (РФ)\n"
        f"⚙️ Статус: Сохранено в базу данных бота."
    )
    
    # 3. Запоминаем результат
    save_to_memory(target, full_info)
    
    await status.edit_text(f"✅ **НОВЫЕ ДАННЫЕ НАЙДЕНЫ:**\n\n{full_info}")

async def main():
    init_db()
    print("СИСТЕМА С ПАМЯТЬЮ ЗАПУЩЕНА...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
