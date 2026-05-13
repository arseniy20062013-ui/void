import asyncio
import aiohttp
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

# Данные со скриншота 1000019834.jpg
TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"
DADATA_API_KEY = "b65c4cec7c29d56935abf05a05e534cea7b2075c"
DADATA_SECRET_KEY = "1ae34aebd98f740bda338b963a1ee3f13425b8e4"

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_sessions = {}

async def get_dadata_info(phone: str):
    """Запрос к DaData для получения города, региона и оператора"""
    url = "https://cleaner.dadata.ru/api/v1/clean/phone"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {DADATA_API_KEY}",
        "X-Secret": DADATA_SECRET_KEY
    }
    # Очистка номера для API
    clean_phone = re.sub(r'\D', '', phone)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=[clean_phone]) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    res = data[0]
                    return {
                        "operator": res.get("network", "Неизвестно"),
                        "region": res.get("region", "Неизвестно"),
                        "city": res.get("city", "Не определен"),
                        "tz": res.get("timezone", "UTC")
                    }
    except Exception as e:
        print(f"Ошибка API: {e}")
    return None

@dp.message(F.text)
async def handle_input(msg: Message):
    target = msg.text.strip()
    user_sessions[msg.from_user.id] = target
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю согласие", callback_data="run")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="stop")]
    ])
    
    await msg.answer(
        f"🎯 <b>Цель:</b> <code>{target}</code>\n\n"
        "Подтвердите, что вы проверяете свои данные или имеете согласие субъекта.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "run")
async def run_search(cb: CallbackQuery):
    target = user_sessions.get(cb.from_user.id)
    await cb.message.edit_text("🛰 <b>Идет запрос к реестрам...</b>", parse_mode=ParseMode.HTML)
    
    info = await get_dadata_info(target)
    
    if info:
        report = (
            f"💉 <b>РЕЗУЛЬТАТЫ ПО ОБЪЕКТУ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📞 <b>Номер:</b> <code>{target}</code>\n"
            f"🏢 <b>Оператор:</b> {info['operator']}\n"
            f"🌍 <b>Регион:</b> {info['region']}\n"
            f"🏙 <b>Город:</b> {info['city']}\n"
            f"⏰ <b>Пояс:</b> {info['tz']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <i>Данные извлечены через шлюз DaData.</i>"
        )
        await cb.message.answer(report, parse_mode=ParseMode.HTML)
    else:
        await cb.message.answer("❌ Ошибка связи с API. Проверьте баланс на DaData.")
    await cb.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
