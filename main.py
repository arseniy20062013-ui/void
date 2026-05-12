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
sessions: Dict[int, Dict] = {}

# ==================== ОПРЕДЕЛЕНИЕ ТИПА ДАННЫХ ====================
def detect_type(text: str) -> str:
    text = text.strip()
    # Телефон
    if re.match(r'^[\+7|8]?\d{10,11}$', re.sub(r'[\s\-\(\)]', '', text)):
        return 'phone'
    # Email
    if re.match(r'[^@]+@[^@]+\.[^@]+', text):
        return 'email'
    # Домен/сайт
    if re.match(r'^[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', text):
        return 'domain'
    # Никнейм (начинается с @)
    if text.startswith('@'):
        return 'username'
    # Похоже на номер (цифры)
    if re.match(r'^\d{5,}$', re.sub(r'[\s\-\(\)]', '', text)):
        return 'phone'
    # Иначе имя/фамилия
    return 'name'

# ==================== ТЕЛЕФОН: ОПЕРАТОР/РЕГИОН ====================
async def lookup_phone(phone: str) -> Optional[Dict]:
    clean = re.sub(r'[^\d]', '', phone)
    if len(clean) == 11 and (clean.startswith('7') or clean.startswith('8')):
        clean = '7' + clean[1:] if clean.startswith('8') else clean
    elif len(clean) == 10:
        clean = '7' + clean
    else:
        return None
    try:
        url = f"https://htmlweb.ru/geo/api.php?json&telcod={clean}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            return {
                'country': data.get('country', {}).get('name', ''),
                'region': data.get('region', {}).get('name', ''),
                'operator': data.get('0', {}).get('oper', ''),
                'city': data.get('city', {}).get('name', ''),
                'timezone': data.get('timezone', ''),
            }
    except Exception as e:
        logging.warning(f"Phone lookup error: {e}")
    return None

# ==================== ПОИСК СВЯЗЕЙ ПО ТЕЛЕФОНУ ====================
async def search_phone_links(phone: str) -> Dict:
    """Возвращает всё, что найдено по телефону в открытых источниках"""
    result = {
        'social_profiles': [],
        'names': [],
        'addresses': [],
        'snippets': [],
        'urls': []
    }
    
    clean_phone = re.sub(r'[^\d]', '', phone)
    formatted_phone = phone
    
    queries = [
        f'"{phone}"',
        f'"{clean_phone}"',
        f'"{phone}" site:vk.com',
        f'"{phone}" site:ok.ru',
        f'"{phone}" site:avito.ru',
        f'"{phone}" site:youla.ru',
        f'"{phone}" site:2gis.ru',
        f'"{phone}" site:nomera.org',
        f'"{phone}" site:spravkaru.net',
    ]
    
    for query in queries[:5]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html',
                'Accept-Language': 'ru-RU,ru;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                clean_html = re.sub(r'<[^>]+>', ' ', html)
                clean_html = re.sub(r'\s+', ' ', clean_html)
                
                # Сниппеты
                for snippet_text in re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL):
                    clean_snippet = re.sub(r'<[^>]+>', '', snippet_text).strip()
                    clean_snippet = re.sub(r'\s+', ' ', clean_snippet)
                    if len(clean_snippet) > 20 and phone in clean_snippet:
                        result['snippets'].append(clean_snippet[:300])
                
                # Имена
                names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', clean_html)
                for name in names:
                    if len(name) > 8 and name not in ['Рейсы Путешествия Инструменты', 'Карты Новости Еще', 'Далее Конфиденциальность Условия', 'Все Изображения Видео']:
                        result['names'].append(name)
                
                # URL
                urls = re.findall(r'https?://[^\s<>"\']+', html)
                for u in urls:
                    if not any(skip in u for skip in ['google.com', 'yandex.ru', 'bing.com', 'duckduckgo.com']):
                        result['urls'].append(u)
                
                # Адреса
                addresses = re.findall(r'(?:ул\.|улица|пр\.|проспект|г\.|город)\s*[А-ЯЁ][а-яё\s\-\.\d]+', clean_html)
                result['addresses'].extend(addresses)
                
            await asyncio.sleep(1.5)
        except:
            continue
    
    # Определяем соцсети
    social_domains = {
        'vk.com': 'VK',
        'ok.ru': 'OK.ru',
        'facebook.com': 'Facebook',
        'instagram.com': 'Instagram',
        'twitter.com': 'Twitter/X',
        't.me': 'Telegram',
        'github.com': 'GitHub',
        'linkedin.com': 'LinkedIn',
        'habr.com': 'Habr',
        'youtube.com': 'YouTube',
        'tiktok.com': 'TikTok',
        'avito.ru': 'Avito',
        'youla.ru': 'Youla',
        '2gis.ru': '2GIS',
    }
    
    for url in result['urls']:
        for domain, name in social_domains.items():
            if domain in url and name not in [p['platform'] for p in result['social_profiles']]:
                result['social_profiles'].append({'platform': name, 'url': url})
    
    # Чистим дубликаты
    for key in ['names', 'addresses', 'snippets', 'social_profiles']:
        if key in result:
            seen = set()
            unique = []
            for item in result[key]:
                if isinstance(item, dict):
                    item_str = json.dumps(item)
                else:
                    item_str = item
                if item_str not in seen:
                    seen.add(item_str)
                    unique.append(item)
            result[key] = unique[:10]
    
    result['urls'] = list(set(result['urls']))[:10]
    
    return result

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

