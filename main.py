import asyncio
import logging
import re
import json
import time
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Хранилище сессий
sessions = {}

class Searcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.5',
        }
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def search(self, target):
        results = {
            "names": [],
            "nicks": [],
            "phones": [],
            "emails": [],
            "cities": [],
            "urls": [],
            "social": [],
            "raw": ""
        }
        
        queries = [
            f'"{target}" site:vk.com',
            f'"{target}" site:facebook.com',
            f'"{target}" site:instagram.com',
            f'"{target}" site:twitter.com',
            f'"{target}" site:github.com',
            f'"{target}" site:linkedin.com',
            f'"{target}" site:habr.com',
            f'"{target}" email OR mail OR gmail',
            f'"{target}" phone OR tel OR телефон',
            f'"{target}" город OR city OR location',
            f'"{target}" username OR nickname OR ник',
        ]
        
        for q in queries:
            try:
                url = f"https://www.google.com/search?q={urllib.parse.quote(q)}&num=20&hl=ru"
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=10, context=self.ctx) as resp:
                    html = resp.read().decode('utf-8', errors='ignore')
                    results["raw"] += html[:5000]
                    
                    # Имена
                    names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', html)
                    results["names"].extend(names[:5])
                    
                    # Ники
                    nicks = re.findall(r'@[a-zA-Z0-9_\.]{3,30}', html)
                    results["nicks"].extend(nicks[:5])
                    
                    # Телефоны (форматы РФ)
                    phones = re.findall(r'(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', html)
                    results["phones"].extend(phones[:3])
                    
                    # Email
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
                    results["emails"].extend(emails[:3])
                    
                    # Города
                    cities = re.findall(r'(?:г\.|город)\s*([А-ЯЁ][а-яё\-]+(?:[\s\-][А-ЯЁ][а-яё\-]+)?)', html)
                    results["cities"].extend(cities[:5])
                    
                    # Ссылки
                    urls = re.findall(r'https?://[^\s<>"]+', html)
                    results["urls"].extend(urls[:10])
                    
            except Exception as e:
                continue
        
        # Убираем дубли и сортируем
        for key in results:
            if isinstance(results[key], list):
                results[key] = sorted(list(set(results[key])))
        
        return results

searcher = Searcher()

def format_report(target, data):
    report = f"<b>ОТЧЁТ ПОИСКА</b>\n"
    report += f"<b>Цель:</b> {target}\n"
    report += f"<b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    report += "<b>━━━━━━━━━━━━━━━━━━</b>\n\n"
    
    if data["names"]:
        report += "<b>ИМЕНА:</b>\n"
        for n in data["names"]:
            report += f"• {n}\n"
        report += "\n"
    
    if data["nicks"]:
        report += "<b>НИКИ:</b>\n"
        for n in data["nicks"]:
            report += f"• {n}\n"
        report += "\n"
    
    if data["phones"]:
        report += "<b>ТЕЛЕФОНЫ:</b>\n"
        for p in data["phones"]:
            report += f"• {p}\n"
        report += "\n"
    
    if data["emails"]:
        report += "<b>EMAIL:</b>\n"
        for e in data["emails"]:
            report += f"• {e}\n"
        report += "\n"
    
    if data["cities"]:
        report += "<b>ГОРОДА:</b>\n"
        for c in data["cities"]:
            report += f"• {c}\n"
        report += "\n"
    
    if data["urls"]:
        report += "<b>ССЫЛКИ:</b>\n"
        for u in data["urls"][:7]:
            report += f"• {u}\n"
        report += "\n"
    
    if data["social"]:
        report += "<b>СОЦСЕТИ:</b>\n"
        for s in data["social"]:
            report += f"• {s}\n"
        report += "\n"
    
    if not any([data["names"], data["nicks"], data["phones"], data["emails"], data["cities"], data["urls"]]):
        report += "<b>Ничего не найдено в открытых источниках.</b>\n"
        report += "Попробуйте уточнить запрос (ФИО полностью)."
    
    report += "\n<b>━━━━━━━━━━━━━━━━━━</b>\n"
    report += "Поиск выполнен по открытым источникам."
    
    return report

