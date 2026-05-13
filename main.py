import asyncio
import logging
import re
import json
import time
import socket
import ssl
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)
sessions: Dict[int, dict] = {}

# ==================== УТИЛИТЫ ====================
def normalize_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits[0] in '78':
        return '7' + digits[1:] if digits[0] == '8' else digits
    if len(digits) == 10:
        return '7' + digits
    return digits

def fetch(url: str, timeout: int = 12) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ru-RU,ru;q=0.9',
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode('utf-8', errors='ignore')
    except:
        return ""

def detect_type(text: str) -> str:
    text = text.strip()
    if re.match(r'^[\+7|8]?\d{10,11}$', re.sub(r'[\s\-\(\)]', '', text)):
        return 'phone'
    if re.match(r'[^@]+@[^@]+\.[^@]+', text):
        return 'email'
    if re.match(r'^[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', text):
        return 'domain'
    if text.startswith('@'):
        return 'username'
    return 'name'

# ==================== ТЕЛЕФОН: ОПЕРАТОР ====================
async def phone_info(phone: str) -> dict:
    clean = normalize_phone(phone)
    info = {'operator': '', 'region': '', 'city': ''}
    if not clean:
        return info
    try:
        data = json.loads(fetch(f"https://htmlweb.ru/geo/api.php?json&telcod={clean}"))
        info['operator'] = data.get('0', {}).get('oper', '')
        info['region'] = data.get('region', {}).get('name', '')
        info['city'] = data.get('city', {}).get('name', '')
    except:
        pass
    return info

# ==================== СОЦСЕТИ ПО НОМЕРУ ====================
async def social_by_phone(phone: str) -> List[dict]:
    clean = normalize_phone(phone)
    profiles = []
    try:
        html = fetch(f"https://vk.com/search?c%5Bphone%5D={clean}&c%5Bsection%5D=people")
        ids = re.findall(r'href="/(id\d+)"', html)
        for id_ in list(set(ids)):
            profiles.append({'platform': 'VK', 'url': f'https://vk.com/{id_}'})
    except:
        pass
    try:
        html = fetch(f"https://ok.ru/dk?cmd=Search&st.query={clean}")
        ids = re.findall(r'href="(/profile/\d+)"', html)
        for id_ in list(set(ids)):
            profiles.append({'platform': 'OK', 'url': f'https://ok.ru{id_}'})
    except:
        pass
    return profiles

# ==================== ПРОВЕРКА НИКА ====================
PLATFORMS = [
    ("VK", "https://vk.com/{}"),
    ("OK", "https://ok.ru/{}"),
    ("Instagram", "https://www.instagram.com/{}/"),
    ("Twitter/X", "https://twitter.com/{}"),
    ("GitHub", "https://github.com/{}"),
    ("Telegram", "https://t.me/{}"),
    ("TikTok", "https://www.tiktok.com/@{}"),
    ("Reddit", "https://www.reddit.com/user/{}"),
    ("Habr", "https://habr.com/ru/users/{}/"),
    ("LinkedIn", "https://www.linkedin.com/in/{}"),
    ("Steam", "https://steamcommunity.com/id/{}"),
    ("YouTube", "https://www.youtube.com/@{}"),
]

async def check_username(username: str) -> List[tuple]:
    found = []
    username = username.lstrip('@').strip()
    if not username:
        return found
    for platform, url_template in PLATFORMS:
        url = url_template.format(username)
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'Mozilla/5.0')
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                if resp.status == 200:
                    found.append((platform, url))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                found.append((platform, url))
        except:
            continue
        await asyncio.sleep(0.1)
    return found

# ==================== WHOIS ====================
def whois_domain(domain: str) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect(("whois.iana.org", 43))
        s.send(f"{domain}\r\n".encode())
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            resp += chunk
        s.close()
        text = resp.decode('utf-8', errors='ignore')
        refer = re.search(r'whois:\s*(\S+)', text)
        if refer:
            whois_server = refer.group(1)
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2.settimeout(10)
            s2.connect((whois_server, 43))
            s2.send(f"{domain}\r\n".encode())
            resp2 = b""
            while True:
                chunk = s2.recv(4096)
                if not chunk: break
                resp2 += chunk
            s2.close()
            return resp2.decode('utf-8', errors='ignore')[:800]
        else:
            return text[:800]
    except:
        return ""

# ==================== ИМЯ: ПОИСК ====================
async def search_name(name: str) -> dict:
    result = {'abstract': '', 'profiles': []}
    try:
        data = json.loads(fetch(f"https://api.duckduckgo.com/?q={urllib.parse.quote(name)}&format=json&no_html=1"))
        if data.get('AbstractText'):
            result['abstract'] = data['AbstractText']
    except:
        pass
    result['profiles'] = await check_username(name.replace(' ', ''))
    return result

