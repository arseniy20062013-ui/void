import asyncio
import aiohttp
import re
import json
import random
import time
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
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    # Samsung Internet
    "Mozilla/5.0 (Linux; Android 14; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/23.0 Chrome/120.0.0.0 Mobile Safari/537.36"
]

BROWSER_NAMES = ["Chrome Win", "Chrome Win2", "Chrome Mac", "Firefox Win", "Firefox Linux", "Firefox Mac",
                 "Safari Mac", "Safari iOS", "Edge Win", "Edge Win2", "Opera Win", "Samsung Android"]

# Расширенный стоп-лист для имён
STOP_WORDS = [
    "страница", "помощь", "поддержка", "справка", "закладки", "раздел",
    "экваториальная", "гвинея", "северная", "корея", "новая", "зеландия",
    "объединенные", "арабские", "эмираты", "республика", "федерация",
    "королевство", "область", "край", "округ", "америка", "европа",
    "африка", "азия", "австралия", "антарктида", "политика", "экономика",
    "технологии", "наука", "спорт", "культура", "музыка", "история",
    "география", "математика", "физика", "химия", "биология", "литература",
    "компания", "организация", "сообщение", "комментарий", "публикация",
    "видео", "фото", "запись", "лента", "новости", "главная", "поиск",
    "вход", "регистрация", "профиль", "настройки", "безопасность",
    "конфиденциальность", "реклама", "вакансии", "услуги", "товары",
    "undefined", "null", "none", "loading",
    # Географические названия, которые могут попасться
    "нидерланды", "французская", "гвиана", "полинезия", "саудовская",
    "аравия", "южный", "судан", "карибские", "если", "вам",
    "google", "copyright", "search", "facebook", "twitter", "instagram",
    "yandex", "яндекс", "одноклассники", "вконтакте", "telegram",
    "whatsapp", "viber", "skype", "snapchat", "tiktok", "linkedin",
    "pinterest", "reddit", "tumblr", "flickr", "youtube", "ютуб",
    "download", "upload", "share", "send", "submit"
]

# Дополнительно: слова, которые точно не могут быть частью имени
INVALID_NAME_TOKENS = STOP_WORDS + [
    "google", "copyright", "search", "facebook", "twitter", "instagram",
    "yandex", "яндекс", "одноклассники", "вконтакте", "telegram",
    "whatsapp", "viber", "skype", "snapchat", "tiktok", "linkedin",
    "pinterest", "reddit", "tumblr", "flickr", "youtube", "ютуб",
    "download", "upload", "share", "send", "submit"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

# ====== ФУНКЦИИ ПРОБИВА ======
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

async def fetch_text(session, url, headers, timeout=15):
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 200:
                return await resp.text()
    except:
        pass
    return None

def is_valid_name(name: str) -> bool:
    """Жёсткая проверка: только реальные ФИО, без мусора"""
    name = name.strip()
    # Имя должно содержать минимум 2 слова (русские или английские буквы)
    if not re.match(r'^[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?$', name, re.IGNORECASE) and \
       not re.match(r'^[A-Z][a-z]+\s[A-Z][a-z]+(?:\s[A-Z][a-z]+)?$', name):
        return False

    # Проверяем каждое слово на вхождение в стоп-слова или нежелательные токены
    for word in name.split():
        wl = word.lower()
        if wl in INVALID_NAME_TOKENS:
            return False
        # Дополнительно: если слово короче 2 букв — не имя
        if len(word) < 2:
            return False
    # Исключаем фразы целиком, если они в точности совпадают со стоп-словами (например, "Google Search")
    if name.lower() in [w.lower() for w in INVALID_NAME_TOKENS]:
        return False
    # Проверка на наличие цифр и спецсимволов
    if re.search(r'[^а-яёА-ЯЁa-zA-Z\s]', name):
        return False
    return True

def extract_names(text: str) -> list:
    """Вытаскивает только реальные имена (ФИО) через regex с расширенным фильтром"""
    if not text:
        return []
    # Паттерны русских и английских имён
    patterns = [
        r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?',
        r'[A-Z][a-z]+\s[A-Z][a-z]+(?:\s[A-Z][a-z]+)?'
    ]
    names = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if is_valid_name(m):
                names.append(m)
    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    return unique[:8]  # ограничим количество

def extract_social_links(text: str) -> list:
    """Вытаскивает только профили социальных сетей и мессенджеров, исключая мусор"""
    if not text:
        return []
    # Исключаемые расширения и фрагменты
    exclude_ext = ('.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.ico', '.xml', '.json', '.webp')
    exclude_domains = ('login.', 'papi.', 'st4-', 'pushsse', 'share.php', 'oauth', 'api.')
    urls = re.findall(r'https?://[^\s"\'<>]+', text)
    clean_links = []
    for u in urls:
        u = u.rstrip('.,;:!?')
        # Отбрасываем файлы по расширению
        if any(u.lower().endswith(ext) for ext in exclude_ext):
            continue
        # Отбрасываем по наличию служебных подстрок
        if any(part in u.lower() for part in exclude_domains):
            continue
        # Исключаем все ссылки на vk.com (ВК полностью нахрен)
        if 'vk.com' in u.lower():
            continue
        # Принимаем только ссылки на соцсети/профили
        if any(soc in u.lower() for soc in ['instagram.com/', 'facebook.com/', 'ok.ru/profile/', 't.me/', 'linkedin.com/in/', 'twitter.com/', 'pinterest.com/', 'snapchat.com/']):
            clean_links.append(u)
    return list(dict.fromkeys(clean_links))[:6]

# ====== Источники поиска ======
async def search_google(session, phone: str, ua: str) -> tuple:
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q={query}&hl=ru&num=20"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Google", names, links)

