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

# Браузеры для статуса
BROWSER_NAMES = ["Chrome Win", "Chrome Win2", "Chrome Mac", "Firefox Win", "Firefox Linux", "Firefox Mac",
                 "Safari Mac", "Safari iOS", "Edge Win", "Edge Win2", "Opera Win", "Samsung Android"]

# Стоп-слова для имён (страны, мусор)
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
    "undefined", "null", "none", "loading"
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
    """Проверяет, похоже ли это на реальное имя человека"""
    name_lower = name.lower().strip()
    parts = name_lower.split()
    if len(parts) < 2 or len(parts) > 3:
        return False
    for word in parts:
        if len(word) < 2:
            return False
        if word in STOP_WORDS:
            return False
    return True

def extract_names(text: str) -> list:
    """Достаёт только реальные имена (ФИО) через regex"""
    if not text:
        return []
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
    return list(dict.fromkeys(names))[:5]

def extract_social_links(text: str) -> list:
    """Вытаскивает только ссылки на профили, не js/css"""
    if not text:
        return []
    exclude = ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.ico', '.xml']
    urls = re.findall(r'https?://[^\s"\'<>]+', text)
    links = []
    for u in urls:
        u_clean = u.rstrip('.,;:!?')
        if any(u_clean.endswith(ext) for ext in exclude):
            continue
        if any(x in u_clean.lower() for x in ['vk.com/id', 'vk.com/', 'instagram.com/', 'facebook.com/', 'ok.ru/profile/', 't.me/']):
            links.append(u_clean)
    return list(dict.fromkeys(links))[:5]

async def search_google(session, phone: str, ua: str) -> tuple:
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q={query}&hl=ru&num=20"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Google", names, links)

async def search_vk(session, phone: str, ua: str) -> tuple:
    url = f"https://vk.com/search?c[section]=people&c[phone]=+7{phone}"
    headers = {"User-Agent": ua, "X-Requested-With": "XMLHttpRequest"}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("VK", names, links)

async def search_zvonili(session, phone: str, ua: str) -> tuple:
    url = f"https://zvonili.com/phone/+7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Zvonili.com", names, links)

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
    return ("Nomer.net", names, links)

async def search_telegram(session, phone: str, ua: str) -> tuple:
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q=site:t.me+{query}&num=20"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_social_links(html) if html else []
    return ("Telegram", names, links)

async def collect_data(phone: str, status_callback=None) -> dict:
    """Сбор данных с обновлением статуса"""
    dadata_task = asyncio.create_task(probe_dadata(phone))
    all_names = []
    all_links = []
    sources_results = {}

    sources = [
        ("Google", search_google),
        ("VK", search_vk),
        ("Zvonili.com", search_zvonili),
        ("WhoCalls", search_whocalls),
        ("Nomer.net", search_nomer),
        ("Telegram", search_telegram)
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

    all_names = list(dict.fromkeys(all_names))[:8]
    all_links = list(dict.fromkeys(all_links))[:6]

    return {
        "dadata": dadata_info,
        "names": all_names,
        "links": all_links,
        "sources": sources_results,
        "total_sources": len(sources),
        "success_sources": sum(1 for s in sources_results.values() if s["status"] == "✅")
    }

# ====== БОТ ======
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "╔══════════════════════════╗\n"
        "║   🛡 <b>SHADOW SCAN v8.0</b>   ║\n"
        "║   Теневой пробив номера   ║\n"
        "╚══════════════════════════╝\n"
        "\n"
        "📡 <b>Источники поиска:</b>\n"
        "▫ Google (поиск упоминаний)\n"
        "▫ VK (поиск по телефону)\n"
        "▫ Zvonili.com (определитель)\n"
        "▫ WhoCalls.me (комментарии)\n"
        "▫ Nomer.net (база номеров)\n"
        "▫ Telegram (поиск каналов)\n"
        "▫ DaData (оператор/регион)\n"
        "\n"
        "🔄 <b>Ротация:</b> 12 браузеров\n"
        "⏱ <b>Макс. время:</b> 5 минут\n"
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
    user_sessions[msg.from_user.id] = phone

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 НАЧАТЬ ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="⚡ БЫСТРЫЙ ПОИСК (DaData)", callback_data="quick_scan")],
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
    phone = user_sessions.get(cb.from_user.id)
    if not phone:
        await cb.answer("Сессия истекла. Отправь номер заново.", show_alert=True)
        return

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

    # Кнопки действий
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ЗАПУСТИТЬ ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="🔙 НАЗАД К ВЫБОРУ", callback_data="back_to_choice")]
    ])

    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, reply_markup=kb)
    await cb.answer()