# ==================== ГЛАВНЫЙ ПОИСК ====================
async def search(target: str, status_callback=None) -> dict:
    report = {'target': target, 'type': detect_type(target)}

    if report['type'] == 'phone':
        if status_callback:
            await status_callback("1/2 Определение оператора...")
        report['phone_info'] = await phone_info(target)
        if status_callback:
            await status_callback("2/2 Поиск профилей...")
        report['social'] = await social_by_phone(target)

    elif report['type'] == 'username':
        if status_callback:
            await status_callback("Проверка профилей...")
        report['profiles'] = await check_username(target)

    elif report['type'] == 'name':
        if status_callback:
            await status_callback("Поиск информации...")
        report['name_info'] = await search_name(target)

    elif report['type'] == 'domain':
        if status_callback:
            await status_callback("WHOIS запрос...")
        report['whois'] = whois_domain(target)

    elif report['type'] == 'email':
        domain = target.split('@')[-1]
        if status_callback:
            await status_callback("WHOIS домена...")
        report['whois'] = whois_domain(domain)

    return report

# ==================== ФОРМАТИРОВАНИЕ ====================
def format_report(r: dict) -> str:
    lines = [
        "🔎 <b>РЕЗУЛЬТАТЫ ПОИСКА</b>",
        f"🎯 Цель: <code>{r['target']}</code>",
        f"🕒 Время: {datetime.now():%d.%m.%Y %H:%M:%S}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if 'phone_info' in r:
        pi = r['phone_info']
        lines.append("📡 <b>Оператор/Регион:</b>")
        lines.append(f"   • Оператор: {pi.get('operator') or 'неизвестно'}")
        lines.append(f"   • Регион: {pi.get('region') or 'неизвестно'}")
        lines.append(f"   • Город: {pi.get('city') or 'неизвестно'}")

    if 'social' in r and r['social']:
        lines.append(f"🌐 <b>Профили:</b>")
        for s in r['social']:
            lines.append(f"   • <a href='{s['url']}'>{s['platform']}</a>")

    if 'profiles' in r and r['profiles']:
        lines.append(f"🌐 <b>Найденные профили:</b>")
        for platform, url in r['profiles']:
            lines.append(f"   • <a href='{url}'>{platform}</a>")

    if 'name_info' in r:
        ni = r['name_info']
        if ni.get('abstract'):
            lines.append(f"📚 <b>Информация:</b>\n{ni['abstract']}")
        if ni.get('profiles'):
            lines.append(f"🌐 <b>Профили:</b>")
            for platform, url in ni['profiles']:
                lines.append(f"   • <a href='{url}'>{platform}</a>")

    if 'whois' in r and r['whois']:
        lines.append(f"🌍 <b>WHOIS:</b>\n<pre>{r['whois'][:500]}</pre>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Данные только из открытых источников. Согласие получено.</i>")
    return '\n'.join(lines)

# ==================== КЛАВИАТУРА ====================
def consent_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, ПРОДОЛЖИТЬ", callback_data="ok")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="no")]
    ])

# ==================== ОБРАБОТЧИКИ ====================
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🔎 <b>OSINT БОТ</b>\n\n"
        "Ищу в открытых источниках:\n"
        "📞 Телефон: <code>+7777777777</code>\n"
        "👤 Ник: <code>@username</code>\n"
        "📧 Email: <code>user@mail.ru</code>\n"
        "🌐 Домен: <code>example.com</code>\n"
        "📝 Имя Фамилия\n\n"
        "Нажмите кнопку согласия для запуска.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle(msg: Message):
    target = msg.text.strip()
    if len(target) < 2:
        return

    sessions[msg.from_user.id] = {'target': target, 'time': time.time()}

    type_names = {'phone': '📞 телефон', 'username': '👤 никнейм', 'email': '📧 email', 'domain': '🌐 домен', 'name': '📝 имя'}
    await msg.answer(
        f"🎯 <b>Цель:</b> {target}\n"
        f"📋 <b>Тип:</b> {type_names.get(detect_type(target), 'неизвестно')}\n\n"
        "Запустить поиск по открытым источникам?",
        reply_markup=consent_kb(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "ok")
async def ok_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in sessions:
        await cb.answer("Сессия истекла.", show_alert=True)
        return

    target = sessions[uid]['target']
    await cb.message.edit_text(f"⏳ Поиск: <code>{target}</code>...", parse_mode=ParseMode.HTML)
    await cb.answer()

    status_msg = await cb.message.answer("🔄 Начинаю...")

    async def update(s):
        try:
            await status_msg.edit_text(f"🔄 {s}")
        except:
            pass

    report = await search(target, status_callback=update)
    await status_msg.delete()

    text = format_report(report)
    try:
        await cb.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await cb.message.answer(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.callback_query(F.data == "no")
async def no_cb(cb: CallbackQuery):
    sessions.pop(cb.from_user.id, None)
    await cb.message.edit_text("❌ Поиск отменён.")
    await cb.answer("Отмена")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот запущен. Только открытые данные.")
    asyncio.run(main())