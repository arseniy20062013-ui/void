import asyncio
import aiohttp
import re
import random
from urllib.parse import quote
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from bs4 import BeautifulSoup

# ====== КОНФИГУРАЦИЯ ======
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
DADATA_API_KEY = "b65c4cec7c29d56935abf05a05e534cea7b2075c"
DADATA_SECRET_KEY = "1ae34aebd98f740bda338b963a1ee3f13425b8e4"

# Список User-Agent для ротации (имитация разных браузеров)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
]

# ====== ИНИЦИАЛИЗАЦИЯ БОТА ======
bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
async def probe_dadata(phone: str) -> dict:
    """Базовый пробив через DaData (оператор, регион, город)"""
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
                        "operator": r.get("provider") or "?",
                        "region": r.get("region", "?"),
                        "city": r.get("city", "?"),
                        "timezone": r.get("timezone", "UTC+0"),
                        "type": r.get("type", "?")
                    }
    except Exception as e:
        print(f"DaData error: {e}")
    return None

async def fetch(session, url, headers, timeout=15):
    """Безопасный GET-запрос с таймаутом"""
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        print(f"Fetch error {url}: {e}")
    return None

async def search_google(phone: str, ua: str) -> list:
    """Поиск в Google: собираем сниппеты, где может быть имя или ссылки на соцсети"""
    results = []
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q={query}&hl=ru&num=10"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url, headers)
        if not html:
            return results
        soup = BeautifulSoup(html, "html.parser")
        for g in soup.select(".g"):
            snippet = g.get_text()
            # Простейший поиск имени: два слова подряд с большой буквы, похожие на ФИО
            name_match = re.search(r'[А-Я][а-я]+\s[А-Я][а-я]+(?:\s[А-Я][а-я]+)?', snippet)
            if name_match:
                results.append(("Google", name_match.group(0), snippet[:200]))
            else:
                # Ищем ссылки на соцсети
                link = g.select_one("a[href]")
                if link:
                    href = link["href"]
                    if "vk.com" in href or "instagram.com" in href or "facebook.com" in href:
                        results.append(("Google_social", href, ""))
    return results

async def search_vk(phone: str, ua: str) -> list:
    """Поиск в VK по номеру телефона (через внутренний поиск)"""
    results = []
    url = f"https://vk.com/search?c[section]=people&c[phone]=+7{phone}"
    headers = {"User-Agent": ua, "X-Requested-With": "XMLHttpRequest"}
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url, headers)
        if not html:
            return results
        soup = BeautifulSoup(html, "html.parser")
        # Ищем блоки с профилями
        for el in soup.select(".search_item"):
            name_el = el.select_one(".search_item_name")
            if name_el:
                name = name_el.get_text(strip=True)
                link_el = el.select_one("a[href]")
                link = "https://vk.com" + link_el["href"] if link_el else ""
                results.append(("VK", name, link))
    return results

async def search_phone_sites(phone: str, ua: str) -> list:
    """Парсинг пары сайтов-определителей, где люди могут оставлять комментарии с именем"""
    results = []
    sites = [
        f"https://zvonili.com/phone/+7{phone}",
        f"https://who-calls.me/phone/7{phone}"
    ]
    headers = {"User-Agent": ua}
    async with aiohttp.ClientSession() as session:
        for site in sites:
            html = await fetch(session, site, headers)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            # Извлекаем комментарии, ищем в них имена (обычно в тегах <b> или заголовках)
            comments = soup.select(".comment-text, .review-text, .caller-name")
            for com in comments:
                text = com.get_text(strip=True)
                name_match = re.search(r'[А-Я][а-я]+\s[А-Я][а-я]+', text)
                if name_match:
                    results.append(("PhoneSite", name_match.group(0), text[:150]))
    return results

async def collect_data(phone: str) -> dict:
    """
    Основная логика: сбор всех кусочков информации из разных источников.
    Работает не более 5 минут, запросы распределены по разным User-Agent.
    """
    # Сначала DaData (быстрый)
    dadata_task = probe_dadata(phone)

    # Web-источники будем запускать с ротацией User-Agent и задержками
    web_results = []
    sources = [
        ("Google", search_google),
        ("VK", search_vk),
        ("PhoneSites", search_phone_sites)
    ]

    # Запускаем задачи последовательно с разными браузерами
    tasks = []
    for i, (name, func) in enumerate(sources):
        ua = USER_AGENTS[i % len(USER_AGENTS)]
        tasks.append((name, asyncio.ensure_future(func(phone, ua))))
        # Задержка между запусками, чтобы не частить
        await asyncio.sleep(random.uniform(1, 2))

    # Ожидаем все web-задачи с общим таймаутом 240 секунд (4 минуты)
    done, pending = await asyncio.wait(
        [t[1] for t in tasks],
        timeout=240,
        return_when=asyncio.ALL_COMPLETED
    )

    for (name, task) in tasks:
        if task in done:
            try:
                res = task.result()
                web_results.extend(res)
            except Exception as e:
                print(f"Task {name} failed: {e}")
        else:
            task.cancel()

    # DaData тоже ждём
    dadata_info = await dadata_task

    # Собираем сводку
    collected = {
        "dadata": dadata_info,
        "web_data": web_results,
        "possible_names": list(set(r[1] for r in web_results if r[0] in ("Google", "VK", "PhoneSite"))),
        "social_links": list(set(r[1] for r in web_results if r[0] == "Google_social"))
    }
    return collected