async def search_yandex(session, phone: str, ua: str) -> tuple:
    query = quote(f"+7{phone}")
    url = f"https://yandex.ru/search/?text={query}&lr=213"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Yandex", names, links)

async def search_zvonili(session, phone: str, ua: str) -> tuple:
    url = f"https://zvonili.com/phone/+7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Zvonili", names, links)

async def search_whocalls(session, phone: str, ua: str) -> tuple:
    url = f"https://who-calls.me/phone/7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("WhoCalls", names, links)

async def search_nomer(session, phone: str, ua: str) -> tuple:
    url = f"https://nomer.net/telefon/+7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Nomer", names, links)

async def search_caller_report(session, phone: str, ua: str) -> tuple:
    url = f"https://caller.report/7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("CallerReport", names, links)

async def search_tel_search(session, phone: str, ua: str) -> tuple:
    url = f"https://tel.search.ch/?was={phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("TelSearch", names, links)

async def collect_data(phone: str, status_callback=None) -> dict:
    dadata_task = asyncio.create_task(probe_dadata(phone))
    all_names = []
    all_links = []
    sources_results = {}

    sources = [
        ("Google", search_google),
        ("Yandex", search_yandex),
        ("Zvonili", search_zvonili),
        ("WhoCalls", search_whocalls),
        ("Nomer", search_nomer),
        ("CallerReport", search_caller_report),
        ("TelSearch", search_tel_search)
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
                source_name, names, links = await asyncio.wait_for(task, timeout=60)
                all_names.extend(names)
                all_links.extend(links)
                sources_results[name] = {"names": len(names), "links": len(links), "browser": browser, "status": "✅"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except asyncio.TimeoutError:
                sources_results[name] = {"names": 0, "links": 0, "browser": browser, "status": "⏰"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except:
                sources_results[name] = {"names": 0, "links": 0, "browser": browser, "status": "❌"}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)

    dadata_info = await dadata_task

    # Убираем дубликаты имён и ссылок
    seen_names = set()
    unique_names = []
    for n in all_names:
        if n not in seen_names:
            seen_names.add(n)
            unique_names.append(n)
    unique_names = unique_names[:8]

    unique_links = list(dict.fromkeys(all_links))[:6]

    return {
        "dadata": dadata_info,
        "names": unique_names,
        "links": unique_links,
        "sources": sources_results,
        "total_sources": len(sources),
        "success_sources": sum(1 for s in sources_results.values() if s["status"] == "✅")
    }

# ====== БОТ ======
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "╔══════════════════════════╗\n"
        "║   🛡 <b>SHADOW SCAN v9.0</b>   ║\n"
        "║   Глубокий OSINT поиск    ║\n"
        "╚══════════════════════════╝\n"
        "\n"
        "📡 <b>Источники:</b> Google, Yandex, Zvonili,\n"
        "WhoCalls, Nomer, CallerReport, TelSearch\n"
        "➕ DaData (оператор/регион)\n"
        "\n"
        "🔄 <b>Ротация:</b> 12 браузеров\n"
        "⏱ <b>Макс. время:</b> 5 минут\n"
        "📋 <b>3 варианта итогового отчёта</b>\n"
        "\n"
        "👇 <b>Отправьте номер телефона</b>",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_input(msg: Message):
    target = msg.text.strip()
    digits = re.sub(r'\D', '', target)
    if len(digits) < 10:
        await msg.answer("❌ Нужно минимум 10 цифр.")
        return

    phone = digits[-10:]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    user_sessions[msg.from_user.id] = {"phone": phone, "result": None}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="⚡ БЫСТРЫЙ (DaData)", callback_data="quick_scan")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
    ])

    await msg.answer(
        f"╔══════════════════════════╗\n"
        f"║      🎯 <b>НОВАЯ ЦЕЛЬ</b>      ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
        f"\n"
        f"🔎 <b>Глубокий поиск:</b> все источники (5 мин)\n"
        f"⚡ <b>Быстрый поиск:</b> только DaData (5 сек)\n"
        f"\n"
        f"👇 <b>Выберите режим:</b>",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "quick_scan")
