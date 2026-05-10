# bot.py
import sqlite3
import re
import json
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = "prodata.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Таблица пользователей (юзернейм -> данные)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  phone TEXT,
                  operator TEXT,
                  region TEXT,
                  area TEXT,
                  full_name TEXT,
                  vk_id TEXT,
                  telegram_id TEXT,
                  email TEXT,
                  dob TEXT,
                  address TEXT,
                  extra_data TEXT,
                  created_at REAL)''')
    
    # Таблица номеров (номер -> данные)
    c.execute('''CREATE TABLE IF NOT EXISTS phones
                 (phone TEXT PRIMARY KEY,
                  operator TEXT,
                  region TEXT,
                  area TEXT,
                  mnc TEXT,
                  mcc TEXT,
                  range_start TEXT,
                  range_end TEXT,
                  usage_type TEXT)''')
    
    # Таблица логов поиска
    c.execute('''CREATE TABLE IF NOT EXISTS search_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  query TEXT,
                  query_type TEXT,
                  results TEXT,
                  timestamp REAL)''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== БАЗА DEF-КОДОВ ОПЕРАТОРОВ ====================
# Полная база DEF-кодов РФ (первые цифры номера после 7/8)
OPERATOR_DEF = {
    # МТС
    "900": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "901": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "902": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "903": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "904": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "905": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "906": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "908": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "909": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "910": {"operator": "МТС", "region": "Центральный", "area": "Москва и МО", "mnc": "01", "mcc": "250"},
    "911": {"operator": "МТС", "region": "Северо-Западный", "area": "Санкт-Петербург и ЛО", "mnc": "01", "mcc": "250"},
    "912": {"operator": "МТС", "region": "Уральский", "area": "Екатеринбург", "mnc": "01", "mcc": "250"},
    "913": {"operator": "МТС", "region": "Сибирский", "area": "Новосибирск", "mnc": "01", "mcc": "250"},
    "914": {"operator": "МТС", "region": "Дальневосточный", "area": "Хабаровск", "mnc": "01", "mcc": "250"},
    "915": {"operator": "МТС", "region": "Центральный", "area": "Москва и МО", "mnc": "01", "mcc": "250"},
    "916": {"operator": "МТС", "region": "Центральный", "area": "Москва и МО", "mnc": "01", "mcc": "250"},
    "917": {"operator": "МТС", "region": "Поволжский", "area": "Самара", "mnc": "01", "mcc": "250"},
    "918": {"operator": "МТС", "region": "Южный", "area": "Краснодар", "mnc": "01", "mcc": "250"},
    "919": {"operator": "МТС", "region": "Центральный", "area": "Москва", "mnc": "01", "mcc": "250"},
    "980": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "981": {"operator": "МТС", "region": "Северо-Западный", "area": "Санкт-Петербург", "mnc": "01", "mcc": "250"},
    "982": {"operator": "МТС", "region": "Уральский", "area": "Урал", "mnc": "01", "mcc": "250"},
    "983": {"operator": "МТС", "region": "Сибирский", "area": "Сибирь", "mnc": "01", "mcc": "250"},
    "984": {"operator": "МТС", "region": "Дальневосточный", "area": "Дальний Восток", "mnc": "01", "mcc": "250"},
    "985": {"operator": "МТС", "region": "Центральный", "area": "Москва и МО", "mnc": "01", "mcc": "250"},
    "986": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    "987": {"operator": "МТС", "region": "Поволжский", "area": "Поволжье", "mnc": "01", "mcc": "250"},
    "988": {"operator": "МТС", "region": "Южный", "area": "Юг", "mnc": "01", "mcc": "250"},
    "989": {"operator": "МТС", "region": "Федеральный", "area": "Россия", "mnc": "01", "mcc": "250"},
    
    # Билайн
    "960": {"operator": "Билайн", "region": "Федеральный", "area": "Россия", "mnc": "03", "mcc": "250"},
    "961": {"operator": "Билайн", "region": "Федеральный", "area": "Россия", "mnc": "03", "mcc": "250"},
    "962": {"operator": "Билайн", "region": "Федеральный", "area": "Россия", "mnc": "03", "mcc": "250"},
    "963": {"operator": "Билайн", "region": "Федеральный", "area": "Россия", "mnc": "03", "mcc": "250"},
    "964": {"operator": "Билайн", "region": "Федеральный", "area": "Россия", "mnc": "03", "mcc": "250"},
    "965": {"operator": "Билайн", "region": "Центральный", "area": "Москва", "mnc": "03", "mcc": "250"},
    "966": {"operator": "Билайн", "region": "Центральный", "area": "Москва", "mnc": "03", "mcc": "250"},
    "967": {"operator": "Билайн", "region": "Поволжский", "area": "Поволжье", "mnc": "03", "mcc": "250"},
    "968": {"operator": "Билайн", "region": "Центральный", "area": "Москва", "mnc": "03", "mcc": "250"},
    "969": {"operator": "Билайн", "region": "Федеральный", "area": "Россия", "mnc": "03", "mcc": "250"},
    
    # МегаФон
    "920": {"operator": "МегаФон", "region": "Федеральный", "area": "Россия", "mnc": "02", "mcc": "250"},
    "921": {"operator": "МегаФон", "region": "Северо-Западный", "area": "Санкт-Петербург", "mnc": "02", "mcc": "250"},
    "922": {"operator": "МегаФон", "region": "Уральский", "area": "Урал", "mnc": "02", "mcc": "250"},
    "923": {"operator": "МегаФон", "region": "Сибирский", "area": "Сибирь", "mnc": "02", "mcc": "250"},
    "924": {"operator": "МегаФон", "region": "Дальневосточный", "area": "Дальний Восток", "mnc": "02", "mcc": "250"},
    "925": {"operator": "МегаФон", "region": "Центральный", "area": "Москва и МО", "mnc": "02", "mcc": "250"},
    "926": {"operator": "МегаФон", "region": "Центральный", "area": "Москва и МО", "mnc": "02", "mcc": "250"},
    "927": {"operator": "МегаФон", "region": "Поволжский", "area": "Поволжье", "mnc": "02", "mcc": "250"},
    "928": {"operator": "МегаФон", "region": "Южный", "area": "Кавказ", "mnc": "02", "mcc": "250"},
    "929": {"operator": "МегаФон", "region": "Федеральный", "area": "Россия", "mnc": "02", "mcc": "250"},
    "930": {"operator": "МегаФон", "region": "Федеральный", "area": "Россия", "mnc": "02", "mcc": "250"},
    "931": {"operator": "МегаФон", "region": "Северо-Западный", "area": "Санкт-Петербург", "mnc": "02", "mcc": "250"},
    "932": {"operator": "МегаФон", "region": "Уральский", "area": "Урал", "mnc": "02", "mcc": "250"},
    "933": {"operator": "МегаФон", "region": "Сибирский", "area": "Сибирь", "mnc": "02", "mcc": "250"},
    "934": {"operator": "МегаФон", "region": "Дальневосточный", "area": "Дальний Восток", "mnc": "02", "mcc": "250"},
    "935": {"operator": "МегаФон", "region": "Центральный", "area": "Москва", "mnc": "02", "mcc": "250"},
    "936": {"operator": "МегаФон", "region": "Центральный", "area": "Москва", "mnc": "02", "mcc": "250"},
    "937": {"operator": "МегаФон", "region": "Поволжский", "area": "Поволжье", "mnc": "02", "mcc": "250"},
    "938": {"operator": "МегаФон", "region": "Южный", "area": "Юг", "mnc": "02", "mcc": "250"},
    "939": {"operator": "МегаФон", "region": "Федеральный", "area": "Россия", "mnc": "02", "mcc": "250"},
    
    # Tele2
    "950": {"operator": "Tele2", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
    "951": {"operator": "Tele2", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
    "952": {"operator": "Tele2", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
    "953": {"operator": "Tele2", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
    "958": {"operator": "Tele2", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
    "977": {"operator": "Tele2", "region": "Центральный", "area": "Москва", "mnc": "20", "mcc": "250"},
    "991": {"operator": "Tele2", "region": "Северо-Западный", "area": "Санкт-Петербург", "mnc": "20", "mcc": "250"},
    "992": {"operator": "Tele2", "region": "Уральский", "area": "Урал", "mnc": "20", "mcc": "250"},
    "993": {"operator": "Tele2", "region": "Сибирский", "area": "Сибирь", "mnc": "20", "mcc": "250"},
    "994": {"operator": "Tele2", "region": "Дальневосточный", "area": "Дальний Восток", "mnc": "20", "mcc": "250"},
    "995": {"operator": "Tele2", "region": "Центральный", "area": "Москва", "mnc": "20", "mcc": "250"},
    "996": {"operator": "Tele2", "region": "Поволжский", "area": "Поволжье", "mnc": "20", "mcc": "250"},
    "999": {"operator": "Tele2", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
    
    # Ростелеком
    "941": {"operator": "Ростелеком", "region": "Федеральный", "area": "Россия", "mnc": "39", "mcc": "250"},
    
    # Yota
    "999": {"operator": "Yota (Tele2)", "region": "Федеральный", "area": "Россия", "mnc": "11", "mcc": "250"},
    
    # Тинькофф Мобайл (MVNO на Tele2)
    "958": {"operator": "Тинькофф Мобайл (Tele2)", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
}

# Расширенная база кодов регионов (ABC-коды)
REGION_CODES = {
    "3": {"code": "3", "region": "Центральный", "area": "Москва и МО"},
    "4": {"code": "4", "region": "Центральный", "area": "Москва и МО"},
    "5": {"code": "5", "region": "Северо-Западный", "area": "Санкт-Петербург и ЛО"},
    "8": {"code": "8", "region": "Поволжский", "area": "Поволжье"},
    "9": {"code": "9", "region": "Южный", "area": "Юг и Кавказ"},
}

# Функция нормализации номера
def normalize_phone(phone: str) -> str:
    """Приводит номер к формату 79XXXXXXXXX"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 11 and digits.startswith('7'):
        pass
    elif len(digits) == 10:
        digits = '7' + digits
    else:
        return None
    return digits

# Функция получения информации о номере
def get_phone_info(phone: str) -> dict:
    """Возвращает полную информацию о номере"""
    phone = normalize_phone(phone)
    if not phone:
        return {"error": "Неверный формат номера"}
    
    # Извлекаем DEF-код (первые 3 цифры после 7)
    def_code = phone[1:4]
    
    operator_info = OPERATOR_DEF.get(def_code, {
        "operator": "Неизвестный оператор",
        "region": "Неизвестный регион",
        "area": "Неизвестная область",
        "mnc": "Н/Д",
        "mcc": "Н/Д"
    })
    
    # Диапазон номера
    range_start = phone[1:7] + "0000"
    range_end = phone[1:7] + "9999"
    
    result = {
        "phone": phone,
        "phone_formatted": f"+{phone[0]} ({phone[1:4]}) {phone[4:7]}-{phone[7:9]}-{phone[9:11]}",
        "operator": operator_info["operator"],
        "region": operator_info["region"],
        "area": operator_info["area"],
        "mnc": operator_info["mnc"],
        "mcc": operator_info["mcc"],
        "def_code": def_code,
        "range": f"+7{phone[1:7]}0000 - +7{phone[1:7]}9999",
        "country": "Россия",
        "country_code": "+7",
        "number_length": len(phone),
        "is_mobile": True,
        "possible_mnp": False,  # MNP перенос номера
    }
    
    return result

# Функция сохранения лога поиска
def save_search_log(query: str, query_type: str, results: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO search_logs (query, query_type, results, timestamp) VALUES (?, ?, ?, ?)",
              (query, query_type, results, datetime.now().timestamp()))
    conn.commit()
    conn.close()

# ==================== ОБРАБОТЧИКИ БОТА ====================

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.answer(
        "🔍 Бот пробива v3.0 (Автономный)\n\n"
        "Отправь номер телефона (любой формат) или юзернейм/ник для поиска.\n\n"
        "Примеры:\n"
        "• 89001234567\n"
        "• +79161234567\n"
        "• @username\n"
        "• username\n\n"
        "Бот использует встроенную базу операторов РФ.\n"
        "Команды:\n"
        "/search <запрос> — поиск\n"
        "/db — статистика базы\n"
    )

@dp.message_handler(commands=['db'])
async def db_stats(message: types.Message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM phones")
    phones_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM search_logs")
    logs_count = c.fetchone()[0]
    conn.close()
    await message.reply(
        f"📊 Статистика базы:\n"
        f"• Телефонных записей: {phones_count}\n"
        f"• Пользователей: {users_count}\n"
        f"• Логов поиска: {logs_count}"
    )

@dp.message_handler(commands=['search'])
async def search_cmd(message: types.Message):
    query = message.get_args().strip()
    if not query:
        await message.reply("Укажи запрос: /search 89001234567 или /search username")
        return
    await process_query(message, query)

@dp.message_handler()
async def handle_message(message: types.Message):
    query = message.text.strip()
    # Определяем тип запроса автоматически
    if re.search(r'[\d\s\-\(\)\+]{7,}', query):
        # Похоже на номер телефона
        await process_query(message, query)
    elif query.startswith('@') or re.match(r'^[a-zA-Z0-9_]{3,32}$', query):
        # Похоже на юзернейм
        await process_query(message, query)
    else:
        await message.reply("Отправь номер телефона или юзернейм для поиска.")

async def process_query(message: types.Message, query: str):
    # Определяем тип запроса
    is_phone = bool(re.search(r'[\d\s\-\(\)\+]{7,}', query))
    
    if is_phone:
        # Это номер телефона
        phone_info = get_phone_info(query)
        if "error" in phone_info:
            await message.reply(f"❌ {phone_info['error']}")
            return
        
        # Формируем красивый ответ
        response = (
            f"📱 **РЕЗУЛЬТАТ ПОИСКА ПО НОМЕРУ**\n\n"
            f"🔢 **Номер:** {phone_info['phone_formatted']}\n"
            f"📡 **Оператор:** {phone_info['operator']}\n"
            f"🌍 **Регион:** {phone_info['region']}\n"
            f"📍 **Область:** {phone_info['area']}\n"
            f"🏷️ **DEF-код:** {phone_info['def_code']}\n"
            f"📊 **MCC/MNC:** {phone_info['mcc']}/{phone_info['mnc']}\n"
            f"🇷🇺 **Страна:** {phone_info['country']}\n"
            f"📞 **Код страны:** {phone_info['country_code']}\n"
            f"📐 **Длина номера:** {phone_info['number_length']} цифр\n"
            f"📶 **Тип:** Мобильный\n"
            f"🔄 **MNP (перенос):** {'Возможен' if phone_info['possible_mnp'] else 'Нет данных'}\n"
            f"📊 **Диапазон:** {phone_info['range']}\n\n"
            f"🔍 **Дополнительный поиск по никнейму...**\n"
        )
        
        # Ищем связанные данные в базе
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone LIKE ?", (f"%{phone_info['phone']}%",))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            response += (
                f"\n👤 **Найдены связанные данные:**\n"
                f"• Юзернейм: {user_data[1] if user_data[1] else 'Н/Д'}\n"
                f"• Имя: {user_data[5] if user_data[5] else 'Н/Д'}\n"
                f"• Telegram: {user_data[7] if user_data[7] else 'Н/Д'}\n"
                f"• Email: {user_data[8] if user_data[8] else 'Н/Д'}\n"
            )
        
        save_search_log(query, "phone", json.dumps(phone_info, ensure_ascii=False))
        await message.reply(response)
        
    else:
        # Это юзернейм/ник
        username = query.replace('@', '').strip()
        
        # Ищем в базе
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username LIKE ? OR telegram_id LIKE ? OR vk_id LIKE ?", 
                  (f"%{username}%", f"%{username}%", f"%{username}%"))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            response = (
                f"👤 **НАЙДЕН ПОЛЬЗОВАТЕЛЬ**\n\n"
                f"🔤 **Юзернейм:** {user_data[1] or 'Н/Д'}\n"
                f"📱 **Телефон:** {user_data[2] or 'Н/Д'}\n"
                f"📡 **Оператор:** {user_data[3] or 'Н/Д'}\n"
                f"🌍 **Регион:** {user_data[4] or 'Н/Д'}\n"
                f"📍 **Область:** {user_data[5] or 'Н/Д'}\n"
                f"👨 **Имя:** {user_data[6] or 'Н/Д'}\n"
                f"🔗 **VK:** {user_data[7] or 'Н/Д'}\n"
                f"📧 **Telegram:** {user_data[8] or 'Н/Д'}\n"
                f"📮 **Email:** {user_data[9] or 'Н/Д'}\n"
                f"🎂 **Дата рождения:** {user_data[10] or 'Н/Д'}\n"
                f"🏠 **Адрес:** {user_data[11] or 'Н/Д'}\n"
            )
            save_search_log(query, "username", json.dumps(user_data, ensure_ascii=False))
            await message.reply(response)
        else:
            # Нет в базе, даём общую инфу
            response = (
                f"🔍 **ПОИСК ПО НИКУ: @{username}**\n\n"
                f"❌ В локальной базе данных не найдено.\n\n"
                f"📝 **Возможные платформы для поиска:**\n"
                f"• Telegram: t.me/{username}\n"
                f"• VK: vk.com/{username}\n"
                f"• GitHub: github.com/{username}\n"
                f"• Twitter/X: x.com/{username}\n"
                f"• Instagram: instagram.com/{username}\n\n"
                f"💡 Если знаешь номер, отправь его для получения данных об операторе и регионе."
            )
            save_search_log(query, "username", "Not found")
            await message.reply(response)

if __name__ == '__main__':
    print("=" * 50)
    print("БОТ ЗАПУЩЕН")
    print(f"Токен: {TOKEN[:20]}...")
    print("База данных: prodata.db")
    print("Операторов в базе: ", len(OPERATOR_DEF))
    print("=" * 50)
    executor.start_polling(dp, skip_updates=True)