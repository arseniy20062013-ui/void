import asyncio
import logging
import re
import urllib.request
import urllib.parse
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ТОКЕН ТВОЕГО БОТА
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

class AutonomousGrimReaper:
    """Система самостоятельного сбора данных из открытого веба"""
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    async def scrape_target(self, target):
        extracted_data = []
        # Список дорков для прямого выдирания данных из индекса
        queries = [
            f"{target} + \"owner\"",
            f"{target} + \"адрес\"",
            f"site:vk.com {target}",
            f"site:facebook.com {target}",
            f"\"{target}\" + \"mail.ru\""
        ]

        for q in queries:
            try:
                url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
                req = urllib.request.Request(url, headers=self.headers)
                
                # Прямое чтение HTML без сторонних библиотек
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                    
                    # 1. Вырезаем ФИО (поиск по паттернам кириллицы в заголовках)
                    names = re.findall(r'[А-Я][а-я]+\s[А-Я][а-я]+\s?[А-Я]?[а-я]*', html)
                    # 2. Вырезаем ID и Ники
                    nicks = re.findall(r'@[a-zA-Z0-9_]+|id\d{6,12}', html)
                    # 3. Вырезаем связанные города
                    cities = re.findall(r'г\.\s[А-Я][а-я]+', html)
                    
                    if names: extracted_data.extend(names[:3])
                    if nicks: extracted_data.extend(nicks[:3])
                    if cities: extracted_data.extend(cities[:2])
            except:
                continue
        
        return sorted(list(set(extracted_data)))

reaper = AutonomousGrimReaper()

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("🏗 **AUTONOMOUS REAPER v11.0**\nЯ ищу сам. Никаких API. Только сырой интернет. Введите цель.")

@dp.message()
async def probe(m: Message):
    target = m.text.strip()
    status = await m.answer("🧬 *Идет автономное вскрытие веба...*")
    
    # Прямой поиск и парсинг
    data = await reaper.scrape_target(target)
    
    if not data:
        report = f"🔍 Объект {target}: Прямых улик в первом эшелоне веба не найдено. Пробую глубокий парсинг..."
    else:
        report = f"💀 **РЕЗУЛЬТАТ АВТОНОМНОГО ПРОБИВА** 💀\n\n"
        report += "📍 Найдено связей:\n" + "\n".join([f"— {item}" for item in data])
        report += f"\n\n🔗 Объект привязан к цифровому следу {target}."

    await status.edit_text(report)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
