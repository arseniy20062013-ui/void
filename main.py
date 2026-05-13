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

# 12 браузеров для ротации
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

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

# ====== КЛАССИФИКАЦИЯ ВВОДА ======
def classify_input(text: str):
    text = text.strip()
    if re.match(r'^@[a-zA-Z0-9_]{5,}$', text):
        return {"type": "username", "value": text.replace("@", "")}
    digits = re.sub(r'\D', '', text)
    if len(digits) >= 10:
        return {"type": "phone", "value": digits[-10:]}
    return {"type": "unknown", "value": text}

# ====== ФУНКЦИИ ПАРСИНГА ======
def extract_phones(html):
    if not html: return []
    raw = re.findall(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', html)
    clean = []
    for num in raw:
        digits = re.sub(r'\D', '', num)
        if len(digits) == 11 and digits[0] in '78':
            clean.append(digits[-10:])
    return list(set(clean))

def extract_emails(html):
    if not html: return []
    return list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))[:5]

def extract_names(html):
    if not html: return []
    STOP = {
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
        "культура", "наука", "технологии", "undefined", "null", "none", "loading"
    }
    pattern = r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?'
    raw = re.findall(pattern, html)
    valid = []
    for name in raw:
        parts = name.split()
        if len(parts) < 2 or len(parts) > 3: continue
        if any(p.lower() in STOP for p in parts): continue
        valid.append(name)
    return list(dict.fromkeys(valid))[:8]

def extract_social_links(html):
    if not html: return []
    urls = re.findall(r'https?://[^\s"\'<>]+', html)
    found = []
    for u in urls:
        u = u.rstrip('.,;:!?')
        # GitHub профиль
        gh_match = re.match(r'https://github\.com/([a-zA-Z0-9_-]+)/?$', u)
        if gh_match:
            user = gh_match.group(1)
            if user not in ["search", "features", "fluidicon", "mcp", "why-github", "security", "topics", "marketplace", "explore", "notifications"]:
                found.append(u)
                continue
        # Другие соцсети
        if any(p in u.lower() for p in ['vk.com/', 'instagram.com/', 'facebook.com/', 'twitter.com/',
                                        't.me/', 'linkedin.com/in/', 'ok.ru/profile/', 'pinterest.com/',
                                        'reddit.com/user/', 'steamcommunity.com/id/']):
            found.append(u)
    return list(dict.fromkeys(found))[:6]

async def fetch(session, url, ua, timeout=12):
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        print(f"[!] Ошибка запроса {url}: {e}")
    return ""

# ====== DaData ======
async def probe_dadata(phone):
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
    except Exception as e:
        print(f"[!] DaData error: {e}")
    return None

# ====== ПОИСК ПО НОМЕРУ (глубокий) ======
async def google_phone(session, phone, ua):
    print(f"[Google] Поиск по номеру +7{phone}")
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q={query}&hl=ru&num=20"
    html = await fetch(session, url, ua)
    names = extract_names(html)
    print(f"[Google] Найдено имён: {len(names)}")
    return names

async def yandex_phone(session, phone, ua):
    print(f"[Yandex] Поиск по номеру +7{phone}")
    query = quote(f"+7{phone}")
    url = f"https://yandex.ru/search/?text={query}&lr=213"
    html = await fetch(session, url, ua)
    names = extract_names(html)
    print(f"[Yandex] Найдено имён: {len(names)}")
    return names

async def zvonili_phone(session, phone, ua):
    print(f"[Zvonili] Запрос +7{phone}")
    url = f"https://zvonili.com/phone/+7{phone}"
    html = await fetch(session, url, ua)
    names = extract_names(html)
    print(f"[Zvonili] Найдено имён: {len(names)}")
    return names

async def whocalls_phone(session, phone, ua):
    print(f"[WhoCalls] Запрос +7{phone}")
    url = f"https://who-calls.me/phone/7{phone}"
    html = await fetch(session, url, ua)
    names = extract_names(html)
    print(f"[WhoCalls] Найдено имён: {len(names)}")
    return names

async def nomer_phone(session, phone, ua):
    print(f"[Nomer] Запрос +7{phone}")
    url = f"https://nomer.net/telefon/+7{phone}"
    html = await fetch(session, url, ua)
    names = extract_names(html)
    print(f"[Nomer] Найдено имён: {len(names)}")
    return names

