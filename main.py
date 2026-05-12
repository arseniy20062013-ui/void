import asyncio
import logging
import re
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

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)
sessions: Dict[int, dict] = {}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
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
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.5',
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
    """Извлекает последовательности кириллических слов, похожие на ФИО"""
    names = re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?', html)
    # фильтр коротких и мусорных
    result = []
    for n in names:
        n = n.strip()
        if len(n) > 8 and not re.search(r'(?i)(google|yandex|помощь|поддержка|войти|регистрация|пароль|страниц|сервис|поиск|вход|личный|кабинет|интернет|магазин|доставка|оплата|корзина|товар|реклама|конфиденциальность|условия|использование|соглашение|карты|новости|изображения|видео|рейсы|путешествия|инструменты|далее)', n):
            result.append(n)
    return list(set(result))

def filter_garbage(names: List[str]) -> List[str]:
    garbage_words = [
        'рейсы', 'путешествия', 'инструменты', 'карты', 'новости', 'далее',
        'конфиденциальность', 'условия', 'все', 'изображения', 'видео',
        'поиск', 'картинки', 'google', 'play', 'app', 'store', 'регистрация',
        'забыли', 'пароль', 'показать', 'результаты', 'поисковая', 'система',
        'интернет', 'магазин', 'служба', 'поддержки', 'личный', 'кабинет',
        'мобильная', 'версия', 'полная', 'версия', 'обратная', 'связь',
        'пользовательское', 'соглашение', 'политика', 'конфиденциальности',
        'все', 'права', 'защищены', 'создать', 'сайт', 'бесплатный', 'конструктор'
    ]
    clean = []
    for name in names:
        parts = name.lower().split()
        if not any(part in garbage_words for part in parts):
            clean.append(name)
    return clean

# ==================== ТЕЛЕФОН: ОПЕРАТОР / РЕГИОН ====================
async def phone_operator_info(phone: str) -> dict:
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

# ==================== ПОИСК ИМЕН ПО НОМЕРУ НА САЙТАХ-ОПРЕДЕЛИТЕЛЯХ ====================
async def search_names_on_sites(phone: str) -> List[str]:
    clean = normalize_phone(phone)
    all_names = []

    # Список сайтов: URL + функция парсинга (по умолчанию extract_names)
    sites = [
        f"https://num.voxlink.ru/{clean}/",
        f"https://callfilter.ru/{clean}",
        f"https://ktozvonit.com/{clean}",
        f"https://nomera.org/telefon/{clean}",
        f"https://spravkaru.net/{clean}",
        f"https://neberitrubku.ru/nomer/{clean}",
        f"https://kto-zvonil.ru/nomer/{clean}",
    ]

    for url in sites:
        try:
            html = await asyncio.to_thread(fetch, url)
            names = extract_names(html)
            all_names.extend(names)
        except:
            continue
        await asyncio.sleep(0.2)  # небольшая задержка

    return filter_garbage(all_names)

# ==================== ПОИСК ПРОФИЛЕЙ ВК И ОК ПО НОМЕРУ ====================
async def search_social_profiles(phone: str) -> List[dict]:
    clean = normalize_phone(phone)
    profiles = []

    # VK
    try:
        html = await asyncio.to_thread(
            fetch, f"https://vk.com/search?c%5Bphone%5D={clean}&c%5Bsection%5D=people"
        )
        vk_ids = re.findall(r'href="/(id\d+)"', html)
        for vk_id in list(set(vk_ids)):
            profiles.append({'platform': 'VK', 'url': f'https://vk.com/{vk_id}'})
    except:
        pass

    # OK
    try:
        html = await asyncio.to_thread(
            fetch, f"https://ok.ru/dk?cmd=Search&st.query={clean}"
        )
        ok_ids = re.findall(r'href="(/profile/\d+)"', html)
        for ok_id in list(set(ok_ids)):
            profiles.append({'platform': 'OK', 'url': f'https://ok.ru{ok_id}'})
    except:
        pass

    return profiles

# ==================== ПОИСК УПОМИНАНИЙ (СНИППЕТЫ) ====================
async def search_snippets(query: str) -> List[str]:
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        html = await asyncio.to_thread(fetch, url)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        clean_snippets = []
        for s in snippets:
            text = re.sub(r'<[^>]+>', '', s).strip()
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 20 and query in text:
                clean_snippets.append(text[:250])
        return clean_snippets[:5]
    except:
        return []

