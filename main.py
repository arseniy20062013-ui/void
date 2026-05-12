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
from typing import Optional, Dict, List, Tuple
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)
sessions = {}

# ==================== ЗАГРУЗЧИК СТРАНИЦ ====================
def fetch(url, headers=None, timeout=15):
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ru-RU,ru;q=0.9',
        }
    try:
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.read().decode('utf-8', errors='ignore')
    except:
        return ""

# ==================== ОПРЕДЕЛИТЕЛЬ НОМЕРА (оператор + регион + возможное имя) ====================
async def phone_info(phone: str) -> Dict:
    clean = re.sub(r'[^\d]', '', phone)
    if len(clean) == 11 and clean[0] in ('7', '8'):
        clean = '7' + clean[1:] if clean[0] == '8' else clean
    elif len(clean) == 10:
        clean = '7' + clean
    else:
        return {}

    result = {'operator': '', 'region': '', 'city': '', 'country': 'Россия'}

    # htmlweb.ru
    try:
        data = json.loads(fetch(f"https://htmlweb.ru/geo/api.php?json&telcod={clean}"))
        result['operator'] = data.get('0', {}).get('oper', '')
        result['region'] = data.get('region', {}).get('name', '')
        result['city'] = data.get('city', {}).get('name', '')
    except:
        pass

    return result