# ====== ОБРАБОТЧИКИ БОТА ======
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🛡 <b>DEEP OSINT PROBE v6.0</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Отправь номер телефона. Бот соберёт информацию по кусочкам из открытых источников.\n"
        "Используется ротация браузеров и аккуратные задержки.\n"
        "Максимальное время сбора — 5 минут.",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_input(msg: Message):
    target = msg.text.strip()
    digits = re.sub(r'\D', '', target)
    if len(digits) < 10:
        await msg.answer("❌ Нужно минимум 10 цифр.")
        return

    phone = digits[-10:]  # берём последние 10 цифр

    user_sessions[msg.from_user.id] = phone

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 НАЧАТЬ ГЛУБОКИЙ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
    ])

    await msg.answer(
        f"🎯 <b>ЦЕЛЬ:</b> <code>+7 {phone}</code>\n"
        "Запустить сбор данных из всех доступных источников? Это займёт до 5 минут.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "deep_scan")
async def deep_scan(cb: CallbackQuery):
    phone = user_sessions.get(cb.from_user.id)
    if not phone:
        await cb.answer("Сессия истекла. Отправь номер заново.", show_alert=True)
        return

    # Сообщение-заглушка, пока идёт сбор
    status_msg = await cb.message.edit_text(
        "⏳ <b>Запущен сбор данных...</b>\n"
        "• Google (Chrome)\n"
        "• VK (Firefox)\n"
        "• Сайты-определители (Safari)\n"
        "• DaData\n"
        "Пожалуйста, подождите до 5 минут.",
        parse_mode=ParseMode.HTML
    )

    # Запускаем сбор с общим таймаутом 300 секунд
    try:
        data = await asyncio.wait_for(collect_data(phone), timeout=300)
    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ Превышено время ожидания. Попробуйте позже.")
        await cb.answer()
        return

    # Формируем отчёт
    report = ["🕵️‍♂️ <b>РЕЗУЛЬТАТЫ ГЛУБОКОГО ПОИСКА</b>", "━━━━━━━━━━━━━━━━━━━━"]

    if data["dadata"]:
        d = data["dadata"]
        report += [
            f"📞 <b>Номер:</b> <code>+{d['phone']}</code>",
            f"📡 <b>Оператор:</b> {d['operator']} ({d['type']})",
            f"📍 <b>Регион:</b> {d['region']}",
            f"🏙 <b>Город:</b> {d['city']}",
            f"⏰ <b>Часовой пояс:</b> {d['timezone']}",
            "━━━━━━━━━━━━━━━━━━━━"
        ]
    else:
        report.append("❌ DaData не ответил")

    # Имена
    if data["possible_names"]:
        report.append("👤 <b>Вероятные имена:</b>")
        for name in data["possible_names"]:
            report.append(f"• {name}")
    else:
        report.append("👤 <b>Имена не найдены</b> (либо скрыты)")

    # Соцсети
    if data["social_links"]:
        report.append("🌐 <b>Найденные ссылки на соцсети:</b>")
        for link in data["social_links"]:
            report.append(f"• {link}")
    else:
        report.append("🌐 <b>Прямых ссылок на соцсети не обнаружено</b>")

    # Детали веб-поиска
    if data["web_data"]:
        report.append("━━━━━━━━━━━━━━━━━━━━")
        report.append("📋 <b>Фрагменты из открытых источников:</b>")
        for source, title, snippet in data["web_data"]:
            if snippet:
                report.append(f"▸ [{source}] {snippet[:100]}...")

    report.append("━━━━━━━━━━━━━━━━━━━━")
    report.append("⏱ <i>Сбор завершён за счёт ротации браузеров и открытых данных.</i>")

    await status_msg.edit_text("\n".join(report), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await cb.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery):
    await cb.message.edit_text("🚫 Отменено.")
    await cb.answer()

# ====== ЗАПУСК ======
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())