async def update_status(msg, done, total, current_source, browser):
    """Обновляет сообщение со статусом"""
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
        f"🌐 <b>Текущий источник:</b> {current_source}\n"
        f"🖥 <b>Браузер:</b> {browser}\n"
        f"\n"
        f"⏳ <i>Пожалуйста, подождите...</i>"
    )
    try:
        await msg.edit_text(status, parse_mode=ParseMode.HTML)
    except:
        pass

@dp.callback_query(F.data == "deep_scan")
async def deep_scan(cb: CallbackQuery):
    phone = user_sessions.get(cb.from_user.id)
    if not phone:
        await cb.answer("Сессия истекла. Отправь номер заново.", show_alert=True)
        return

    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"
    status_msg = await cb.message.edit_text("⏳ <b>Запуск поиска...</b>", parse_mode=ParseMode.HTML)

    async def status_callback(done, total, source, browser):
        await update_status(status_msg, done, total, source, browser)

    try:
        data = await asyncio.wait_for(collect_data(phone, status_callback), timeout=300)
    except asyncio.TimeoutError:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ", callback_data="deep_scan")],
            [InlineKeyboardButton(text="⚡ БЫСТРЫЙ ПОИСК", callback_data="quick_scan")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_choice")]
        ])
        await status_msg.edit_text("❌ <b>Превышено время поиска (5 мин)</b>\nПопробуйте ещё раз или используйте быстрый поиск.",
                                   parse_mode=ParseMode.HTML, reply_markup=kb)
        await cb.answer()
        return

    # Формируем красивый отчёт
    d = data["dadata"]
    report = (
        f"╔══════════════════════════╗\n"
        f"║   🕵️‍♂️ <b>ПОЛНЫЙ ОТЧЁТ</b>     ║\n"
        f"╚══════════════════════════╝\n"
        f"\n"
        f"📞 <b>Номер:</b> <code>{formatted}</code>\n"
    )
    if d:
        report += (
            f"📡 <b>Оператор:</b> {d['operator']}\n"
            f"📶 <b>Тип:</b> {d['type']}\n"
            f"📍 <b>Регион:</b> {d['region']}\n"
            f"🏙 <b>Город:</b> {d['city']}\n"
            f"⏰ <b>Часовой пояс:</b> {d['timezone']}\n"
        )
    else:
        report += "📡 <b>DaData:</b> не ответил\n"

    report += "\n━━━━━━ <b>НАЙДЕННЫЕ ДАННЫЕ</b> ━━━━━━\n\n"

    if data["names"]:
        report += "👤 <b>Вероятные имена:</b>\n"
        for i, name in enumerate(data["names"], 1):
            report += f"  {i}. {name}\n"
    else:
        report += "👤 <b>Имён не найдено</b>\n"

    report += "\n"

    if data["links"]:
        report += "🌐 <b>Ссылки на профили:</b>\n"
        for i, link in enumerate(data["links"], 1):
            short = link[:60] + "..." if len(link) > 60 else link
            report += f"  {i}. {short}\n"
    else:
        report += "🌐 <b>Ссылок не найдено</b>\n"

    report += (
        f"\n━━━━━━ <b>СТАТИСТИКА</b> ━━━━━━\n"
        f"\n"
        f"📊 <b>Источников проверено:</b> {data['total_sources']}\n"
        f"✅ <b>Успешно:</b> {data['success_sources']}\n"
        f"❌ <b>Не ответили:</b> {data['total_sources'] - data['success_sources']}\n"
        f"\n"
        f"<i>Ротация: 12 браузеров</i>\n"
    )

    # Кнопки: вернуться или повторить
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ПОВТОРИТЬ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="🔙 ВЕРНУТЬСЯ К ВЫБОРУ", callback_data="back_to_choice")]
    ])

    await status_msg.edit_text(report, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data == "back_to_choice")
async def back_to_choice(cb: CallbackQuery):
    phone = user_sessions.get(cb.from_user.id)
    if not phone:
        await cb.answer("Сессия истекла.", show_alert=True)
        return

    formatted = f"+7 ({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="⚡ БЫСТРЫЙ ПОИСК", callback_data="quick_scan")],
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