# ==================== ПОИСК ПРОФИЛЕЙ ПО НИКУ ====================
PLATFORMS = [
    ("VK", "https://vk.com/{}"),
    ("Facebook", "https://www.facebook.com/{}"),
    ("Instagram", "https://www.instagram.com/{}/"),
    ("Twitter/X", "https://twitter.com/{}"),
    ("GitHub", "https://github.com/{}"),
    ("YouTube", "https://www.youtube.com/@{}"),
    ("TikTok", "https://www.tiktok.com/@{}"),
    ("Reddit", "https://www.reddit.com/user/{}"),
    ("Habr", "https://habr.com/ru/users/{}/"),
    ("LinkedIn", "https://www.linkedin.com/in/{}"),
    ("Steam", "https://steamcommunity.com/id/{}"),
    ("Telegram", "https://t.me/{}"),
    ("OK.ru", "https://ok.ru/{}"),
    ("Pinterest", "https://www.pinterest.com/{}/"),
    ("SoundCloud", "https://soundcloud.com/{}"),
    ("Medium", "https://medium.com/@{}"),
    ("Behance", "https://www.behance.net/{}"),
    ("Dribbble", "https://dribbble.com/{}"),
    ("GitLab", "https://gitlab.com/{}"),
    ("Codecademy", "https://www.codecademy.com/profiles/{}"),
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
            with urllib.request.urlopen(req, timeout=5, context=ssl.create_default_context()) as resp:
                if resp.status == 200:
                    found.append((platform, url))
        except urllib.error.HTTPError as e:
            if e.code == 403:
                found.append((platform, url))
        except:
            continue
        await asyncio.sleep(0.15)
    return found

# ==================== ПОИСК ИМЕНИ ====================
async def search_name_info(name: str) -> Dict:
    result = {'abstract': '', 'profiles': [], 'urls': []}
    
    # DuckDuckGo Instant Answer
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(name)}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            abstract = data.get('AbstractText', '')
            if abstract:
                result['abstract'] = abstract
    except:
        pass
    
    # Поиск профилей
    result['profiles'] = await check_username(name.replace(' ', ''))
    
    return result

# ==================== ГЛАВНЫЙ ПОИСК ====================
async def comprehensive_search(target: str, status_callback=None) -> Dict:
    report = {'target': target, 'type': detect_type(target)}
    
    if report['type'] == 'phone':
        if status_callback: await status_callback("Определение оператора и региона...")
        report['phone_info'] = await lookup_phone(target)
        
        if status_callback: await status_callback("Поиск связей в интернете...")
        report['phone_links'] = await search_phone_links(target)
        
    elif report['type'] == 'username':
        if status_callback: await status_callback("Поиск профилей по нику...")
        report['profiles'] = await check_username(target)
        
    elif report['type'] == 'name':
        if status_callback: await status_callback("Поиск информации по имени...")
        report['name_info'] = await search_name_info(target)
        
    elif report['type'] == 'domain':
        if status_callback: await status_callback("WHOIS запрос...")
        report['whois'] = whois_domain(target)
        
    elif report['type'] == 'email':
        domain = target.split('@')[-1]
        if status_callback: await status_callback("WHOIS домена...")
        report['whois'] = whois_domain(domain)
    
    return report

