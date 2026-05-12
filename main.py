import asyncio, logging, re, json, time, socket, ssl, urllib.request, urllib.parse
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

# ==================== ТЕЛЕФОН ====================
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
            }
    except Exception as e:
        logging.warning(f"Phone error: {e}")
    return None

# ==================== EMAIL: WHOIS домена + MX ====================
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
            return resp2.decode('utf-8', errors='ignore')[:500]
        else:
            return text[:500]
    except:
        return ""

def check_mx(domain: str) -> List[str]:
    try:
        import smtplib
        from email.utils import parseaddr
        # Простая проверка MX записи через socket
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        return [str(r.exchange) for r in answers]
    except:
        try:
            # fallback: через smtplib (не всегда работает)
            import smtplib
            mx = smtplib.SMTP()
            mx.connect(domain)
            mx.quit()
            return ["SMTP доступен"]
        except:
            return []

# ==================== ПОИСК EMAIL В DUCKDUCKGO (ЧИСТЫЕ СНИППЕТЫ) ====================
async def search_email_snippets(email: str) -> List[str]:
    snippets = []
    # Экранируем email для URL
    query = urllib.parse.quote(f'"{email}"')
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            # Ищем блоки результатов: <a class="result__snippet"...>текст</a>
            # В DuckDuckGo HTML сниппеты лежат в <a class="result__snippet">
            raw_snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            for s in raw_snippets:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                clean = re.sub(r'\s+', ' ', clean)
                if len(clean) > 20 and email.lower() in clean.lower():
                    snippets.append(clean)
            return snippets[:5]
    except Exception as e:
        logging.warning(f"Email search error: {e}")
    return snippets

# ==================== ПРОВЕРКА ПРОФИЛЕЙ ПО НИКУ ====================
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
]

async def check_username(username: str) -> List[Tuple[str, str]]:
    found = []
    username = username.lstrip('@')
    if not username: return found
    for platform, url_template in PLATFORMS:
        url = url_template.format(username)
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'Mozilla/5.0')
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    found.append((platform, url))
        except urllib.error.HTTPError as e:
            if e.code in (403, 200):
                found.append((platform, url))
        except:
            continue
        await asyncio.sleep(0.1)
    return found

# ==================== ПОИСК ИМЕНИ В DUCKDUCKGO ====================
async def search_name(name: str) -> Optional[str]:
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(name)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            abstract = data.get('AbstractText', '')
            if abstract:
                return abstract
    except:
        pass
    return None

# ==================== ГЛАВНЫЙ ПОИСК ====================
async def comprehensive_search(target: str, status_callback=None) -> Dict:
    report = {'target': target}
    target = target.strip()

    # Телефон?
    if re.match(r'^[\+7|8]?\d{10,11}$', re.sub(r'[\s\-\(\)]', '', target)):
        report['type'] = 'phone'
        if status_callback: await status_callback("Определение оператора...")
        report['phone_info'] = await lookup_phone(target)

    # Email?
    elif re.match(r'[^@]+@[^@]+\.[^@]+', target):
        report['type'] = 'email'
        domain = target.split('@')[-1]
        if status_callback: await status_callback("WHOIS домена...")
        report['whois'] = whois_domain(domain)
        if status_callback: await status_callback("Поиск сниппетов в интернете...")
        report['snippets'] = await search_email_snippets(target)

    # Домен?
    elif re.match(r'^[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', target):
        report['type'] = 'domain'
        if status_callback: await status_callback("WHOIS запрос...")
        report['whois'] = whois_domain(target)

    # Иначе ник или имя
    else:
        report['type'] = 'username_name'
        if status_callback: await status_callback("Поиск профилей...")
        report['profiles'] = await check_username(target)
        if status_callback: await status_callback("Поиск упоминаний...")
        report['abstract'] = await search_name(target)

    return report

# ==================== ФОРМАТ ОТЧЁТА ====================
def format_report(report: Dict) -> str:
    lines = [
        f"<b>ОТЧЁТ ПОИСКА</b>\n"
        f"Цель: {report['target']}\n"
        f"Время: {datetime.now():%d.%m.%Y %H:%M:%S}\n"
        f"Тип: {report.get('type', 'неизвестно')}\n"
        f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
    ]
    if 'phone_info' in report:
        pi = report['phone_info']
        if pi:
            lines.append(f"<b>Телефон:</b>\n• Оператор: {pi['operator']}\n• Регион: {pi['region']}\n• Страна: {pi['country']}\n")
        else:
            lines.append("Телефон: не удалось определить.\n")

    if 'whois' in report and report['whois']:
        lines.append(f"<b>WHOIS домена:</b>\n<pre>{report['whois']}</pre>\n")

    if 'snippets' in report and report['snippets']:
        lines.append("<b>Упоминания email в интернете:</b>")
        for s in report['snippets']:
            lines.append(f"• {s}")
        lines.append("")

    if 'profiles' in report:
        lines.append("<b>Найденные профили:</b>")
        for platform, url in report['profiles']:
            lines.append(f"• <a href='{url}'>{platform}</a>")

    if 'abstract' in report and report['abstract']:
        lines.append(f"<b>Краткая информация:</b>\n{report['abstract']}")

    lines.append("\n<b>━━━━━━━━━━━━━━━━━━</b>\nДанные из открытых источников.")
    return '\n'.join(lines)

# ==================== КЛАВИАТУРА ====================
def consent_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, ПРОДОЛЖИТЬ", callback_data="ok")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="no")]
    ])

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🔍 <b>OSINT БОТ</b>\n\n"
        "Отправьте телефон, email, никнейм или домен.\n"
        "Без API-ключей, только публичные данные.\n"
        "Перед поиском запрашивается согласие.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle_input(msg: Message):
    target = msg.text.strip()
    if len(target) < 2: return
    sessions[msg.from_user.id] = {'target': target, 'time': time.time()}
    await msg.answer(
        f"🎯 <b>Цель:</b> {target}\n\n"
        "Начинаем поиск. Подтвердите согласие.",
        reply_markup=consent_kb(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "ok")
async def process_yes(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in sessions:
        await cb.answer("Сессия истекла.", show_alert=True)
        return
    target = sessions[uid]['target']
    await cb.message.edit_text(f"🔎 Идёт поиск: <b>{target}</b>\nОжидайте...", parse_mode=ParseMode.HTML)
    await cb.answer()
    status_msg = await cb.message.answer("⏳ Старт...")

    async def update(text):
        try: await status_msg.edit_text(f"⏳ {text}")
        except: pass

    report = await comprehensive_search(target, status_callback=update)
    await status_msg.delete()
    formatted = format_report(report)
    try:
        await cb.message.answer(formatted, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except:
        for part in [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]:
            await cb.message.answer(part, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.callback_query(F.data == "no")
async def process_no(cb: CallbackQuery):
    sessions.pop(cb.from_user.id, None)
    await cb.message.edit_text("Поиск отменён.")
    await cb.answer("Отмена")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот без HIBP запущен.")
    asyncio.run(main())