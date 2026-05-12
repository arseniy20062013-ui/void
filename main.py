import asyncio
import logging
import re
import json
import time
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
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
]

def normalize_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits[0] in '78':
        return '7' + digits[1:] if digits[0] == '8' else digits
    if len(digits) == 10:
        return '7' + digits
    return digits

def fetch(url: str, timeout: int = 15) -> str:
    headers = {
        'User-Agent': USER_AGENTS[int(time.time()) % len(USER_AGENTS)],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.5',
        'Accept-Encoding': 'identity',
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

def extract_names(html: str) -> List[str]:
    html_clean = re.sub(r'<[^>]+>', ' ', html)
    html_clean = re.sub(r'\s+', ' ', html_clean)
    names = re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?', html_clean)
    garbage = {
        'google', 'yandex', 'помощь', 'поддержка', 'войти', 'регистрация', 'пароль',
        'страниц', 'сервис', 'поиск', 'вход', 'личный', 'кабинет', 'интернет',
        'магазин', 'доставка', 'оплата', 'корзина', 'товар', 'реклама',
        'конфиденциальность', 'условия', 'использование', 'соглашение', 'карты',
        'новости', 'изображения', 'видео', 'рейсы', 'путешествия', 'инструменты',
        'далее', 'приложение', 'установить', 'скачать', 'бесплатно', 'подробнее',
        'читать', 'смотреть', 'слушать', 'перейти', 'назад', 'вперёд', 'отправить',
        'сообщение', 'комментарий', 'ответить', 'поделиться', 'сохранить',
        'пожаловаться', 'заблокировать', 'позвонить', 'написать', 'заказать',
        'купить', 'продать', 'обменять', 'снять', 'арендовать', 'забронировать',
    }
    result = []
    for n in names:
        n = n.strip()
        if len(n) >= 8:
            parts = set(n.lower().split())
            if not parts.intersection(garbage):
                result.append(n)
    return list(set(result))

# ==================== ОПЕРАТОР/РЕГИОН ====================
async def get_operator_info(phone: str) -> dict:
    clean = normalize_phone(phone)
    info = {'operator': '', 'region': '', 'city': ''}
    if not clean:
        return info
    try:
        url = f"https://htmlweb.ru/geo/api.php?json&telcod={clean}"
        data = json.loads(fetch(url))
        info['operator'] = data.get('0', {}).get('oper', '')
        info['region'] = data.get('region', {}).get('name', '')
        info['city'] = data.get('city', {}).get('name', '')
    except:
        pass
    return info

# ==================== ПОИСК ИМЁН ====================
async def find_names(phone: str) -> List[str]:
    clean = normalize_phone(phone)
    all_names = []

    sites = [
        f"https://num.voxlink.ru/{clean}/",
        f"https://callfilter.ru/{clean}",
        f"https://ktozvonit.com/{clean}",
        f"https://nomera.org/telefon/{clean}",
        f"https://spravkaru.net/{clean}",
        f"https://neberitrubku.ru/nomer/{clean}",
        f"https://kto-zvonil.ru/nomer/{clean}",
        f"https://www.telefonnyjdovidnyk.com.ua/nomer/{clean}",
        f"https://phoneradar.ru/phone/{clean}",
    ]

    for url in sites:
        try:
            html = fetch(url)
            names = extract_names(html)
            all_names.extend(names)
        except:
            continue
        await asyncio.sleep(0.5)

    return list(set(all_names))

# ==================== ПОИСК В СОЦСЕТЯХ ====================
async def find_social(phone: str) -> List[dict]:
    clean = normalize_phone(phone)
    profiles = []

    # VK
    try:
        html = fetch(f"https://vk.com/search?c%5Bphone%5D={clean}&c%5Bsection%5D=people")
        ids = re.findall(r'href="/(id\d+)"', html)
        for id_ in list(set(ids)):
            profiles.append({'platform': 'VK', 'url': f'https://vk.com/{id_}'})
    except:
        pass

    # OK
    try:
        html = fetch(f"https://ok.ru/dk?cmd=Search&st.query={clean}")
        ids = re.findall(r'href="(/profile/\d+)"', html)
        for id_ in list(set(ids)):
            profiles.append({'platform': 'OK', 'url': f'https://ok.ru{id_}'})
    except:
        pass

    return profiles

# ==================== СНИППЕТЫ ====================
async def find_snippets(phone: str) -> List[str]:
    encoded = urllib.parse.quote(phone)
    try:
        html = fetch(f"https://html.duckduckgo.com/html/?q={encoded}")
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        result = []
        for s in snippets:
            text = re.sub(r'<[^>]+>', '', s).strip()
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 15 and phone in text:
                result.append(text[:250])
        return result[:5]
    except:
        return []

# ==================== ГЛАВНЫЙ ПОИСК ====================
async def full_search(phone: str, status_callback=None) -> dict:
    report = {'phone': phone}

    if status_callback:
        await status_callback("1/3 Определение оператора...")
    report['operator'] = await get_operator_info(phone)

    if status_callback:
        await status_callback("2/3 Поиск имён...")
    report['names'] = await find_names(phone)

    if status_callback:
        await status_callback("3/3 Поиск соцсетей...")
    report['social'] = await find_social(phone)

    report['snippets'] = await find_snippets(phone)
    return report

# ==================== ФОРМАТИРОВАНИЕ ====================
def format_report(r: dict) -> str:
    lines = [
        "🔎 <b>РЕЗУЛЬТАТЫ ПОИСКА</b>",
        f"📞 Номер: <code>{r['phone']}</code>",
        f"🕒 Время: {datetime.now():%d.%m.%Y %H:%M:%S}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    op = r.get('operator', {})
    lines.append("📡 <b>Оператор/Регион:</b>")
    lines.append(f"   • Оператор: {op.get('operator') or 'неизвестно'}")
    lines.append(f"   • Регион: {op.get('region') or 'неизвестно'}")
    lines.append(f"   • Город: {op.get('city') or 'неизвестно'}")

    names = r.get('names', [])
    if names:
        lines.append(f"👤 <b>Вероятные имена ({len(names)}):</b>")
        for i, n in enumerate(names[:15], 1):
            lines.append(f"   {i}. {n}")
    else:
        lines.append("👤 <b>Имена:</b> не найдены")

    social = r.get('social', [])
    if social:
        lines.append(f"🌐 <b>Соцсети:</b>")
        for s in social:
            lines.append(f"   • <a href='{s['url']}'>{s['platform']}</a>")
    else:
        lines.append("🌐 <b>Соцсети:</b> не найдены")

    snippets = r.get('snippets', [])
    if snippets:
        lines.append(f"💬 <b>Упоминания:</b>")
        for s in snippets:
            lines.append(f"   • {s}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Данные из открытых источников. Согласие получено.</i>")
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
        "🔎 <b>ПОИСК ПО НОМЕРУ ТЕЛЕФОНА</b>\n\n"
        "Отправьте номер:\n"
        "<code>+7777777777</code>\n\n"
        "Бот найдёт оператора, регион, возможные имена и соцсети.\n"
        "<i>Только открытые данные. Требуется согласие.</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle(msg: Message):
    target = msg.text.strip()
    digits = re.sub(r'\D', '', target)
    if len(digits) < 10:
        await msg.answer("Отправьте номер (минимум 10 цифр).")
        return

    sessions[msg.from_user.id] = {'target': target, 'time': time.time()}
    await msg.answer(
        f"🎯 Номер: <code>{target}</code>\n\nЗапустить поиск по открытым источникам?",
        reply_markup=consent_kb(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "ok")
async def ok(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in sessions:
        await cb.answer("Сессия истекла.", show_alert=True)
        return

    target = sessions[uid]['target']
    await cb.message.edit_text(f"⏳ Поиск: <code>{target}</code>...", parse_mode=ParseMode.HTML)
    await cb.answer()

    status_msg = await cb.message.answer("🔄 Старт...")

    async def update(s):
        try:
            await status_msg.edit_text(f"🔄 {s}")
        except:
            pass

    report = await full_search(target, status_callback=update)
    await status_msg.delete()

    text = format_report(report)
    try:
        await cb.message.answer(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await cb.message.answer(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.callback_query(F.data == "no")
async def no(cb: CallbackQuery):
    sessions.pop(cb.from_user.id, None)
    await cb.message.edit_text("❌ Поиск отменён.")
    await cb.answer("Отмена")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот запущен.")
    asyncio.run(main())