async def collect_phone_data(phone, status_callback=None):
    dadata_task = asyncio.create_task(probe_dadata(phone))
    all_names = []
    sources_stats = {}
    sources = [
        ("Google", google_phone),
        ("Yandex", yandex_phone),
        ("Zvonili.com", zvonili_phone),
        ("WhoCalls", whocalls_phone),
        ("Nomer.net", nomer_phone)
    ]
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, (name, func) in enumerate(sources):
            ua = USER_AGENTS[i % len(USER_AGENTS)]
            browser = BROWSER_NAMES[i % len(BROWSER_NAMES)]
            tasks.append((name, browser, asyncio.create_task(func(session, phone, ua))))
            await asyncio.sleep(random.uniform(0.8, 1.5))
        completed = 0
        total = len(sources)
        for name, browser, task in tasks:
            try:
                names = await asyncio.wait_for(task, timeout=60)
                all_names.extend(names)
                sources_stats[name] = {"status": "✅", "names": len(names)}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
            except Exception as e:
                print(f"[!] Ошибка {name}: {e}")
                sources_stats[name] = {"status": "❌", "names": 0}
                completed += 1
                if status_callback:
                    await status_callback(completed, total, name, browser)
    dadata_info = await dadata_task
    all_names = list(dict.fromkeys(all_names))[:8]
    return {
        "dadata": dadata_info,
        "names": all_names,
        "sources": sources_stats,
        "total_sources": total
    }

# ====== ПОИСК ПО ЮЗЕРНЕЙМУ (полный сбор) ======
DORKS = [
    '"{username}" phone OR tel OR +7',
    '"{username}" email OR почта',
    '"{username}" vk.com OR вконтакте',
    '"{username}" instagram',
    '"{username}" facebook',
    '"{username}" twitter',
    '"{username}" github',
    '"{username}" site:pastebin.com',
    '"{username}" site:psbdmp.ws',
    '"{username}" site:t.me',
    '"{username}" "телефон"',
    '"{username}" "номер"',
    '"{username}" контакт',
    '"{username}" address OR адрес',
    '"{username}" паспорт',
    '"{username}" site:4pda.to',
    '"{username}" site:habr.com',
    '"{username}" site:forum.mozilla-russia.org',
    '"{username}" site:freelance.ru',
    '"{username}" site:avito.ru',
]

async def process_dork(session, username, dork, ua):
    query = quote(dork.format(username=username))
    url = f"https://www.google.com/search?q={query}&num=20&hl=ru"
    html = await fetch(session, url, ua)
    if not html:
        return {"dork": dork, "phones": [], "emails": [], "names": [], "social": []}
    phones = extract_phones(html)
    emails = extract_emails(html)
    names = extract_names(html)
    social = extract_social_links(html)
    print(f"[Dork] {dork}: телефонов={len(phones)}, email={len(emails)}, имена={len(names)}, соцсети={len(social)}")
    return {"dork": dork, "phones": phones, "emails": emails, "names": names, "social": social}