def get_consent_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ДА, Я ДАЮ СОГЛАСИЕ", callback_data="consent_yes"),
        ],
        [
            InlineKeyboardButton(text="НЕТ, ОТМЕНА", callback_data="consent_no"),
        ]
    ])
    return kb

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "<b>ПОИСКОВЫЙ БОТ</b>\n\n"
        "Отправь ФИО, никнейм, телефон или email для поиска.\n\n"
        "<b>Важно:</b> поиск идёт только по открытым публичным источникам. "
        "Продолжая, вы подтверждаете, что ищете информацию о себе либо имеете законное право на поиск.\n\n"
        "Отправьте запрос:",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>КАК ИСКАТЬ:</b>\n\n"
        "• ФИО: Иванов Иван Иванович\n"
        "• Ник: @username\n"
        "• Телефон: 89991234567\n"
        "• Email: user@mail.ru\n\n"
        "Бот автоматически определит тип запроса и найдёт связанные данные.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle_search(message: Message):
    target = message.text.strip()
    user_id = message.from_user.id
    
    if len(target) < 2:
        await message.answer("Слишком короткий запрос. Введите ФИО, телефон, email или ник.")
        return
    
    sessions[user_id] = {"target": target, "time": time.time()}
    
    await message.answer(
        f"<b>ЗАПРОС НА ПОИСК</b>\n\n"
        f"Цель: <b>{target}</b>\n\n"
        f"Вы подтверждаете, что:\n"
        f"• Ищете информацию о себе\n"
        f"• Либо имеете законное право на поиск\n"
        f"• Поиск ведётся только по открытым источникам\n\n"
        f"Нажмите кнопку для продолжения:",
        reply_markup=get_consent_keyboard(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "consent_yes")
async def consent_yes(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in sessions:
        await callback.answer("Сессия истекла. Отправьте запрос заново.", show_alert=True)
        return
    
    target = sessions[user_id]["target"]
    
    await callback.message.edit_text(
        f"<b>ПОИСК ЗАПУЩЕН</b>\n\nЦель: <b>{target}</b>\n\n"
        f"Статус: Идёт поиск по 11 источникам...\n"
        f"Пожалуйста, подождите (10-20 секунд)",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()
    
    # Запуск поиска
    status_msg = await callback.message.answer("Начинаю поиск...")
    
    for i in range(1, 4):
        await asyncio.sleep(0.3)
        dots = "●" * i + "○" * (3 - i)
        try:
            await status_msg.edit_text(f"Поиск: [{dots}] {i*33}%")
        except:
            pass
    
    # Сам поиск
    data = searcher.search(target)
    
    # Дополнительный разбор соцсетей
    social_platforms = []
    for url in data["urls"]:
        if "vk.com" in url:
            social_platforms.append(f"VK: {url}")
        elif "facebook.com" in url:
            social_platforms.append(f"Facebook: {url}")
        elif "instagram.com" in url:
            social_platforms.append(f"Instagram: {url}")
        elif "twitter.com" in url or "x.com" in url:
            social_platforms.append(f"Twitter/X: {url}")
        elif "github.com" in url:
            social_platforms.append(f"GitHub: {url}")
        elif "linkedin.com" in url:
            social_platforms.append(f"LinkedIn: {url}")
        elif "habr.com" in url:
            social_platforms.append(f"Habr: {url}")
        elif "t.me" in url:
            social_platforms.append(f"Telegram: {url}")
    data["social"] = list(set(social_platforms))[:10]
    
    await status_msg.delete()
    
    report = format_report(target, data)
    
    # Отправляем отчёт
    try:
        await callback.message.answer(report, parse_mode=ParseMode.HTML)
    except:
        # Если слишком длинный
        parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
        for part in parts:
            await callback.message.answer(part, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "consent_no")
async def consent_no(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in sessions:
        del sessions[user_id]
    
    await callback.message.edit_text("<b>ПОИСК ОТМЕНЁН</b>\n\nЗапрос удалён. Отправьте новый запрос, если нужно.", parse_mode=ParseMode.HTML)
    await callback.answer("Поиск отменён")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот запущен. Поиск работает.")
    asyncio.run(main())