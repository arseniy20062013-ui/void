import asyncio
import logging
import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# Твой токен
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

# Конфигурация локального кластера баз данных (Сюда загружаются терабайты дампов)
DB_CONFIG = {
    "user": "postgres",
    "password": "your_secure_password",
    "database": "massive_leaks_db",
    "host": "127.0.0.1", # База должна крутиться на твоем железе
    "port": 5432
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

class DeepSearchEngine:
    def __init__(self, pool):
        self.pool = pool

    async def full_profile_lookup(self, target_phone: str):
        """
        Глубокий поиск по всем таблицам дампов через асинхронный пул соединений.
        Объединяет данные из логов доставок, соцсетей и провайдеров.
        """
        query = """
            SELECT 
                p.full_name, 
                p.birth_date,
                l.ip_address, 
                l.region,
                s.vk_id, 
                s.tg_username,
                e.email_address,
                e.pass_hash
            FROM phone_registry p
            LEFT JOIN location_logs l ON p.phone = l.phone
            LEFT JOIN social_binds s ON p.phone = s.phone
            LEFT JOIN email_leaks e ON p.phone = e.phone
            WHERE p.phone = $1
            LIMIT 100;
        """
        async with self.pool.acquire() as connection:
            # Выполнение тяжелого запроса к локальной БД
            records = await connection.fetch(query, target_phone)
            return records

    def build_dossier(self, records, phone):
        if not records:
            return f"❌ Данных по номеру {phone} в локальных дампах не найдено."
        
        # Парсинг результатов сложного SQL-запроса
        report = f"🔥 **ГЛУБОКИЙ АНАЛИЗ ЗАВЕРШЕН** 🔥\n📱 Номер: {phone}\n\n"
        
        for idx, r in enumerate(records, 1):
            report += f"[{idx}] СОВПАДЕНИЕ:\n"
            if r['full_name']: report += f"👤 ФИО: {r['full_name']}\n"
            if r['birth_date']: report += f"🎂 Возраст/ДР: {r['birth_date']}\n"
            if r['region']: report += f"📍 Локация: {r['region']}\n"
            if r['ip_address']: report += f"🌐 IP: {r['ip_address']}\n"
            if r['vk_id'] or r['tg_username']: 
                report += f"🔗 Соцсети: VK:{r['vk_id']} | TG:{r['tg_username']}\n"
            if r['email_address']: report += f"📧 Почта: {r['email_address']}\n"
            report += "➖➖➖➖➖➖➖➖\n"
            
        return report

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("☠️ DEEP CORE OSINT ГОТОВ.\nФормат ввода: 79991234567")

@dp.message()
async def execute_search(message: Message):
    phone = message.text.strip()
    status_msg = await message.answer("⏳ *Инициирую сканирование кластера БД...*")
    
    try:
        # Создаем пул подключений к БД для обработки огромных массивов данных
        pool = await asyncpg.create_pool(**DB_CONFIG)
        engine = DeepSearchEngine(pool)
        
        # Выполнение поиска
        records = await engine.full_profile_lookup(phone)
        final_report = engine.build_dossier(records, phone)
        
        await status_msg.edit_text(final_report, parse_mode="Markdown")
        await pool.close()
        
    except Exception as e:
        await status_msg.edit_text(f"КРИТИЧЕСКАЯ ОШИБКА БД: Проверьте подключение к PostgreSQL.\nДетали: {e}")

async def main():
    print("БЭКЕНД ЗАПУЩЕН. ОЖИДАНИЕ ПОДКЛЮЧЕНИЯ POSTGRESQL...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
