import asyncio
import aiohttp
import re
import json
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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

# ====== ФУНКЦИИ ======
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
                        "operator": r.get("provider") or "?",
                        "region": r.get("region", "?"),
                        "city": r.get("city", "?"),
                        "timezone": r.get("timezone", "UTC+0"),
                        "type": r.get("type", "?")
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

def extract_names(text: str) -> list:
    """Вытаскивает имена (два слова с большой буквы) через regex"""
    if not text:
        return []
    pattern = r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?'
    matches = re.findall(pattern, text)
    return list(set(matches))[:5]

def extract_links(text: str) -> list:
    """Вытаскивает ссылки на соцсети и профили"""
    if not text:
        return []
    links = []
    urls = re.findall(r'https?://[^\s"\'<>]+', text)
    for u in urls:
        if any(x in u for x in ['vk.com', 'instagram.com', 'facebook.com', 'ok.ru', 't.me', 'telegram.org']):
            links.append(u)
    return list(set(links))[:5]

async def search_google(session, phone: str, ua: str) -> tuple:
    """Поиск в Google"""
    query = quote(f"+7{phone}")
    url = f"https://www.google.com/search?q={query}&hl=ru&num=20"
    headers = {"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_links(html) if html else []
    return ("Google", names, links)

async def search_vk(session, phone: str, ua: str) -> tuple:
    """Поиск в VK"""
    url = f"https://vk.com/search?c[section]=people&c[phone]=+7{phone}"
    headers = {"User-Agent": ua, "X-Requested-With": "XMLHttpRequest"}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_links(html) if html else []
    return ("VK", names, links)

async def search_zvonili(session, phone: str, ua: str) -> tuple:
    """Поиск на zvonili.com"""
    url = f"https://zvonili.com/phone/+7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_links(html) if html else []
    return ("Zvonili", names, links)

async def search_whocalls(session, phone: str, ua: str) -> tuple:
    """Поиск на who-calls.me"""
    url = f"https://who-calls.me/phone/7{phone}"
    headers = {"User-Agent": ua}
    html = await fetch_text(session, url, headers)
    names = extract_names(html) if html else []
    links = extract_links(html) if html else []
    return ("WhoCalls", names, links)

async def collect_data(phone: str) -> dict:
    """Сбор всех данных с разных браузеров"""
    dadata_task = asyncio.create_task(probe_dadata(phone))

    all_names = []
    all_links = []

    sources = [search_google, search_vk, search_zvonili, search_whocalls]

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, source in enumerate(sources):
            ua = USER_AGENTS[i % len(USER_AGENTS)]
            tasks.append(asyncio.create_task(source(session, phone, ua)))
            await asyncio.sleep(random.uniform(1.5, 3))

        done, pending = await asyncio.wait(tasks, timeout=240)

        for task in done:
            try:
                source_name, names, links = task.result()
                all_names.extend(names)
                all_links.extend(links)
            except:
                pass

        for task in pending:
            task.cancel()

    dadata_info = await dadata_task

    return {
        "dadata": dadata_info,
        "names": list(set(all_names))[:10],
        "links": list(set(all_links))[:10]
    }

# ====== БОТ ======
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🛡 <b>OSINT PROBE v7.0 (TERMUX READY)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Отправь номер. Бот соберёт имена и ссылки из открытых источников.\n"
        "Ротация браузеров, без bs4, без проблем в Termux.",
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
    user_sessions[msg.from_user.id] = phone

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 НАЧАТЬ ПОИСК", callback_data="deep_scan")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
    ])

    await msg.answer(
        f"🎯 <b>ЦЕЛЬ:</b> <code>+7 {phone}</code>\n"
        "Запустить сбор?",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "deep_scan")
async def deep_scan(cb: CallbackQuery):
    phone = user_sessions.get(cb.from_user.id)
    if not phone:
        await cb.answer("Сессия истекла. Отправь номер заново.", show_alert=True)
        return

    status_msg = await cb.message.edit_text(
        "⏳ <b>Сбор данных...</b>\n"
        "• Google (Chrome)\n"
        "• VK (Firefox)\n"
        "• Zvonili (Safari)\n"
        "• WhoCalls (Edge)\n"
        "• DaData\n"
        "До 5 минут...",
        parse_mode=ParseMode.HTML
    )

    try:
        data = await asyncio.wait_for(collect_data(phone), timeout=300)
    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ Превышено время ожидания.")
        await cb.answer()
        return

    report = ["🕵️‍♂️ <b>РЕЗУЛЬТАТЫ</b>", "━━━━━━━━━━━━━━━━━━━━"]

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

    if data["names"]:
        report.append("👤 <b>Найденные имена:</b>")
        for name in data["names"]:
            report.append(f"• {name}")
    else:
        report.append("👤 <b>Имена не найдены</b>")

    if data["links"]:
        report.append("🌐 <b>Ссылки на профили:</b>")
        for link in data["links"]:
            report.append(f"• {link}")
    else:
        report.append("🌐 <b>Ссылок не найдено</b>")

    report.append("━━━━━━━━━━━━━━━━━━━━")
    report.append("⏱ <i>Сбор завершён.</i>")

    await status_msg.edit_text("\n".join(report), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await cb.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery):
    await cb.message.edit_text("🚫 Отменено.")
    await cb.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())