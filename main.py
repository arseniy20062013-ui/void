import asyncio
import aiohttp
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

# Твои данные
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
DADATA_API_KEY = "b65c4cec7c29d56935abf05a05e534cea7b2075c"
DADATA_SECRET_KEY = "1ae34aebd98f740bda338b963a1ee3f13425b8e4"

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

async def get_extended_info(phone: str):
    """Сбор данных через DaData"""
    url = "https://cleaner.dadata.ru/api/v1/clean/phone"
    headers = {
        "Authorization": f"Token {DADATA_API_KEY}",
        "X-Secret": DADATA_SECRET_KEY,
        "Content-Type": "application/json"
    }
    clean_phone = re.sub(r'\D', '', phone)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=[clean_phone]) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    res = data[0]
                    return {
                        "phone": res.get("phone"),
                        "op": res.get("network") or res.get("provider") or "Не определен",
                        "reg": res.get("region") or "Неизвестно",
                        "city": res.get("city") or "Не указан",
                        "tz": res.get("timezone") or "UTC+0",
                        "type": res.get("type", "Мобильный")
                    }
    except Exception as e:
        print(f"Error: {e}")
    return None

@dp.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(
        "📞 <b>Проверка номера телефона</b>\n"
        "Отправьте номер, чтобы узнать регион, оператора и часовой пояс.",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_msg(msg: Message):
    target = msg.text.strip()
    user_sessions[msg.from_user.id] = target

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Проверить номер", callback_data="start_scan")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

    await msg.answer(
        f"📞 <b>Номер:</b> <code>{target}</code>\n"
        "Нажмите «Проверить», чтобы узнать информацию.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "start_scan")
async def start_scan(cb: CallbackQuery):
    target = user_sessions.get(cb.from_user.id)
    msg = await cb.message.edit_text("⏳ Проверяю номер...", parse_mode=ParseMode.HTML)

    info = await get_extended_info(target)

    if info:
        report = (
            f"📋 <b>Информация о номере</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📞 <b>Номер:</b> <code>+{info['phone']}</code>\n"
            f"📡 <b>Оператор:</b> {info['op']} ({info['type']})\n"
            f"📍 <b>Регион:</b> {info['reg']}\n"
            f"🏙 <b>Город:</b> {info['city']}\n"
            f"⏰ <b>Часовой пояс:</b> {info['tz']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"ℹ️ Это открытые данные, доступные любому."
        )
        await msg.edit_text(report, parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text("❌ Не удалось проверить номер. Попробуйте позже.")
    await cb.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery):
    await cb.message.edit_text("❌ Проверка отменена.")
    await cb.answer()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())