async def quick_scan(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data:
        await cb.answer("Сессия истекла.", show_alert=True)
        return
    phone = data["phone"]
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
        [InlineKeyboardButton(text="🔎 ЗАПУСТИТЬ ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="🔙 НАЗАД К ВЫБОРУ", callback_data="back_to_choice")]
    ])

    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

async def update_status(msg, done, total, current_source, browser):
    bar_len = 10
    filled = int(bar_len * done / total)
    bar = "▓" * filled + "░" * (bar_len - filled)
    pct = int(done / total * 100)

    status = (
        f"╔══════════════════════════╗\n"
        f"║    🔎 <b>ГЛУБОКИЙ ПОИСК</b>    ║\n"
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

@dp.callback_query(F.data == "deep_scan")
async def deep_scan(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data:
        await cb.answer("Сессия истекла.", show_alert=True)
        return
    phone = data["phone"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    status_msg = await cb.message.edit_text("⏳ <b>Запуск глубокого поиска...</b>", parse_mode=ParseMode.HTML)

    async def status_callback(done, total, source, browser):
        await update_status(status_msg, done, total, source, browser)

    try:
        result = await asyncio.wait_for(collect_data(phone, status_callback), timeout=300)
    except asyncio.TimeoutError:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ", callback_data="deep_scan")],
            [InlineKeyboardButton(text="⚡ БЫСТРЫЙ ПОИСК", callback_data="quick_scan")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
        ])
        await status_msg.edit_text("❌ <b>Превышено время (5 мин)</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
        await cb.answer()
        return

    # Сохраняем результат в сессию
    data["result"] = result
    # Показываем выбор варианта отчёта
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ ОСНОВНОЙ (DaData + имена)", callback_data="report_basic")],
        [InlineKeyboardButton(text="2️⃣ РАСШИРЕННЫЙ (+ ссылки)", callback_data="report_extended")],
        [InlineKeyboardButton(text="3️⃣ ТЕХНИЧЕСКИЙ ДАМП", callback_data="report_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД К ВЫБОРУ РЕЖИМА", callback_data="back_to_choice")]
    ])

    await status_msg.edit_text(
        "✅ <b>Поиск завершён!</b>\nВыберите вариант отчёта:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("report_"))
async def show_report(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or not data.get("result"):
        await cb.answer("Данные устарели. Повторите поиск.", show_alert=True)
        return

    result = data["result"]
    d = result["dadata"]
    phone = data["phone"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"

    report_type = cb.data
    report_text = ""

    if report_type == "report_basic":
        report_text = (
            f"╔══════════════════════════╗\n"
            f"║   📋 <b>ОСНОВНОЙ ОТЧЁТ</b>    ║\n"
            f"╚══════════════════════════╝\n"
            f"\n"
            f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
        )
        if d:
            report_text += (
                f"📡 <b>Оператор:</b> {d['operator']}\n"
                f"📶 <b>Тип:</b> {d['type']}\n"
                f"📍 <b>Регион:</b> {d['region']}\n"
                f"🏙 <b>Город:</b> {d['city']}\n"
                f"⏰ <b>Часовой пояс:</b> {d['timezone']}\n"
            )
        else:
            report_text += "📡 <b>DaData:</b> не ответил\n"

        report_text += "\n👤 <b>Вероятные имена:</b>\n"
        if result["names"]:
            for i, name in enumerate(result["names"], 1):
                report_text += f"  {i}. {name}\n"
        else:
            report_text += "  (не найдены)\n"

    elif report_type == "report_extended":
        report_text = (
            f"╔══════════════════════════╗\n"
            f"║  🧩 <b>РАСШИРЕННЫЙ ОТЧЁТ</b>  ║\n"
            f"╚══════════════════════════╝\n"
            f"\n"
            f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
        )
        if d:
            report_text += (
                f"📡 <b>Оператор:</b> {d['operator']} ({d['type']})\n"
                f"📍 <b>Регион:</b> {d['region']} / {d['city']}\n"
                f"⏰ <b>Часовой пояс:</b> {d['timezone']}\n"
            )
        else:
            report_text += "📡 <b>DaData:</b> не ответил\n"

        report_text += "\n👤 <b>Имена:</b>\n"
        if result["names"]:
            for i, name in enumerate(result["names"], 1):
                report_text += f"  {i}. {name}\n"
        else:
            report_text += "  (нет)\n"

        report_text += "\n🌐 <b>Ссылки на профили:</b>\n"
        if result["links"]:
            for i, link in enumerate(result["links"], 1):
                short = link[:60] + "..." if len(link) > 60 else link
                report_text += f"  {i}. {short}\n"
        else:
            report_text += "  (нет)\n"

    elif report_type == "report_tech":
        report_text = (
            f"╔══════════════════════════╗\n"
            f"║  ⚙️ <b>ТЕХНИЧЕСКИЙ ДАМП</b>  ║\n"
            f"╚══════════════════════════╝\n"
            f"\n"
            f"📞 <b>Цель:</b> <code>{formatted}</code>\n"
            f"\n"
            f"📊 <b>Статистика источников:</b>\n"
        )
        for src, info in result["sources"].items():
            report_text += f"  {info['status']} {src} (браузер: {info['browser']})\n"
        report_text += f"\n🔍 <b>Успешно:</b> {result['success_sources']}/{result['total_sources']}\n"
        report_text += f"\n👤 <b>Собрано имён:</b> {len(result['names'])}\n"
        report_text += f"🌐 <b>Собрано ссылок:</b> {len(result['links'])}\n"
        # покажем сырые данные кратко
        if result["names"]:
            report_text += "\n<b>Имена:</b> " + ", ".join(result["names"]) + "\n"
        if result["links"]:
            report_text += "\n<b>Ссылки:</b>\n"
            for l in result["links"]:
                report_text += f"  • {l}\n"

    # Кнопки: другой вариант, назад к выбору, в начало
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Основной", callback_data="report_basic"),
         InlineKeyboardButton(text="2️⃣ Расширенный", callback_data="report_extended")],
        [InlineKeyboardButton(text="3️⃣ Технический", callback_data="report_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД К ВЫБОРУ ИТОГОВ", callback_data="back_to_reports")],
        [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ ПОИСК", callback_data="deep_scan")]
    ])

    await cb.message.edit_text(report_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "back_to_reports")
async def back_to_reports(cb: CallbackQuery):
    """Вернуться к выбору варианта отчёта после завершения поиска"""
    data = user_sessions.get(cb.from_user.id)
    if not data or not data.get("result"):
        await cb.answer("Данные устарели.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ ОСНОВНОЙ", callback_data="report_basic")],
        [InlineKeyboardButton(text="2️⃣ РАСШИРЕННЫЙ", callback_data="report_extended")],
        [InlineKeyboardButton(text="3️⃣ ТЕХНИЧЕСКИЙ", callback_data="report_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД К ВЫБОРУ РЕЖИМА", callback_data="back_to_choice")]
    ])
    await cb.message.edit_text(
        "✅ <b>Поиск завершён!</b>\nВыберите вариант отчёта:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await cb.answer()

@dp.callback_query(F.data == "back_to_choice")
async def back_to_choice(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data:
        await cb.answer("Сессия истекла.", show_alert=True)
        return
    phone = data["phone"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="⚡ БЫСТРЫЙ (DaData)", callback_data="quick_scan")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
    ])
    await cb.message.edit_text(
        f"╔══════════════════════════╗\n"
        f"║      🎯 <b>НОВАЯ ЦЕЛЬ</b>      ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
        f"\n"
        f"🔎 <b>Глубокий поиск:</b> все источники (5 мин)\n"
        f"⚡ <b>Быстрый поиск:</b> только DaData (5 сек)\n"
        f"\n"
        f"👇 <b>Выберите режим:</b>",
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