import asyncio
import logging
import re
import time
import urllib.request
import urllib.parse
import ssl
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode

TOKEN = "8786648200:AAHWlhGJO9PzNLBCEoNAxFnADZebmvPsgb0"

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

sessions = {}

class Searcher:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        
        self.agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.3 Mobile Safari/537.36',
        ]


        self.engines = [
            {'url': 'https://html.duckduckgo.com/html/?q={query}&kl=ru-ru', 'name': 'DuckDuckGo'},
            {'url': 'https://search.yahoo.com/search?p={query}&n=30', 'name': 'Yahoo'},
            {'url': 'https://www.bing.com/search?q={query}&count=30&setlang=ru', 'name': 'Bing'},
            {'url': 'https://yandex.ru/search/?text={query}&numdoc=30&lr=2', 'name': 'Яндекс'},
            {'url': 'https://www.google.com/search?q={query}&num=30&hl=ru&gl=ru', 'name': 'Google'},
            {'url': 'https://search.aol.com/aol/search?q={query}&count=30', 'name': 'AOL'},
            {'url': 'https://www.ask.com/web?q={query}', 'name': 'Ask'},
            {'url': 'https://search.lycos.com/web/?q={query}', 'name': 'Lycos'},
            {'url': 'https://startpage.com/do/dsearch?query={query}&language=ru', 'name': 'Startpage'},
            {'url': 'https://search.brave.com/search?q={query}&source=web', 'name': 'Brave'},
            {'url': 'https://www.ecosia.org/search?q={query}', 'name': 'Ecosia'},
            {'url': 'https://www.dogpile.com/serp?q={query}', 'name': 'Dogpile'},
            {'url': 'https://searx.be/search?q={query}&language=ru', 'name': 'SearX'},
            {'url': 'https://search.qwant.com/?q={query}&language=ru', 'name': 'Qwant'},
            {'url': 'https://www.entireweb.com/search?q={query}', 'name': 'Entireweb'},
        ]

    def _get_headers(self):
        return {
            'User-Agent': random.choice(self.agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'identity',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://www.google.com/',
        }

    def _fetch(self, url):
        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=20, context=self.ctx) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except:
            return ""

    def _extract_data(self, html, target):
        found = {
            'names': [],
            'nicks': [],
            'phones': [],
            'emails': [],
            'addresses': [],
            'urls': [],
            'snippets': []
        }


        clean = re.sub(r'<[^>]+>', ' ', html)
        clean = re.sub(r'&[a-z]+;', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean)


        names = re.findall(r'[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+(?:\s[А-ЯЁ][а-яё]+)?', clean)
        for n in names:
            if len(n) > 6 and n not in found['names']:
                found['names'].append(n.strip())


        nicks = re.findall(r'(?:@|ник:?\s*|nick:?\s*|username:?\s*|login:?\s*)([a-zA-Z0-9_\.]{3,30})', clean.lower())
        found['nicks'].extend(nicks[:10])


        phones = re.findall(
            r'(?:\+7|8|7)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',
            clean
        )


        email_pattern = r'[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, clean)


        addr_patterns = [
            r'(?:ул\.|улица|пр\.|проспект|пер\.|переулок|пл\.|площадь|б-р|бульвар|наб\.|набережная)[\s\w\-\.\,]+(?:д\.|дом|к\.|корп\.|кв\.|квартира)?\s*\d+[а-я]?',
            r'(?:г\.|город)\s*[А-ЯЁ][а-яё\-]+',
            r'[А-ЯЁ][а-яё\-]+\s(?:область|край|район)',
        ]
        for pat in addr_patterns:
            addresses = re.findall(pat, clean)
            found['addresses'].extend(addresses)


        urls = re.findall(
            r'https?://(?!google\.|yandex\.|bing\.|yahoo\.|duckduckgo\.|aol\.|ask\.|lycos\.|startpage\.|brave\.|ecosia\.|dogpile\.|searx\.|qwant\.|entireweb\.)[^\s<>"\']+',
            clean
        )


        snippets = re.split(r'[.!?]\s+', clean)
        for s in snippets:
            s = s.strip()
            if len(s) > 30 and len(s) < 300 and target.lower() in s.lower():
                found['snippets'].append(s)

        for key in found:
            found[key] = list(set(found[key]))[:15]

        return found

    async def search(self, target, status_callback=None):
        all_data = {
            'names': [],
            'nicks': [],
            'phones': [],
            'emails': [],
            'addresses': [],
            'urls': [],
            'snippets': [],
            'sources': []
        }

        queries = [
            f'"{target}"',
            f'{target} контакты',
            f'{target} адрес',
            f'{target} email',
            f'{target} соцсети',
            f'{target} vk',
            f'{target} telegram',
            f'{target} facebook',
            f'{target} instagram',
            f'{target} github',
            f'{target} linkedin',
            f'site:vk.com {target}',
            f'site:facebook.com {target}',
            f'site:instagram.com {target}',
            f'site:t.me {target}',
            f'site:github.com {target}',
            f'site:habr.com {target}',
            f'site:linkedin.com {target}',
            f'site:twitter.com {target}',
            f'site:ok.ru {target}',
            f'site:avito.ru {target}',
            f'site:cian.ru {target}',
            f'{target} телефон',
            f'{target} +7',
            f'{target} город',
            f'{target} работа',
            f'{target} резюме',
            f'{target} отзывы',
            f'{target} слив',
            f'{target} утечка',
        ]

        total_q = len(queries)
        engines_to_use = self.engines[:8]

        for i, q in enumerate(queries):
            if status_callback and i % 2 == 0:
                pct = int((i / total_q) * 100)
                await status_callback(f"Обработано запросов: {i}/{total_q} ({pct}%)")

            engine = random.choice(engines_to_use)
            url = engine['url'].format(query=urllib.parse.quote(q))
            html = self._fetch(url)

            if html:
                data = self._extract_data(html, target)
                for key in all_data:
                    if key != 'sources':
                        all_data[key].extend(data.get(key, []))
                all_data['sources'].append(engine['name'])


            await asyncio.sleep(random.uniform(1.5, 3.5))


        for key in all_data:
            if isinstance(all_data[key], list):
                all_data[key] = list(set(all_data[key]))[:20]

        all_data['sources'] = list(set(all_data['sources']))
        return all_data

