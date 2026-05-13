import asyncio
import aiohttp
import re
import random
from urllib.parse import quote
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

# ====== КОНФИГУРАЦИЯ ======
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
DADATA_API_KEY = "b65c4cec7c29d56935abf05a05e534cea7b2075c"
DADATA_SECRET_KEY = "1ae34aebd98f740bda338b963a1ee3f13425b8e4"

# 12 браузеров
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Linux; Android 14; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/23.0 Chrome/120.0.0.0 Mobile Safari/537.36"
]

BROWSER_NAMES = ["Chrome Win", "Chrome Win2", "Chrome Mac", "Firefox Win", "Firefox Linux", "Firefox Mac",
                 "Safari Mac", "Safari iOS", "Edge Win", "Edge Win2", "Opera Win", "Samsung Android"]

# Расширенный стоп-лист для имён (на основе предыдущих ошибок)
STOP_WORDS = set([
    "google", "copyright", "search", "facebook", "twitter", "instagram",
    "yandex", "яндекс", "одноклассники", "вконтакте", "telegram",
    "whatsapp", "viber", "skype", "snapchat", "tiktok", "linkedin",
    "pinterest", "reddit", "tumblr", "flickr", "youtube", "ютуб",
    "download", "upload", "share", "send", "submit", "login", "logout",
    "страница", "помощь", "поддержка", "справка", "закладки", "раздел",
    "новости", "лента", "главная", "поиск", "вход", "регистрация",
    "профиль", "настройки", "безопасность", "конфиденциальность",
    "реклама", "вакансии", "услуги", "товары", "компания", "организация",
    "сообщение", "комментарий", "публикация", "видео", "фото", "запись",
    "музыка", "история", "география", "математика", "физика", "химия",
    "биология", "литература", "экономика", "политика", "спорт",
    "культура", "наука", "технологии", "undefined", "null", "none", "loading",
    "экваториальная", "гвинея", "северная", "корея", "новая", "зеландия",
    "объединенные", "арабские", "эмираты", "республика", "федерация",
    "королевство", "область", "край", "округ", "америка", "европа",
    "африка", "азия", "австралия", "антарктида", "нидерланды",
    "французская", "гвиана", "полинезия", "саудовская", "аравия",
    "южный", "судан", "карибские", "если", "вам", "для", "что", "как",
    "это", "или", "также", "только", "ещё", "уже", "был", "была", "были",
    "весь", "вся", "все", "кто", "кого", "кому", "кем", "что", "чего",
    "чему", "чем", "где", "куда", "откуда", "когда", "зачем", "почему",
    "сколько", "какой", "который", "свой", "своя", "свои", "наш", "наша",
    "наши", "мой", "моя", "мои", "твой", "твоя", "твои", "его", "её", "их",
    "этот", "эта", "эти", "тот", "та", "те", "весь", "всё", "вся", "все",
    "один", "одна", "одно", "одни", "два", "две", "три", "четыре", "пять"
])

