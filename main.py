# bot.py
import sqlite3
import re
import json
import os
from datetime import datetime
import telebot

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = telebot.TeleBot(TOKEN)

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = "prodata.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS search_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  query TEXT,
                  query_type TEXT,
                  results TEXT,
                  timestamp REAL)''')
    
    # Вставляем тестовые данные если их нет
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        test_users = [
            ("user123", "79001234567", "МТС", "Центральный", "Москва", "Иванов Иван", "vk.com/user123", "@user123", "user123@mail.ru", "01.01.1990", "Москва, ул. Примерная, 1", "{}", datetime.now().timestamp()),
            ("testuser", "79161234567", "Билайн", "Центральный", "Москва", "Петров Петр", "vk.com/testuser", "@testuser", "testuser@mail.ru", "02.02.1992", "Москва, ул. Тестовая, 2", "{}", datetime.now().timestamp()),
            ("demo_user", "79261234567", "МегаФон", "Северо-Западный", "Санкт-Петербург", "Сидоров Сидор", "vk.com/demo_user", "@demo_user", "demo@mail.ru", "03.03.1995", "СПб, ул. Демо, 3", "{}", datetime.now().timestamp()),
        ]
        c.executemany("INSERT INTO users (username, phone, operator, region, area, full_name, vk_id, telegram_id, email, dob, address, extra_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", test_users)
    
    conn.commit()
    conn.close()

init_db()

# ==================== БАЗА DEF-КОДОВ ОПЕРАТОРОВ ====================
OPERATOR_DEF = {
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
    "999": {"operator": "Tele2/Yota", "region": "Федеральный", "area": "Россия", "mnc": "20", "mcc": "250"},
}

def normalize_phone(phone: str) -> str:
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

def get_phone_info(phone: str) -> dict:
    phone = normalize_phone(phone)
    if not phone:
        return {"error": "Неверный формат номера"}
    
    def_code = phone[1:4]
    
    operator_info = OPERATOR_DEF.get(def_code, {
        "operator": "Неизвестный оператор (возможно виртуальный)",
        "region": "Неизвестный регион",
        "area": "Неизвестная область",
        "mnc": "Н/Д",
        "mcc": "Н/Д"
    })
    
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
    }
    
    return result

def save_search_log(query: str, query_type: str, results: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO search_logs (query, query_type, results, timestamp) VALUES (?, ?, ?, ?)",
              (query, query_type, results, datetime.now().timestamp()))
    conn.commit()
    conn.close()

# ==================== КОМАНДЫ БОТА ====================

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message,
        "🔍 БОТ ПРОБИВА v4.0 (Автономный)\n\n"
        "Отправь номер или ник для поиска:\n\n"
        "📱 Номер: 89001234567\n"
        "👤 Ник: @username\n\n"
        "Команды:\n"
        "/search — поиск\n"
        "/db — статистика\n"
        "/add — добавить данные\n"
        "/help — помощь"
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message,
        "📖 ПОМОЩЬ\n\n"
        "1. Отправь номер телефона — получишь оператора, регион, область, DEF-код\n"
        "2. Отправь юзернейм — найдёт в базе телефон и данные\n"
        "3. /add телефон юзернейм имя — добавить в базу\n\n"
        "База уже содержит тестовые данные:\n"
        "• user123\n"
        "• testuser\n"
        "• demo_user"
    )

@bot.message_handler(commands=['db'])
def db_stats(message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM phones")
    phones_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users")
    users_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM search_logs")
    logs_count = c.fetchone()[0]
    conn.close()
    bot.reply_to(message,
        f"📊 СТАТИСТИКА БАЗЫ\n"
        f"• Телефонных записей: {phones_count}\n"
        f"• Пользователей: {users_count}\n"
        f"• Логов поиска: {logs_count}\n"
        f"• Операторов: {len(OPERATOR_DEF)}"
    )

@bot.message_handler(commands=['search'])
def search_cmd(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "Использование: /search номер_или_ник")
        return
    query = args[1].strip()
    process_query(message, query)

@bot.message_handler(commands=['add'])
def add_cmd(message):
    args = message.text.split(maxsplit=4)
    if len(args) < 5:
        bot.reply_to(message, "Использование: /add телефон юзернейм имя регион область\nПример: /add 79001234567 user1 Иванов Москва Москва")
        return
    
    phone = normalize_phone(args[1])
    if not phone:
        bot.reply_to(message, "Неверный формат номера")
        return
    
    username = args[2]
    name = args[3]
    region = args[4] if len(args) > 4 else ""
    area = args[5] if len(args) > 5 else ""
    
    phone_info = get_phone_info(phone)
    operator = phone_info.get("operator", "Неизвестно")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, phone, operator, region, area, full_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (username, phone, operator, region, area, name, datetime.now().timestamp()))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"✅ Добавлено: {username} — {phone_info['phone_formatted']} — {operator}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    query = message.text.strip()
    process_query(message, query)

def process_query(message, query):
    is_phone = bool(re.search(r'[\d\s\-\(\)\+]{7,}', query))
    
    if is_phone:
        phone_info = get_phone_info(query)
        if "error" in phone_info:
            bot.reply_to(message, f"❌ {phone_info['error']}")
            return
        
        response = (
            f"📱 **РЕЗУЛЬТАТ ПОИСКА ПО НОМЕРУ**\n\n"
            f"🔢 Номер: {phone_info['phone_formatted']}\n"
            f"📡 Оператор: {phone_info['operator']}\n"
            f"🌍 Регион: {phone_info['region']}\n"
            f"📍 Область: {phone_info['area']}\n"
            f"🏷️ DEF-код: {phone_info['def_code']}\n"
            f"📊 MCC/MNC: {phone_info['mcc']}/{phone_info['mnc']}\n"
            f"🇷🇺 Страна: {phone_info['country']} ({phone_info['country_code']})\n"
            f"📐 Длина: {phone_info['number_length']} цифр\n"
            f"📊 Диапазон: {phone_info['range']}\n"
        )
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone LIKE ?", (f"%{phone_info['phone']}%",))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            response += (
                f"\n👤 **СВЯЗАННЫЕ ДАННЫЕ:**\n"
                f"• Юзернейм: {user_data[1] or 'Н/Д'}\n"
                f"• Имя: {user_data[5] or 'Н/Д'}\n"
                f"• Telegram: {user_data[7] or 'Н/Д'}\n"
                f"• Email: {user_data[8] or 'Н/Д'}\n"
                f"• Адрес: {user_data[11] or 'Н/Д'}\n"
            )
        
        save_search_log(query, "phone", json.dumps(phone_info, ensure_ascii=False))
        bot.reply_to(message, response)
        
    else:
        username = query.replace('@', '').strip()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username LIKE ? OR telegram_id LIKE ? OR vk_id LIKE ?", 
                  (f"%{username}%", f"%{username}%", f"%{username}%"))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            response = (
                f"👤 **НАЙДЕН ПОЛЬЗОВАТЕЛЬ**\n\n"
                f"🔤 Юзернейм: {user_data[1] or 'Н/Д'}\n"
                f"📱 Телефон: {user_data[2] or 'Н/Д'}\n"
                f"📡 Оператор: {user_data[3] or 'Н/Д'}\n"
                f"🌍 Регион: {user_data[4] or 'Н/Д'}\n"
                f"📍 Область: {user_data[5] or 'Н/Д'}\n"
                f"👨 Имя: {user_data[6] or 'Н/Д'}\n"
                f"🔗 VK: {user_data[7] or 'Н/Д'}\n"
                f"📧 Telegram: {user_data[8] or 'Н/Д'}\n"
                f"📮 Email: {user_data[9] or 'Н/Д'}\n"
                f"🎂 Дата рождения: {user_data[10] or 'Н/Д'}\n"
                f"🏠 Адрес: {user_data[11] or 'Н/Д'}\n"
            )
            save_search_log(query, "username", "found")
            bot.reply_to(message, response)
        else:
            response = (
                f"🔍 **ПОИСК: @{username}**\n\n"
                f"❌ В базе не найдено.\n\n"
                f"📝 Возможные платформы:\n"
                f"• t.me/{username}\n"
                f"• vk.com/{username}\n"
                f"• github.com/{username}\n\n"
                f"💡 Отправь номер телефона для получения данных оператора.\n"
                f"💡 Используй /add чтобы добавить данные."
            )
            save_search_log(query, "username", "not_found")
            bot.reply_to(message, response)

if __name__ == '__main__':
    print("=" * 50)
    print("БОТ ЗАПУЩЕН")
    print(f"Токен: {TOKEN[:20]}...")
    print(f"База: {DB_PATH}")
    print(f"Операторов: {len(OPERATOR_DEF)}")
    print("=" * 50)
    bot.polling(none_stop=True)