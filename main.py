import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ВАШ ТОКЕН
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

# ПРЯМЫЕ ШЛЮЗЫ К БАЗАМ УТЕЧЕК (API РЕАЛЬНОГО ПРОБИВА)
# Сюда подключаются ключи от LeakCheck, EyeOfGod API или собственных дампов
LEAK_API_URL = "https://api.leakcheck.net/public?check=" 
SOCIAL_API_URL = "https://api.search4faces.com/v1/search"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

async def get_real_intelligence(target):
    """
    ПРЯМОЙ ЗАПРОС К АГРЕГАТОРАМ УТЕЧЕК
    Возвращает только реальные совпадения из дампов.
    """
    async with aiohttp.ClientSession() as session:
        # Запрос в базу сливов паролей и почт
        async with session.get(f"{LEAK_API_URL}{target}") as resp:
            leak_data = await resp.json() if resp.status == 200 else {"success": False}
        
        results = []
        if leak_data.get("success") and leak_data.get("found") > 0:
            for source in leak_data.get("sources", []):
                results.append(f"📂 Источник слива: {source.get('name')}\n📧 Данные: {source.get('line')}")
        
        return results

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("💀 **CRIMSON OSINT v10.0 (CORE ACCESS)**\nПодключение к шлюзам утечек установлено. Введите цель (номер/почта).")

@dp.message()
async def handle_search(message: Message):
    target = message.text.strip()
    status = await message.answer("🛠 *Вскрываю дампы баз данных...*")
    
    # ПОЛУЧЕНИЕ РЕАЛЬНОЙ ИНФОРМАЦИИ
    intel = await get_real_intelligence(target)
    
    if not intel:
        # Если в паблик-шлюзах нет, бот выдает системный отчет
        report = f"❌ По объекту {target} в текущих открытых дампах совпадений не найдено."
    else:
        report = f"💉 **РЕАЛЬНЫЙ ПРОБИВ ЗАВЕРШЕН** 💉\n\n" + "\n\n".join(intel)
        report += "\n\n⚠️ Данные извлечены из архивов утечек 2022-2026 гг."

    await status.edit_text(report)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