# ==================== ПОИСК ИМЕНИ ПО НОМЕРУ (ПРЯМЫЕ ИСТОЧНИКИ) ====================
async def find_names_by_phone(phone: str) -> List[str]:
    names = []
    clean = re.sub(r'[^\d]', '', phone)

    # 1. num.voxlink.ru
    try:
        html = fetch(f"https://num.voxlink.ru/{clean}/")
        # Ищем ФИО на странице
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names and 'VoxLink' not in n and 'Поиск' not in n:
                names.append(n)
    except:
        pass

    # 2. callfilter.ru
    try:
        html = fetch(f"https://callfilter.ru/{clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names and 'Callfilter' not in n and 'Отзывы' not in n and 'Звонки' not in n:
                names.append(n)
    except:
        pass

    # 3. ktozvonit.com
    try:
        html = fetch(f"https://ktozvonit.com/{clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names and 'Кто звонит' not in n:
                names.append(n)
    except:
        pass

    # 4. nomera.org
    try:
        html = fetch(f"https://nomera.org/telefon/{clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names and 'Номера' not in n and 'Поиск' not in n:
                names.append(n)
    except:
        pass

    # 5. spravkaru.net
    try:
        html = fetch(f"https://spravkaru.net/{clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names:
                names.append(n)
    except:
        pass

    # 6. neberitrubku.ru
    try:
        html = fetch(f"https://neberitrubku.ru/nomer/{clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names:
                names.append(n)
    except:
        pass

    # 7. kto-zvonil.ru
    try:
        html = fetch(f"https://kto-zvonil.ru/nomer/{clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
        for n in found:
            if len(n) > 8 and n not in names:
                names.append(n)
    except:
        pass

    # 8. Поиск в VK (публичный поиск людей)
    try:
        html = fetch(f"https://vk.com/search?c%5Bphone%5D={clean}&c%5Bsection%5D=people")
        found = re.findall(r'data-search-name="([^"]+)"', html)
        for n in found:
            if n not in names and len(n) > 3:
                names.append(n)
    except:
        pass

    # 9. Поиск в OK.ru
    try:
        html = fetch(f"https://ok.ru/dk?cmd=Search&st.query={clean}")
        found = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+', html)
        for n in found:
            if len(n) > 6 and n not in names:
                names.append(n)
    except:
        pass

    # Чистим мусор
    garbage = [
        'Рейсы Путешествия', 'Карты Новости', 'Далее Конфиденциальность',
        'Все Изображения', 'Поиск Картинки', 'Google Play', 'App Store',
        'Войти Регистрация', 'Забыли пароль', 'Показать результаты',
        'Поисковая система', 'Интернет магазин', 'Служба поддержки',
        'Личный кабинет', 'Мобильная версия', 'Полная версия',
        'Обратная связь', 'Пользовательское соглашение', 'Политика конфиденциальности',
        'Все права защищены', 'Создать сайт', 'Бесплатный конструктор',
        'VoxLink', 'Callfilter', 'Кто звонит', 'Номера телефонов',
        'Справочник телефонов', 'Отзывы о номере', 'Проверка номера',
        'Информация о номере', 'Поиск по номеру', 'База номеров',
        'Не бери трубку', 'Кто звонил', 'Определить номер',
        'Чей номер', 'Номер телефона', 'Мобильный номер',
    ]
    names = [n for n in names if not any(g.lower() in n.lower() for g in garbage)]

    return list(set(names))[:15]

# ==================== ПОИСК СОЦСЕТЕЙ ПО НОМЕРУ ====================
async def find_social_by_phone(phone: str) -> List[Dict]:
    social = []
    clean = re.sub(r'[^\d]', '', phone)

    # VK
    try:
        html = fetch(f"https://vk.com/search?c%5Bphone%5D={clean}&c%5Bsection%5D=people")
        ids = re.findall(r'href="/(id\d+)"', html)
        for id_ in ids:
            social.append({'platform': 'VK', 'url': f'https://vk.com/{id_}'})
    except:
        pass

    # OK.ru
    try:
        html = fetch(f"https://ok.ru/dk?cmd=Search&st.query={clean}")
        ids = re.findall(r'href="(/profile/\d+)"', html)
        for id_ in ids:
            social.append({'platform': 'OK.ru', 'url': f'https://ok.ru{id_}'})
    except:
        pass

    # Avito
    try:
        html = fetch(f"https://www.avito.ru/all?q={clean}")
        if 'Объявления' in html or 'item' in html:
            social.append({'platform': 'Avito', 'url': f'https://www.avito.ru/all?q={clean}'})
    except:
        pass

    # 2GIS
    try:
        social.append({'platform': '2GIS', 'url': f'https://2gis.ru/search/{clean}'})
    except:
        pass

    # Telegram (проверка через t.me)
    try:
        html = fetch(f"https://t.me/+{clean}")
        name = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if name and 'Telegram' not in name.group(1):
            social.append({'platform': 'Telegram', 'url': f'https://t.me/+{clean}', 'name': name.group(1)})
    except:
        pass

    return social

# ==================== ПОИСК ОТЗЫВОВ/СНИППЕТОВ О НОМЕРЕ ====================
async def find_snippets_by_phone(phone: str) -> List[str]:
    snippets = []
    clean = re.sub(r'[^\d]', '', phone)

    # DuckDuckGo сниппеты
    try:
        html = fetch(f"https://html.duckduckgo.com/html/?q={phone}")
        raw = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        for r in raw:
            s = re.sub(r'<[^>]+>', '', r).strip()
            s = re.sub(r'\s+', ' ', s)
            if len(s) > 20 and phone in s:
                snippets.append(s[:300])
    except:
        pass

    return snippets[:10]

# ==================== ПРОВЕРКА НИКА ====================
PLATFORMS = [
    ("VK", "https://vk.com/{}"),
    ("OK.ru", "https://ok.ru/{}"),
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

async def check_username(username: str) -> List[Tuple[str, str]]:
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
            if not chunk:
                break
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
                if not chunk:
                    break
                resp2 += chunk
            s2.close()
            return resp2.decode('utf-8', errors='ignore')[:800]
        else:
            return text[:800]
    except:
        return ""

# ==================== ОПРЕДЕЛЕНИЕ ТИПА ====================
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

# ==================== ГЛАВНЫЙ ПОИСК ====================
async def comprehensive_search(target: str, status_callback=None) -> Dict:
    report = {'target': target, 'type': detect_type(target)}

    if report['type'] == 'phone':
        if status_callback:
            await status_callback("1/4 Определение оператора...")
        report['phone_info'] = await phone_info(target)

        if status_callback:
            await status_callback("2/4 Поиск имён в базах номеров...")
        report['names'] = await find_names_by_phone(target)

        if status_callback:
            await status_callback("3/4 Поиск соцсетей...")
        report['social'] = await find_social_by_phone(target)

        if status_callback:
            await status_callback("4/4 Поиск упоминаний...")
        report['snippets'] = await find_snippets_by_phone(target)

    elif report['type'] == 'username':
        if status_callback:
            await status_callback("Поиск профилей по нику...")
        report['profiles'] = await check_username(target)

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

# ==================== ФОРМАТИРОВАНИЕ ОТЧЁТА ====================
def format_report(report: Dict) -> str:
    lines = [
        f"<b>╔══════════════════════════════════╗</b>\n"
        f"<b>║           ОТЧЁТ ПОИСКА           ║</b>\n"
        f"<b>╚══════════════════════════════════╝</b>\n\n"
        f"<b>🎯 Цель:</b> {report['target']}\n"
        f"<b>🕐 Время:</b> {datetime.now():%d.%m.%Y %H:%M:%S}\n"
        f"<b>📋 Тип:</b> {report.get('type', 'неизвестно')}\n"
        f"\n<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
    ]

    # Телефон
    if 'phone_info' in report and report['phone_info']:
        pi = report['phone_info']
        if pi:
            lines.append(f"\n<b>📞 ИНФОРМАЦИЯ О НОМЕРЕ</b>\n")
            if pi.get('operator'):
                lines.append(f"  • Оператор: <b>{pi['operator']}</b>")
            if pi.get('region'):
                lines.append(f"  • Регион: <b>{pi['region']}</b>")
            if pi.get('city'):
                lines.append(f"  • Город: <b>{pi['city']}</b>")
            if pi.get('country'):
                lines.append(f"  • Страна: <b>{pi['country']}</b>")

    if 'names' in report and report['names']:
        lines.append(f"\n<b>👤 ВОЗМОЖНЫЕ ВЛАДЕЛЬЦЫ (найдено в открытых базах):</b>\n")
        for i, name in enumerate(report['names'][:12], 1):
            lines.append(f"  {i}. {name}")

    if 'social' in report and report['social']:
        lines.append(f"\n<b>🌐 СВЯЗАННЫЕ ПРОФИЛИ:</b>\n")
        seen = set()
        for s in report['social']:
            if s['url'] not in seen:
                seen.add(s['url'])
                name_extra = f" — {s['name']}" if 'name' in s and s['name'] else ""
                lines.append(f"  • <a href='{s['url']}'>{s['platform']}</a>{name_extra}")

    if 'snippets' in report and report['snippets']:
        lines.append(f"\n<b>💬 УПОМИНАНИЯ В СЕТИ:</b>\n")
        for s in report['snippets'][:6]:
            lines.append(f"  • {s[:250]}")

    # Профили по нику
    if 'profiles' in report and report['profiles']:
        lines.append(f"\n<b>🌐 НАЙДЕННЫЕ ПРОФИЛИ:</b>\n")
        for platform, url in report['profiles']:
            lines.append(f"  • <a href='{url}'>{platform}</a>")

    # WHOIS
    if 'whois' in report and report['whois']:
        lines.append(f"\n<b>🌍 WHOIS:</b>\n<pre>{report['whois'][:600]}</pre>")

    lines.append(f"\n<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>")
    lines.append("<i>Данные получены исключительно из открытых источников.</i>")

    return '\n'.join(lines)

# ==================== КЛАВИАТУРА ====================
def consent_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, НАЧАТЬ ПОИСК", callback_data="ok")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="no")]
    ])

# ==================== ОБРАБОТЧИКИ ====================
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "<b>🔍 OSINT БОТ v3.0</b>\n\n"
        "<b>Что можно искать:</b>\n"
        "• 📞 Телефон: +77777777777\n"
        "• 👤 Никнейм: @username\n"
        "• 📧 Email: user@mail.ru\n"
        "• 🌐 Домен: example.com\n"
        "• 📝 Имя Фамилия\n\n"
        "<b>Источники:</b> открытые базы номеров, соцсети, WHOIS.\n"
        "Перед поиском запрашивается согласие.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle_input(msg: Message):
    target = msg.text.strip()
    if len(target) < 2:
        return

    sessions[msg.from_user.id] = {'target': target, 'time': time.time()}
    target_type = detect_type(target)

    type_names = {'phone': '📞 телефон', 'email': '📧 email', 'domain': '🌐 домен', 'username': '👤 никнейм', 'name': '📝 имя'}
    await msg.answer(
        f"<b>Цель:</b> {target}\n"
        f"<b>Тип:</b> {type_names.get(target_type, 'неизвестно')}\n\n"
        "Начать поиск в открытых источниках?",
        reply_markup=consent_kb(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "ok")
async def process_yes(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in sessions:
        await cb.answer("Сессия истекла. Отправьте запрос заново.", show_alert=True)
        return

    target = sessions[uid]['target']
    await cb.message.edit_text(f"<b>🔎 Поиск запущен:</b> {target}\n\nОжидайте, проверяю источники...", parse_mode=ParseMode.HTML)
    await cb.answer()

    status_msg = await cb.message.answer("⏳ Подготовка...")

    async def update_status(text):
        try:
            await status_msg.edit_text(f"⏳ {text}")
        except:
            pass

    report = await comprehensive_search(target, status_callback=update_status)

    try:
        await status_msg.delete()
    except:
        pass

    formatted = format_report(report)
    try:
        await cb.message.answer(formatted, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except:
        for part in [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]:
            await cb.message.answer(part, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.callback_query(F.data == "no")
async def process_no(cb: CallbackQuery):
    sessions.pop(cb.from_user.id, None)
    await cb.message.edit_text("<b>❌ Поиск отменён.</b>", parse_mode=ParseMode.HTML)
    await cb.answer("Отмена")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот v3.0 запущен. Поиск по прямым базам.")
    asyncio.run(main())