async def deep_osint_username(username, status_callback=None):
    all_phones = set()
    all_emails = set()
    all_names = []
    all_social = []
    sources_stats = {}
    total_sources = len(DORKS) + 3  # + GitHub, форумы, PSBDMP отдельно

    async with aiohttp.ClientSession() as session:
        # 1. Все Google-дорки
        for i, dork in enumerate(DORKS, 1):
            ua = USER_AGENTS[i % len(USER_AGENTS)]
            browser = BROWSER_NAMES[i % len(BROWSER_NAMES)]
            if status_callback:
                await status_callback(i, total_sources, f"Dork {i}/{len(DORKS)}: {dork[:40]}...", browser)
            try:
                res = await asyncio.wait_for(process_dork(session, username, dork, ua), timeout=45)
                all_phones.update(res["phones"])
                all_emails.update(res["emails"])
                all_names.extend(res["names"])
                all_social.extend(res["social"])
                sources_stats[f"Dork {i}"] = {"status": "✅", "phones": len(res["phones"]), "emails": len(res["emails"])}
            except Exception as e:
                sources_stats[f"Dork {i}"] = {"status": "❌"}
                print(f"[!] Ошибка дорка {i}: {e}")
            await asyncio.sleep(random.uniform(0.5, 1.2))

        # 2. GitHub отдельно
        idx = len(DORKS) + 1
        ua = USER_AGENTS[idx % len(USER_AGENTS)]
        browser = BROWSER_NAMES[idx % len(BROWSER_NAMES)]
        if status_callback:
            await status_callback(idx, total_sources, "GitHub", browser)
        try:
            github_url = f"https://github.com/search?q={username}&type=users"
            html = await fetch(session, github_url, ua)
            if html:
                profiles = re.findall(r'https://github\.com/[a-zA-Z0-9_-]+', html)
                for p in profiles:
                    if re.match(r'https://github\.com/[a-zA-Z0-9_-]+$', p):
                        all_social.append(p)
            sources_stats["GitHub"] = {"status": "✅", "profiles": len(all_social)}
            print(f"[GitHub] Профилей: {len(all_social)}")
        except:
            sources_stats["GitHub"] = {"status": "❌"}

        # 3. PSBDMP (утечки)
        idx += 1
        ua = USER_AGENTS[idx % len(USER_AGENTS)]
        browser = BROWSER_NAMES[idx % len(BROWSER_NAMES)]
        if status_callback:
            await status_callback(idx, total_sources, "PSBDMP", browser)
        try:
            psbdmp_url = f"https://psbdmp.ws/api/search/{username}"
            async with session.get(psbdmp_url, headers={"User-Agent": ua}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for paste in data.get("data", []):
                        content = paste.get("content", "")
                        phones = extract_phones(content)
                        emails = extract_emails(content)
                        names = extract_names(content)
                        all_phones.update(phones)
                        all_emails.update(emails)
                        all_names.extend(names)
            sources_stats["PSBDMP"] = {"status": "✅", "phones": len(all_phones), "emails": len(all_emails)}
        except:
            sources_stats["PSBDMP"] = {"status": "❌"}

        # 4. Форумы-определители (через поиск по нику)
        idx += 1
        ua = USER_AGENTS[idx % len(USER_AGENTS)]
        browser = BROWSER_NAMES[idx % len(BROWSER_NAMES)]
        if status_callback:
            await status_callback(idx, total_sources, "Форумы", browser)
        try:
            forum_urls = [
                f"https://zvonili.com/search/?q={username}",
                f"https://who-calls.me/search/?q={username}"
            ]
            for fu in forum_urls:
                html = await fetch(session, fu, ua)
                if html:
                    all_phones.update(extract_phones(html))
            sources_stats["Форумы"] = {"status": "✅", "phones": len(all_phones)}
        except:
            sources_stats["Форумы"] = {"status": "❌"}

    # Финальная обработка
    all_names = list(dict.fromkeys(all_names))[:10]
    all_social = list(dict.fromkeys(all_social))[:8]
    all_phones = sorted(list(all_phones))[:10]
    all_emails = list(all_emails)[:5]

    return {
        "phones": all_phones,
        "emails": all_emails,
        "names": all_names,
        "social": all_social,
        "sources": sources_stats,
        "total_sources": total_sources
    }

# ====== ОБРАБОТЧИКИ БОТА ======
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "╔══════════════════════════╗\n"
        "║   🛡 <b>ULTIMATE OSINT v12</b> ║\n"
        "║   Максимальный пробив     ║\n"
        "╚══════════════════════════╝\n"
        "\n"
        "📡 <b>Номер:</b> поиск имён через DaData, Google, Yandex, Zvonili, WhoCalls, Nomer\n"
        "📡 <b>Юзернейм (@...):</b> 20 дорков, GitHub, утечки, форумы\n"
        "\n"
        "🔎 В реальном времени показываю логи каждого шага.\n"
        "⏱ Макс. время: 5 минут.\n"
        "\n"
        "👇 Отправьте номер или @username",
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
            f"🎯 <b>НОМЕР:</b> <code>{formatted}</code>\nВыберите режим:",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )

    elif classification["type"] == "username":
        username = classification["value"]
        user_sessions[msg.from_user.id] = {"type": "username", "value": username, "result": None}
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 ТОТАЛЬНЫЙ ПОИСК", callback_data="deep_scan_username")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await msg.answer(
            f"🎯 <b>ЮЗЕРНЕЙМ:</b> @{username}\n\n"
            "Будет выполнен поиск по 20 доркам, GitHub, утечкам, форумам.\n"
            "Каждый шаг логируется в реальном времени.\n"
            "Максимальное время — 5 мин.",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )

    else:
        await msg.answer("❌ Не удалось определить номер или юзернейм. Попробуйте ещё раз.")

