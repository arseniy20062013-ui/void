import asyncio
import aiohttp
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
DADATA_API_KEY = "b65c4cec7c29d56935abf05a05e534cea7b2075c"
DADATA_SECRET_KEY = "1ae34aebd98f740bda338b963a1ee3f13425b8e4"

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

async def probe_dadata(phone: str) -> dict:
    """Основной пробив через DaData"""
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
                        "op": r.get("provider") or "?",
                        "region": r.get("region", "?"),
                        "city": r.get("city", "?"),
                        "tz": r.get("timezone", "UTC+0"),
                        "type": r.get("type", "?")
                    }
    except:
        pass
    return None

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🛡 <b>ПРОБИВ ПО НОМЕРУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Отправь номер в любом формате.\n"
        "Получишь: оператора, регион, город, часовой пояс и ссылки на ручной поиск.",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_input(msg: Message):
    target = msg.text.strip()
    digits = re.sub(r'\D', '', target)
    if len(digits) < 10:
        await msg.answer("❌ Нужно минимум 10 цифр.")
        return

    # Форматируем под российский номер
    if len(digits) == 11 and (digits[0] == '7' or digits[0] == '8'):
        phone = digits[-10:]
    elif len(digits) == 10:
        phone = digits
    else:
        phone = digits[-10:]

    user_sessions[msg.from_user.id] = phone

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 ПРОБИТЬ", callback_data="start_scan")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
    ])

    await msg.answer(
        f"🎯 <b>ЦЕЛЬ:</b> <code>+7 {phone}</code>\n"
        "Начать сбор данных?",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "start_scan")
async def start_scan(cb: CallbackQuery):
    phone = user_sessions.get(cb.from_user.id)
    if not phone:
        await cb.answer("Сессия истекла. Отправь номер заново.", show_alert=True)
        return

    msg = await cb.message.edit_text("⏳ <b>Сканируем DaData...</b>", parse_mode=ParseMode.HTML)

    info = await probe_dadata(phone)

    if info:
        report = (
            f"🕵️‍♂️ <b>РЕЗУЛЬТАТЫ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📞 <b>Номер:</b> <code>+{info['phone']}</code>\n"
            f"📡 <b>Оператор:</b> {info['op']} ({info['type']})\n"
            f"📍 <b>Регион:</b> {info['region']}\n"
            f"🏙 <b>Город:</b> {info['city']}\n"
            f"⏰ <b>Часовой пояс:</b> {info['tz']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Ручной поиск в утечках:</b>\n"
            f"└ <a href='https://t.me/GlazBogaOfficial_bot?start=+7{phone}'>Глаз Бога</a>\n"
            f"└ <a href='https://t.me/maikls_bot?start=+7{phone}'>Maikls</a>\n"
            f"└ <a href='https://t.me/HGB94836385_bot?start=+7{phone}'>HGBot</a>\n"
            f"└ <a href='https://t.me/x8152384_bot?start=+7{phone}'>x8152384</a>\n"
            f"└ <a href='https://vk.com/search?c[section]=people&c[phone]=+7{phone}'>VK</a>\n"
            f"└ <a href='https://www.google.com/search?q=\"+7{phone}\"'>Google</a>"
        )
        await msg.edit_text(report, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        await msg.edit_text("❌ <b>DaData не ответил.</b> Попробуй позже.")

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