# Регулярка для извлечения телефонных номеров из текста
PHONE_REGEX = re.compile(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
def classify_input(text: str) -> dict:
    """Определяет, что прислали: телефон или юзернейм"""
    text = text.strip()
    if re.match(r'^@[a-zA-Z0-9_]{5,}$', text):
        return {"type": "username", "value": text.replace("@", "")}
    digits = re.sub(r'\D', '', text)
    if len(digits) >= 10:
        return {"type": "phone", "value": digits[-10:]}
    return {"type": "unknown", "value": text}

async def fetch_text(session, url, headers, timeout=15):
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 200:
                return await resp.text()
    except:
        pass
    return None

def extract_phone_numbers(html: str) -> list:
    """Извлекает все телефонные номера из HTML-кода страницы"""
    if not html:
        return []
    matches = PHONE_REGEX.findall(html)
    # Очищаем от лишних символов и приводим к единому формату
    clean_numbers = []
    for num in matches:
        digits = re.sub(r'\D', '', num)
        if len(digits) == 11 and digits[0] in '78':
            clean_numbers.append(digits[-10:])
        elif len(digits) == 10:
            clean_numbers.append(digits)
    return list(set(clean_numbers))

def filter_names(raw_names: list) -> list:
    """Убирает из списка имён мусор, используя стоп-слова и проверки"""
    valid = []
    for name in raw_names:
        parts = name.split()
        # Минимум 2 части (имя + фамилия), каждая начинается с заглавной буквы
        if len(parts) < 2:
            continue
        if not all(part[0].isupper() for part in parts):
            continue
        # Проверка на стоп-слова и мусор
        lower_name = name.lower()
        if any(word in STOP_WORDS for word in lower_name.split()):
            continue
        if lower_name in STOP_WORDS:
            continue
        # Проверка на наличие только букв и пробелов
        if not re.match(r'^[A-Za-zА-ЯЁа-яё\s]+$', name):
            continue
        valid.append(name)
    # Удаляем дубликаты
    return list(dict.fromkeys(valid))

async def probe_dadata(phone: str) -> dict:
    url = "https://cleaner.dadata.ru/api/v1/clean/phone"
    headers = {
        "Authorization": f"Token {DADATA_API_KEY}",
        "X-Secret": DADATA_SECRET_KEY,
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, headers=headers, json=[phone]) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    r = data[0]
                    return {
                        "phone": r.get("phone", phone),
                        "operator": r.get("provider") or "Не определен",
                        "region": r.get("region") or "Неизвестно",
                        "city": r.get("city") or "Не указан",
                        "timezone": r.get("timezone", "UTC+0"),
                        "type": r.get("type", "Мобильный")
                    }
    except:
        pass
    return None

# ====== ИСТОЧНИКИ ДЛЯ НОМЕРА ======
async def search_google_phone(session, phone, ua):
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q={query}&hl=ru&num=20"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    if not html:
        return [], []
    # Ищем имена (только ФИО)
    name_pattern = r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?'
    raw_names = re.findall(name_pattern, html)
    names = filter_names(raw_names)
    # Ссылки теперь не ищем специально
    return names, []

async def search_yandex_phone(session, phone, ua):
    query = quote(f"+7{phone}")
    url = f"https://yandex.ru/search/?text={query}&lr=213"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    if not html:
        return [], []
    name_pattern = r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?'
    raw_names = re.findall(name_pattern, html)
    names = filter_names(raw_names)
    return names, []

async def search_zvonili_phone(session, phone, ua):
    url = f"https://zvonili.com/phone/+7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    if not html:
        return [], []
    # На этом сайте имена могут быть в отзывах
    name_pattern = r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+'
    raw_names = re.findall(name_pattern, html)
    names = filter_names(raw_names)
    return names, []

async def search_whocalls_phone(session, phone, ua):
    url = f"https://who-calls.me/phone/7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    if not html:
        return [], []
    name_pattern = r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+'
    raw_names = re.findall(name_pattern, html)
    names = filter_names(raw_names)
    return names, []

# ====== ИСТОЧНИКИ ДЛЯ ЮЗЕРНЕЙМА (поиск номеров) ======
async def search_google_username(session, username, ua):
    """Поиск телефонов, связанных с юзернеймом, через Google"""
    query = quote(f'"{username}" phone OR tel OR +7')
    url = f"https://www.google.com/search?q={query}&num=30"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    if not html:
        return []
    return extract_phone_numbers(html)

async def search_yandex_username(session, username, ua):
    query = quote(f'"{username}" телефон')
    url = f"https://yandex.ru/search/?text={query}&lr=213"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    if not html:
        return []
    return extract_phone_numbers(html)

async def search_special_sites_username(session, username, ua):
    """Поиск на сайтах, где могут быть утечки данных (например, psbdmp.ws)"""
    # Это пример, реальный доступ может быть ограничен
    all_numbers = []
    # Пример: поиск по базам утечек (условный)
    # В реальности нужно использовать публичные API или парсинг, здесь просто демонстрация
    # Оставим как заглушку, чтобы не усложнять
    return all_numbers

# ====== СБОР ДАННЫХ ======
async def collect_phone_data(phone: str, status_callback=None) -> dict:
    dadata_task = asyncio.create_task(probe_dadata(phone))
    all_names = []
    sources_results = {}

    sources = [
        ("Google", search_google_phone),
        ("Yandex", search_yandex_phone),
        ("Zvonili", search_zvonili_phone),
        ("WhoCalls", search_whocalls_phone)
    ]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, (name, func) in enumerate(sources):
            ua = USER_AGENTS[i % len(USER_AGENTS)]
            browser = BROWSER_NAMES[i % len(BROWSER_NAMES)]
            tasks.append((name, browser, asyncio.create_task(func(session, phone, ua))))
            await asyncio.sleep(random.uniform(1.5, 3))

        completed = 0
        total = len(tasks)

        for name, browser, task in tasks:
            try:
                names, links = await asyncio.wait_for(task, timeout=60)
                all_names.extend(names)
                sources_results[name] = {"names": len(names), "browser": browser, "status": "✅"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except asyncio.TimeoutError:
                sources_results[name] = {"names": 0, "browser": browser, "status": "⏰"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except:
                sources_results[name] = {"names": 0, "browser": browser, "status": "❌"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)

    dadata_info = await dadata_task
    unique_names = filter_names(all_names)[:8]

    return {
        "dadata": dadata_info,
        "names": unique_names,
        "sources": sources_results,
        "total_sources": len(sources),
        "success_sources": sum(1 for s in sources_results.values() if s["status"] == "✅")
    }

async def collect_username_data(username: str, status_callback=None) -> dict:
    """Собирает возможные телефонные номера для юзернейма"""
    all_numbers = set()
    sources_results = {}

    sources = [
        ("Google", search_google_username),
        ("Yandex", search_yandex_username),
        # Можно добавить другие источники
    ]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, (name, func) in enumerate(sources):
            ua = USER_AGENTS[i % len(USER_AGENTS)]
            browser = BROWSER_NAMES[i % len(BROWSER_NAMES)]
            tasks.append((name, browser, asyncio.create_task(func(session, username, ua))))
            await asyncio.sleep(random.uniform(1.5, 3))

        completed = 0
        total = len(tasks)

        for name, browser, task in tasks:
            try:
                numbers = await asyncio.wait_for(task, timeout=60)
                all_numbers.update(numbers)
                sources_results[name] = {"numbers": len(numbers), "browser": browser, "status": "✅"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except asyncio.TimeoutError:
                sources_results[name] = {"numbers": 0, "browser": browser, "status": "⏰"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except:
                sources_results[name] = {"numbers": 0, "browser": browser, "status": "❌"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)

    return {
        "numbers": sorted(list(all_numbers))[:10],
        "sources": sources_results,
        "total_sources": len(sources),
        "success_sources": sum(1 for s in sources_results.values() if s["status"] == "✅")
    }

# ====== ОБРАБОТЧИКИ БОТА ======
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "╔══════════════════════════╗\n"
        "║   🛡 <b>SHADOW SCAN v10.0</b>  ║\n"
        "║   Универсальный пробив    ║\n"
        "╚══════════════════════════╝\n"
        "\n"
        "🔹 <b>Для номера:</b> глубочайший поиск имён\n"
        "🔹 <b>Для юзернейма (@...):</b> поиск связанных телефонов\n"
        "\n"
        "👇 Отправьте номер или юзернейм",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_input(msg: Message):
    target = msg.text.strip()
    classification = classify_input(target)

    if classification["type"] == "phone":
        phone = classification["value"]
        formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
        user_sessions[msg.from_user.id] = {"type": "phone", "value": phone, "result": None}

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 ГЛУБОКИЙ ПОИСК", callback_data="deep_scan_phone")],
            [InlineKeyboardButton(text="⚡ БЫСТРЫЙ (DaData)", callback_data="quick_scan")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await msg.answer(
            f"🎯 <b>ЦЕЛЬ (номер):</b> <code>{formatted}</code>\n\n"
            "Выберите режим поиска:",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )

    elif classification["type"] == "username":
        username = classification["value"]
        user_sessions[msg.from_user.id] = {"type": "username", "value": username, "result": None}
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 ИСКАТЬ СВЯЗАННЫЕ НОМЕРА", callback_data="deep_scan_username")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await msg.answer(
            f"🎯 <b>ЦЕЛЬ (юзернейм):</b> @{username}\n\n"
            "⚠️ Мы <b>не можем</b> гарантировать полную деанонимизацию, но попытаемся найти "
            "все телефонные номера, которые упоминаются в интернете вместе с этим юзернеймом.\n"
            "Поиск займёт до 5 минут.",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )

    else:
        await msg.answer("❌ Не удалось распознать номер телефона или юзернейм (@...). Попробуйте ещё раз.")

async def update_status(msg, done, total, current_source, browser, mode="phone"):
    bar_len = 10
    filled = int(bar_len * done / total)
    bar = "▓" * filled + "░" * (bar_len - filled)
    pct = int(done / total * 100)

    status = (
        f"╔══════════════════════════╗\n"
        f"║    🔎 <b>{'ПОИСК НОМЕРОВ' if mode == 'username' else 'ГЛУБОКИЙ ПОИСК'}</b>    ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"Прогресс: [{bar}] {pct}%\n"
        f"Выполнено: {done}/{total}\n"
        f"\n"
        f"🌐 <b>Источник:</b> {current_source}\n"
        f"🖥 <b>Браузер:</b> {browser}\n"
        f"\n"
        f"⏳ <i>Ожидайте...</i>"
    )
    try:
        await msg.edit_text(status, parse_mode=ParseMode.HTML)
    except:
        pass

@dp.callback_query(F.data == "quick_scan")
async def quick_scan(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or data["type"] != "phone":
        await cb.answer("Сессия устарела.", show_alert=True)
        return
    phone = data["value"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    status_msg = await cb.message.edit_text("⚡ <b>Быстрый поиск через DaData...</b>", parse_mode=ParseMode.HTML)
    dadata_info = await probe_dadata(phone)

    if dadata_info:
        d = dadata_info
        report = (
            f"╔══════════════════════════╗\n"
            f"║    ⚡ <b>БЫСТРЫЙ ОТЧЁТ</b>     ║\n"
            f"╚══════════════════════════╝\n"
            f"\n"
            f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
            f"📡 <b>Оператор:</b> {d['operator']}\n"
            f"📶 <b>Тип:</b> {d['type']}\n"
            f"📍 <b>Регион:</b> {d['region']}\n"
            f"🏙 <b>Город:</b> {d['city']}\n"
            f"⏰ <b>Часовой пояс:</b> {d['timezone']}\n"
        )
    else:
        report = "❌ <b>DaData не ответил.</b> Попробуйте глубокий поиск."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ЗАПУСТИТЬ ГЛУБОКИЙ ПОИСК", callback_data="deep_scan_phone")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
    ])
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "deep_scan_phone")
async def deep_scan_phone(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or data["type"] != "phone":
        await cb.answer("Сессия устарела.", show_alert=True)
        return
    phone = data["value"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    status_msg = await cb.message.edit_text("⏳ <b>Запуск глубокого поиска...</b>", parse_mode=ParseMode.HTML)

    async def status_callback(done, total, source, browser):
        await update_status(status_msg, done, total, source, browser, mode="phone")

    try:
        result = await asyncio.wait_for(collect_phone_data(phone, status_callback), timeout=300)
    except asyncio.TimeoutError:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ", callback_data="deep_scan_phone")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
        ])
        await status_msg.edit_text("❌ Превышено время ожидания (5 минут).", reply_markup=kb)
        await cb.answer()
        return

    data["result"] = result
    d = result["dadata"]
    report = (
        f"╔══════════════════════════╗\n"
        f"║   🕵️‍♂️ <b>ПОЛНЫЙ ОТЧЁТ</b>     ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
    )
    if d:
        report += (
            f"📡 <b>Оператор:</b> {d['operator']} ({d['type']})\n"
            f"📍 <b>Регион:</b> {d['region']} | 🏙 {d['city']}\n"
            f"⏰ <b>Часовой пояс:</b> {d['timezone']}\n"
        )
    else:
        report += "📡 <b>DaData:</b> не ответил\n"

    report += "\n👤 <b>Вероятные имена:</b>\n"
    if result["names"]:
        for i, name in enumerate(result["names"], 1):
            report += f"  {i}. {name}\n"
    else:
        report += "  (не найдены)\n"

    report += f"\n📊 <b>Источников проверено:</b> {result['total_sources']}, успешно: {result['success_sources']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ ПОИСК", callback_data="deep_scan_phone")],
        [InlineKeyboardButton(text="🔙 ВЫБОР РЕЖИМА", callback_data="back_to_choice")]
    ])
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "deep_scan_username")
async def deep_scan_username(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or data["type"] != "username":
        await cb.answer("Сессия устарела.", show_alert=True)
        return
    username = data["value"]
    status_msg = await cb.message.edit_text("⏳ <b>Поиск связанных номеров для</b> @{username}...", parse_mode=ParseMode.HTML)

    async def status_callback(done, total, source, browser):
        await update_status(status_msg, done, total, source, browser, mode="username")

    try:
        result = await asyncio.wait_for(collect_username_data(username, status_callback), timeout=300)
    except asyncio.TimeoutError:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ", callback_data="deep_scan_username")],
            [InlineKeyboardButton(text="🔙 ОТМЕНА", callback_data="cancel")]
        ])
        await status_msg.edit_text("❌ Превышено время ожидания.", reply_markup=kb)
        await cb.answer()
        return

    data["result"] = result
    report = (
        f"╔══════════════════════════╗\n"
        f"║  🔍 <b>РЕЗУЛЬТАТЫ ПОИСКА</b>  ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"👤 <b>Юзернейм:</b> @{username}\n"
        f"\n"
        f"📞 <b>Возможные связанные номера:</b>\n"
    )
    if result["numbers"]:
        for i, num in enumerate(result["numbers"], 1):
            report += f"  {i}. +7 {num}\n"
    else:
        report += "  ❌ Не найдено ни одного номера.\n"

    report += f"\n📊 <b>Источников проверено:</b> {result['total_sources']}, успешно: {result['success_sources']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ", callback_data="deep_scan_username")],
        [InlineKeyboardButton(text="🔙 ОТМЕНА", callback_data="cancel")]
    ])
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "back_to_choice")
async def back_to_choice(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data:
        await cb.answer("Сессия истекла.", show_alert=True)
        return

    if data["type"] == "phone":
        phone = data["value"]
        formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔎 ГЛУБОКИЙ ПОИСК", callback_data="deep_scan_phone")],
            [InlineKeyboardButton(text="⚡ БЫСТРЫЙ (DaData)", callback_data="quick_scan")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await cb.message.edit_text(
            f"🎯 <b>ЦЕЛЬ (номер):</b> <code>{formatted}</code>\n\nВыберите режим:",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        username = data["value"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 ИСКАТЬ СВЯЗАННЫЕ НОМЕРА", callback_data="deep_scan_username")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await cb.message.edit_text(
            f"🎯 <b>ЦЕЛЬ (юзернейм):</b> @{username}\n\nВыберите действие:",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    await cb.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery):
    await cb.message.edit_text("🚫 <b>Операция отменена.</b>", parse_mode=ParseMode.HTML)
    await cb.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())