# Общая функция обновления статуса
async def update_status(msg, done, total, current_source, browser, mode="phone"):
    bar_len = 10
    filled = int(bar_len * done / total)
    bar = "▓" * filled + "░" * (bar_len - filled)
    pct = int(done / total * 100)
    status = (
        f"╔══════════════════════════╗\n"
        f"║    🔎 <b>{'СБОР ДАННЫХ' if mode == 'username' else 'ГЛУБОКИЙ ПОИСК'}</b>    ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"Прогресс: [{bar}] {pct}%\n"
        f"Выполнено: {done}/{total}\n"
        f"\n"
        f"🌐 <b>Текущий шаг:</b> {current_source}\n"
        f"🖥 <b>Браузер:</b> {browser}\n"
        f"\n"
        f"⏳ <i>Выжимаем все соки из интернета...</i>"
    )
    try:
        await msg.edit_text(status, parse_mode=ParseMode.HTML)
    except:
        pass

# Быстрый поиск по номеру
@dp.callback_query(F.data == "quick_scan")
async def quick_scan(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or data["type"] != "phone":
        await cb.answer("Сессия устарела.", show_alert=True)
        return
    phone = data["value"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    status_msg = await cb.message.edit_text("⚡ Быстрый запрос к DaData...")
    info = await probe_dadata(phone)
    if info:
        report = (
            f"╔══════════════════════════╗\n"
            f"║    ⚡ <b>БЫСТРЫЙ ОТЧЁТ</b>     ║\n"
            f"╚══════════════════════════╝\n"
            f"\n"
            f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
            f"📡 <b>Оператор:</b> {info['operator']} ({info['type']})\n"
            f"📍 <b>Регион:</b> {info['region']} | 🏙 {info['city']}\n"
            f"⏰ <b>Часовой пояс:</b> {info['timezone']}\n"
        )
    else:
        report = "❌ DaData не ответил."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ГЛУБОКИЙ ПОИСК", callback_data="deep_scan_phone")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
    ])
    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