# ==================== ФОРМАТ ОТЧЁТА ====================
def format_report(report: Dict) -> str:
    lines = [
        f"<b>ОТЧЁТ ПОИСКА</b>\n"
        f"<b>Цель:</b> {report['target']}\n"
        f"<b>Время:</b> {datetime.now():%d.%m.%Y %H:%M:%S}\n"
        f"<b>Тип:</b> {report.get('type', 'неизвестно')}\n"
        f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
    ]
    
    # Телефон
    if 'phone_info' in report and report['phone_info']:
        pi = report['phone_info']
        lines.append(f"<b>📞 ТЕЛЕФОН:</b>")
        lines.append(f"• Оператор: {pi.get('operator', 'неизвестно')}")
        lines.append(f"• Регион: {pi.get('region', 'неизвестно')}")
        lines.append(f"• Город: {pi.get('city', 'неизвестно')}")
        lines.append(f"• Страна: {pi.get('country', 'неизвестно')}")
        if pi.get('timezone'):
            lines.append(f"• Часовой пояс: {pi['timezone']}")
        lines.append("")
    
    # Связи телефона
    if 'phone_links' in report:
        pl = report['phone_links']
        
        if pl.get('names'):
            lines.append("<b>👤 ВОЗМОЖНЫЕ ИМЕНА:</b>")
            for name in pl['names'][:7]:
                lines.append(f"• {name}")
            lines.append("")
        
        if pl.get('social_profiles'):
            lines.append("<b>🌐 СОЦСЕТИ:</b>")
            for profile in pl['social_profiles']:
                lines.append(f"• {profile['platform']}: {profile['url']}")
            lines.append("")
        
        if pl.get('addresses'):
            lines.append("<b>📍 АДРЕСА:</b>")
            for addr in pl['addresses'][:5]:
                lines.append(f"• {addr}")
            lines.append("")
        
        if pl.get('snippets'):
            lines.append("<b>📝 УПОМИНАНИЯ:</b>")
            for snippet in pl['snippets'][:5]:
                lines.append(f"• {snippet[:250]}")
            lines.append("")
    
    # Профили по нику
    if 'profiles' in report and report['profiles']:
        lines.append("<b>🌐 НАЙДЕННЫЕ ПРОФИЛИ:</b>")
        for platform, url in report['profiles']:
            lines.append(f"• <a href='{url}'>{platform}</a>")
        lines.append("")
    
    # Информация по имени
    if 'name_info' in report:
        ni = report['name_info']
        if ni.get('abstract'):
            lines.append(f"<b>📚 ИНФОРМАЦИЯ:</b>\n{ni['abstract']}\n")
        if ni.get('profiles'):
            lines.append("<b>🌐 ПРОФИЛИ:</b>")
            for platform, url in ni['profiles']:
                lines.append(f"• <a href='{url}'>{platform}</a>")
            lines.append("")
    
    # WHOIS
    if 'whois' in report and report['whois']:
        lines.append(f"<b>🌍 WHOIS:</b>\n<pre>{report['whois'][:500]}</pre>\n")
    
    lines.append("<b>━━━━━━━━━━━━━━━━━━</b>")
    lines.append("Данные получены из открытых источников.")
    
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
        "<b>🔍 OSINT БОТ v2.0</b>\n\n"
        "Отправьте мне:\n"
        "• Телефон: +77777777777\n"
        "• Никнейм: @username\n"
        "• Email: user@mail.ru\n"
        "• Домен: example.com\n"
        "• Имя: Иванов Иван\n\n"
        "Бот автоматически определит тип данных и найдёт информацию в открытых источниках.\n"
        "Перед каждым поиском запрашивается подтверждение.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle_input(msg: Message):
    target = msg.text.strip()
    if len(target) < 2:
        return
    
    target_type = detect_type(target)
    sessions[msg.from_user.id] = {'target': target, 'type': target_type, 'time': time.time()}
    
    type_names = {
        'phone': 'телефон',
        'email': 'email',
        'domain': 'домен',
        'username': 'никнейм',
        'name': 'имя'
    }
    
    await msg.answer(
        f"<b>🎯 Цель:</b> {target}\n"
        f"<b>📋 Тип:</b> {type_names.get(target_type, 'неизвестно')}\n\n"
        "Начинаем поиск в открытых источниках.\n"
        "Вы подтверждаете, что имеете право искать эту информацию?",
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
    await cb.message.edit_text(f"<b>🔎 Идёт поиск:</b> {target}\n\nПожалуйста, подождите...", parse_mode=ParseMode.HTML)
    await cb.answer()
    
    status_msg = await cb.message.answer("⏳ Запуск поиска...")
    
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
    print("Бот запущен.")
    asyncio.run(main())