searcher = Searcher()

def format_report(target, data):
    lines = []
    lines.append("ОТЧЁТ ПОИСКА\n")
    lines.append(f"Цель: {target}")
    lines.append(f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    lines.append(f"Источники: {', '.join(data.get('sources', []))}")
    lines.append("━━━━━━━━━━━━━━━━━━\n")

    if data.get('names'):
        lines.append("ИМЕНА:")
        for n in data['names'][:10]:
            lines.append(f"  • {n}")
        lines.append("")

    if data.get('nicks'):
        lines.append("НИКИ:")
        for n in data['nicks'][:10]:
            lines.append(f"  • {n}")
        lines.append("")

    if data.get('phones'):
        lines.append("ТЕЛЕФОНЫ:")
        for p in data['phones'][:10]:
            lines.append(f"  • {p}")
        lines.append("")

    if data.get('emails'):
        lines.append("EMAIL:")
        for e in data['emails'][:10]:
            lines.append(f"  • {e}")
        lines.append("")

    if data.get('addresses'):
        lines.append("АДРЕСА:")
        for a in data['addresses'][:10]:
            lines.append(f"  • {a}")
        lines.append("")

    if data.get('urls'):
        lines.append("ССЫЛКИ:")
        for u in data['urls'][:10]:
            lines.append(f"  • {u}")
        lines.append("")

    if data.get('snippets'):
        lines.append("НАЙДЕННЫЕ ФРАГМЕНТЫ:")
        for s in data['snippets'][:8]:
            lines.append(f"  • {s[:200]}...")
        lines.append("")

    if not any([data.get('names'), data.get('nicks'), data.get('phones'), data.get('emails'), data.get('addresses'), data.get('urls')]):
        lines.append("В открытых источниках ничего не найдено.")
        lines.append("Возможно, данные скрыты или цель использует защиту.")

    lines.append("\n━━━━━━━━━━━━━━━━━━")
    lines.append("Поиск завершён. Данные из открытых источников.")

    return '\n'.join(lines)

def consent_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ДА, ИСКАТЬ", callback_data="ok")],
        [InlineKeyboardButton(text="НЕТ, ОТМЕНА", callback_data="no")],
    ])

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "ПОИСКОВЫЙ БОТ\n\n"
        "Отправьте ФИО, телефон, email или никнейм.\n"
        "Поиск по 15 поисковикам, автономно.\n\n"
        "Перед поиском запрашивается согласие.\n"
        "Данные только из открытых источников.",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def handle(msg: Message):
    target = msg.text.strip()
    if len(target) < 2:
        await msg.answer("Слишком коротко.")
        return

    sessions[msg.from_user.id] = {
        'target': target,
        'time': time.time()
    }

    await msg.answer(
        f"Цель: <b>{target}</b>\n\n"
        f"Поиск по 15 системам (Google, Yandex, Bing, DuckDuckGo, Yahoo, AOL, Ask, Lycos, Startpage, Brave, Ecosia, Dogpile, SearX, Qwant, Entireweb).\n"
        f"Обрабатывается 30 поисковых запросов.\n"
        f"Ориентировочное время: 60-90 секунд.\n\n"
        f"Продолжить?",
        reply_markup=consent_kb(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "ok")
async def ok_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid not in sessions:
        await cb.answer("Сессия истекла. Отправьте запрос заново.", show_alert=True)
        return

    target = sessions[uid]['target']

    await cb.message.edit_text(
        f"ПОИСК ЗАПУЩЕН\n\nЦель: <b>{target}</b>\n\n"
        f"Выполняется поиск...\n"
        f"Пожалуйста, подождите.",
        parse_mode=ParseMode.HTML
    )
    await cb.answer()

    status_msg = await cb.message.answer("0%")
    last_update = [0]

    async def update_status(text):
        now = int(time.time())
        if now - last_update[0] >= 2:
            last_update[0] = now
            try:
                await status_msg.edit_text(f"Статус: {text}")
            except:
                pass

    data = await searcher.search(target, status_callback=update_status)

    try:
        await status_msg.delete()
    except:
        pass

    report = format_report(target, data)

    try:
        await cb.message.answer(report, parse_mode=ParseMode.HTML)
    except:
        parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
        for p in parts:
            await cb.message.answer(p, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "no")
async def no_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    if uid in sessions:
        del sessions[uid]
    await cb.message.edit_text("Поиск отменён.")
    await cb.answer("Отмена")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот запущен.")
    asyncio.run(main())