# ==================== ГЛАВНЫЙ ПОИСК ====================
async def full_search(target: str, status_callback=None) -> dict:
    report = {'target': target, 'type': 'phone'}

    # 1. Оператор/регион
    if status_callback: await status_callback("1/3 Определение оператора...")
    report['operator_info'] = await phone_operator_info(target)

    # 2. Имена с сайтов-определителей
    if status_callback: await status_callback("2/3 Поиск имён владельца...")
    report['names'] = await search_names_on_sites(target)

    # 3. Соцсети
    if status_callback: await status_callback("3/3 Поиск профилей в соцсетях...")
    report['social'] = await search_social_profiles(target)

    # 4. Сниппеты (упоминания)
    report['snippets'] = await search_snippets(target)

    return report

# ==================== ФОРМАТИРОВАНИЕ ОТЧЁТА ====================
def format_report(report: dict) -> str:
    lines = [
        "🔎 <b>РЕЗУЛЬТАТЫ ПОИСКА</b>",
        f"📞 Номер: <code>{report['target']}</code>",
        f"🕒 Время: {datetime.now():%d.%m.%Y %H:%M:%S}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    op = report.get('operator_info', {})
    if op:
        lines.append("📡 <b>Оператор/Регион:</b>")
        lines.append(f"   • Оператор: {op.get('operator') or 'неизвестно'}")
        lines.append(f"   • Регион: {op.get('region') or 'неизвестно'}")
        lines.append(f"   • Город: {op.get('city') or 'неизвестно'}")

    names = report.get('names', [])
    if names:
        lines.append(f"👤 <b>Вероятные имена владельца (из открытых баз):</b>")
        for i, name in enumerate(names[:15], 1):
            lines.append(f"   {i}. {name}")
    else:
        lines.append("👤 <b>Имена:</b> не найдены в открытых источниках")

    social = report.get('social', [])
    if social:
        lines.append(f"🌐 <b>Связанные профили в соцсетях:</b>")
        for s in social:
            lines.append(f"   • <a href='{s['url']}'>{s['platform']}</a>")
    else:
        lines.append("🌐 <b>Профили:</b> не найдены")

    snippets = report.get('snippets', [])
    if snippets:
        lines.append(f"💬 <b>Упоминания в поиске:</b>")
        for snip in snippets:
            lines.append(f"   • {snip}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Данные собраны исключительно из открытых публичных источников.</i>")
    return '\n'.join(lines)

# ==================== КЛАВИАТУРА СОГЛАСИЯ ====================
def consent_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, ПРОДОЛЖИТЬ", callback_data="ok")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="no")]
    ])

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🔎 <b>БОТ ПОИСКА ПО НОМЕРУ ТЕЛЕФОНА</b>\n\n"
        "Отправьте номер в любом формате, например:\n"
        "<code>+7777777777</code>\n\n"
        "Бот проверит открытые базы имён и соцсетей.\n"
        "Перед поиском потребуется ваше согласие.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle_message(msg: Message):
    target = msg.text.strip()
    if not target:
        return

    # проверяем, что похоже на телефон
    digits = re.sub(r'\D', '', target)
    if len(digits) < 10:
        await msg.answer("Пожалуйста, отправьте номер телефона (не менее 10 цифр).")
        return

    sessions[msg.from_user.id] = {'target': target, 'time': time.time()}
    await msg.answer(
        f"🎯 Номер: <code>{target}</code>\n\n"
        "Запустить поиск по открытым источникам?",
        reply_markup=consent_kb(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "ok")
async def process_ok(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in sessions:
        await cb.answer("Сессия истекла. Отправьте номер ещё раз.", show_alert=True)
        return

    target = sessions[uid]['target']
    await cb.message.edit_text(f"⏳ Идёт поиск для <code>{target}</code>...", parse_mode=ParseMode.HTML)
    await cb.answer()

    status_msg = await cb.message.answer("🔄 Подготовка...")

    async def update_status(text: str):
        try:
            await status_msg.edit_text(f"🔄 {text}")
        except:
            pass

    report = await full_search(target, status_callback=update_status)
    await status_msg.delete()

    result_text = format_report(report)
    # Разбиваем, если больше 4000 символов
    try:
        await cb.message.answer(result_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except:
        for chunk in [result_text[i:i+4000] for i in range(0, len(result_text), 4000)]:
            await cb.message.answer(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@dp.callback_query(F.data == "no")
async def process_no(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid in sessions:
        del sessions[uid]
    await cb.message.edit_text("❌ Поиск отменён.")
    await cb.answer("Отмена")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот запущен. Полный пробив через открытые источники.")
    asyncio.run(main())