# Глубокий поиск номера
@dp.callback_query(F.data == "deep_scan_phone")
async def deep_scan_phone(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or data["type"] != "phone":
        await cb.answer("Сессия устарела.", show_alert=True)
        return
    phone = data["value"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    status_msg = await cb.message.edit_text("⏳ Глубокий поиск запущен...")

    async def status_callback(done, total, source, browser):
        await update_status(status_msg, done, total, source, browser, mode="phone")

    try:
        result = await asyncio.wait_for(collect_phone_data(phone, status_callback), timeout=300)
    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ Превышено время поиска (5 минут).")
        await cb.answer()
        return

    data["result"] = result
    # Показать результат с выбором вариантов отчёта
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ ОСНОВНОЙ", callback_data="report_phone_basic")],
        [InlineKeyboardButton(text="2️⃣ РАСШИРЕННЫЙ", callback_data="report_phone_extended")],
        [InlineKeyboardButton(text="3️⃣ ТЕХНИЧЕСКИЙ", callback_data="report_phone_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
    ])
    await status_msg.edit_text(
        "✅ <b>Глубокий поиск завершён!</b>\nВыберите вариант отчёта:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await cb.answer()

# Тотальный поиск юзернейма
@dp.callback_query(F.data == "deep_scan_username")
async def deep_scan_username(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or data["type"] != "username":
        await cb.answer("Сессия устарела.", show_alert=True)
        return
    username = data["value"]
    status_msg = await cb.message.edit_text("⏳ Запуск тотального поиска...")

    async def status_callback(done, total, source, browser):
        await update_status(status_msg, done, total, source, browser, mode="username")

    try:
        result = await asyncio.wait_for(deep_osint_username(username, status_callback), timeout=300)
    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ Превышено время поиска (5 минут).")
        await cb.answer()
        return

    data["result"] = result
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ ОСНОВНОЙ", callback_data="report_user_basic")],
        [InlineKeyboardButton(text="2️⃣ РАСШИРЕННЫЙ", callback_data="report_user_extended")],
        [InlineKeyboardButton(text="3️⃣ ТЕХНИЧЕСКИЙ", callback_data="report_user_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
    ])
    await status_msg.edit_text(
        "✅ <b>Тотальный поиск завершён!</b>\nВыберите вариант отчёта:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await cb.answer()

# Варианты отчётов для номера
@dp.callback_query(F.data.startswith("report_phone_"))
async def report_phone(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or not data.get("result"):
        await cb.answer("Данные устарели.", show_alert=True)
        return
    result = data["result"]
    d = result["dadata"]
    phone = data["value"]
    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    report_type = cb.data.split("_")[-1]  # basic / extended / tech

    if report_type == "basic":
        text = f"📞 Номер: <code>{formatted}</code>\n"
        if d:
            text += f"📡 Оператор: {d['operator']} ({d['type']})\n📍 {d['region']} / {d['city']}\n"
        text += "\n👤 <b>Вероятные имена:</b>\n" + ("\n".join(f"• {n}" for n in result["names"]) if result["names"] else "❌ не найдены")
    elif report_type == "extended":
        text = f"🧩 <b>Расширенный отчёт по номеру</b>\n\n<b>DaData:</b>\n"
        if d:
            text += f"Оператор: {d['operator']}\nРегион: {d['region']}\nГород: {d['city']}\nЧасовой пояс: {d['timezone']}\n"
        text += f"\n<b>Имена:</b> {', '.join(result['names']) if result['names'] else 'нет'}\n"
        text += f"\n<b>Источники (успешно):</b> {sum(1 for s in result['sources'].values() if s['status']=='✅')}/{result['total_sources']}"
    else:  # tech
        text = f"⚙️ Технический дамп\n\n"
        for src, inf in result["sources"].items():
            text += f"{inf['status']} {src}: имён={inf.get('names',0)}\n"
        text += f"\nВсего источников: {result['total_sources']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Основной", callback_data="report_phone_basic"),
         InlineKeyboardButton(text="2️⃣ Расширенный", callback_data="report_phone_extended")],
        [InlineKeyboardButton(text="3️⃣ Технический", callback_data="report_phone_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
    ])
    await cb.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

# Варианты отчётов для юзернейма
@dp.callback_query(F.data.startswith("report_user_"))
async def report_user(cb: CallbackQuery):
    data = user_sessions.get(cb.from_user.id)
    if not data or not data.get("result"):
        await cb.answer("Данные устарели.", show_alert=True)
        return
    result = data["result"]
    username = data["value"]
    report_type = cb.data.split("_")[-1]

    if report_type == "basic":
        text = f"👤 @{username}\n\n📞 <b>Телефоны:</b> " + (", ".join(result["phones"]) if result["phones"] else "нет")
        text += "\n📧 <b>Email:</b> " + (", ".join(result["emails"]) if result["emails"] else "нет")
        text += "\n👥 <b>Имена:</b> " + (", ".join(result["names"]) if result["names"] else "нет")
    elif report_type == "extended":
        text = f"🧩 @{username}\n\n📞 Телефоны: {', '.join(result['phones'])}\n📧 Email: {', '.join(result['emails'])}\n👥 Имена: {', '.join(result['names'])}\n🌐 Соцсети:\n" + ("\n".join(result["social"]) if result["social"] else "нет")
    else:  # tech
        text = f"⚙️ Дамп\n\n📞 {result['phones']}\n📧 {result['emails']}\n👥 {result['names']}\n🌐 {result['social']}\n\n<b>Источники:</b>\n"
        for src, inf in result["sources"].items():
            text += f"{inf.get('status','?')} {src}\n"
        text += f"\nВсего: {result['total_sources']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Основной", callback_data="report_user_basic"),
         InlineKeyboardButton(text="2️⃣ Расширенный", callback_data="report_user_extended")],
        [InlineKeyboardButton(text="3️⃣ Технический", callback_data="report_user_tech")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
    ])
    await cb.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
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
            [InlineKeyboardButton(text="⚡ БЫСТРЫЙ", callback_data="quick_scan")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await cb.message.edit_text(f"🎯 <b>НОМЕР:</b> <code>{formatted}</code>\nВыберите режим:", reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        username = data["value"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 ТОТАЛЬНЫЙ ПОИСК", callback_data="deep_scan_username")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
        ])
        await cb.message.edit_text(f"🎯 <b>ЮЗЕРНЕЙМ:</b> @{username}\nВыберите действие:", reply_markup=kb, parse_mode=ParseMode.HTML)
    await cb.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery):
    await cb.message.edit_text("🚫 Операция отменена.")
    await cb.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())