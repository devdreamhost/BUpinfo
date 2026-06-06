__version__ = (1, 4, 9, 0)
# meta developer: @devdreamix

import asyncio
import re
import random
import aiohttp
from html import unescape
from typing import List, Optional

from telethon import events
from .. import loader, utils

def _format_tg_emoji(emoji_id: str, fallback: str) -> str:
    return f"<tg-emoji emoji-id=\"{emoji_id}\">{fallback}</tg-emoji>"

def _format_custom_emoji(emoji_id: str, fallback: str) -> str:
    return f"<emoji document_id={emoji_id}>{fallback}</emoji>"

class BunkerUpInfoMod(loader.Module):
    """Модуль для подсчёта прокачки бункера от дрима с автообновлением"""
    strings = {"name": "BUpinfo"}
    
    def __init__(self):
        self.URL_RAW = "https://raw.githubusercontent.com/devdreamix/BUpinfo/main/BUpinfo.py"
        
        self._bot_id = 5813222348
        self._lock = asyncio.Lock()
        self._response_event = None
        self._last_response = None
        self._pending_command = None
        
        self.emoji = {
            'vip': '⚡️', 'user': '🙎‍♂️', 'bunker': '🏢', 'balance': '💰',
            'bottles': '🍾', 'bbcoins': '🪙', 'gpoints': '🍪', 'people': '🧍',
            'queue': '↳', 'rooms': '🏠', 'ready': '🟢', 'upgrade': '🔴',
            'cost': '💵', 'profit': '💎', 'info': '📊', 'warn': '❗️',
            'calc': '🗃', 'arrow': '→', 'chart': '📈', 'question': '❓',
            'note': '🗒', 'bell': '🔔', 'gear': '⚙️'
        }
        
        self._premium_emojis_data = {
            'shield_bunker': {"id": "5310147356883178344", "fallback": "🛡️"},
            'warn_display': {"id": "5309836186502587572", "fallback": "❗️"}, 
            'file_box': {"id": "5309931139639562064", "fallback": "🗃"},       
            'people_display': {"id": "5309844291105869907", "fallback": "👥"}, 
            'arrow_display': {"id": "5312434972429142742", "fallback": "⬇️"},
            'info_display': {"id": "5310104514584399566", "fallback": "ℹ️"},  
            'question_display': {"id": "5310193995933044872", "fallback": "❓"}, 
            'ready_display': {"id": "5310147356883178344", "fallback": "🛡️"},
            'upgrade_display': {"id": "5309836186502587572", "fallback": "❗️"},
            'diamond_custom': {"id": "5309793825240144926", "fallback": "💎"},
            'note_custom': {"id": "5309895504295908899", "fallback": "🗒"},
            'world': {"id": "5310104514584399566", "fallback": "🌎"},
            'bell': {"id": "5310193995933044872", "fallback": "🔔"},
            'gear': {"id": "5787237370709413702", "fallback": "⚙️"},
        }
        
        self._base_people = [6, 6, 6, 6, 12, 20, 32, 52, 92, 144, 234, 380, 520, 750, 1030, 1430, 2020, 3520, 5020]
        self._people_per_level = 2
        
        self._base_profit = [
            80,     # K1 Теплица
            80,     # K2 Генераторная
            80,     # K3 Столовая
            80,     # K4 Станция воды
            151,    # K5 Сейф
            202,    # K6 Игровая комната
            303,    # K7 Медпункт
            505,    # K8 Радиостанция
            808,    # K9 Оружейная
            1515,   # K10 Кухня
            2323,   # K11 Гостиная
            3434,   # K12 Шахта
            5050,   # K13 Лаборатория
            7070,   # K14 Сад
            10100,  # K15 Автомастерская
            18180,  # K16 Гильдия
            30300,  # K17 Киберспортивная
            101000, # K18 Адронный коллайдер
            202000  # K19 Реактор
        ]
        
        self._profit_per_level = [1, 1, 1, 1, 2, 2, 3, 5, 8, 15, 23, 34, 50, 70, 100, 180, 300, 1000, 2000]
        
        self._room_names = [
            "Теплица",
            "Генераторная", 
            "Столовая",
            "Станция обработки воды",
            "Сейф",
            "Игровая комната",
            "Медпункт",
            "Радиостанция",
            "Оружейная",
            "Кухня",
            "Гостиная",
            "Шахта",
            "Лаборатория",
            "Сад",
            "Автомастерская",
            "Гильдия",
            "Киберспортивная комната",
            "Адронный коллайдер",
            "Реактор"
        ]
        
        self._cost_multiplier = 3

    async def _check_update(self) -> Optional[tuple]:
        """Внутренний метод для проверки версии в облаке"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.URL_RAW, timeout=2) as response:
                    if response.status == 200:
                        text = await response.text()
                        match = re.search(r'__version__\s*=\s*\((.*?)\)', text)
                        if match:
                            return tuple(map(int, match.group(1).replace(' ', '').split(',')))
        except Exception:
            pass
        return None
        
    def _get_display_emoji(self, key: str, is_parsing: bool = False, use_custom_format: bool = False) -> str:
        if is_parsing:
            return self.emoji.get(key, '')
        
        premium_data = self._premium_emojis_data.get(key)
        if premium_data:
            if use_custom_format:
                return _format_custom_emoji(premium_data["id"], premium_data["fallback"])
            else:
                return _format_tg_emoji(premium_data["id"], premium_data["fallback"])
        
        return self.emoji.get(key, '')

    async def client_ready(self, client, db) -> None:
        self.client = client
        self.db = db
        self._response_event = asyncio.Event()
        
        @self.client.on(events.NewMessage(from_users=self._bot_id, incoming=True))
        async def bot_handler(event):
            if self._pending_command:
                self._last_response = event.raw_text
                self._response_event.set()

    async def bupcmd(self, message) -> None:
        """<количество людей> - Рассчитать прокачку всех комнат (реплай на бункер)"""
        chat_id = utils.get_chat_id(message)
        args = utils.get_args_raw(message)
        
        if not args or not args.isdigit():
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Укажите количество людей!</b>\nПример: <code>.bup 1500</code>")
            return
        
        target_people = int(args)
        
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Ответьте на сообщение с бункером!</b>")
            return
        
        text = reply.text
        try:
            await message.delete()
        except Exception:
            pass
        
        clean = re.sub(r'<[^>]+>', '', text)
        clean = unescape(clean)
        
        profit_match = re.search(r'Общая прибыль\s+([\d\.,]+)\s+кр\./час\s*\(([+-]?\d+)%\)', clean)
        if profit_match:
            profit_str = profit_match.group(1).replace(',', '').replace('.', '')
            real_current_profit = int(profit_str)
            profit_percent = int(profit_match.group(2))
        else:
            profit_match = re.search(r'Общая прибыль\s+([\d\.,]+)', clean)
            if profit_match:
                profit_str = profit_match.group(1).replace(',', '').replace('.', '')
                real_current_profit = int(profit_str)
                profit_percent = 0
            else:
                real_current_profit = None
                profit_percent = 0
        
        current_rooms = self._parse_rooms_ordered(text)
        
        if not current_rooms or all(lvl == 1 for lvl in current_rooms[:16]):
            await self.client.send_message(chat_id, f"{self._get_display_emoji('warn_display')} <b>Не удалось получить данные о комнатах!</b>")
            return

        version_str = f"v{'.'.join(map(str, __version__))}"
        try:
            cloud_v = await asyncio.wait_for(self._check_update(), timeout=1.5)
            if cloud_v and cloud_v > __version__:
                version_str += " <b>(Доступно обновление 🔥)</b>"
        except Exception:
            pass

        result = self._calculate_upgrade(current_rooms, target_people, real_current_profit, profit_percent)
        
        final_output = f"<code>{version_str}</code>\n<blockquote expandable>{result}</blockquote>"
        await self.client.send_message(chat_id, final_output, parse_mode='html')

    async def kupcmd(self, message) -> None:
        """<количество людей> - Рассчитать прокачку одной комнаты (реплай на комнату)"""
        chat_id = utils.get_chat_id(message)
        args = utils.get_args_raw(message)
        
        if not args or not args.isdigit():
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Укажите целевое количество людей!</b>\nПример: <code>.kup 2000</code>")
            return
        
        target_people = int(args)
        
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Ответьте на сообщение с комнатой!</b>")
            return
        
        text = reply.text
        if not text:
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Пустое сообщение!</b>")
            return
        
        room_match = re.search(r'Комната\s*№(\d+)', text)
        if not room_match:
            if "Киберспортивная" in text:
                room_num = 17
            elif "Адронный коллайдер" in text:
                room_num = 18
            elif "Реактор" in text:
                room_num = 19
            else:
                await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Не удалось определить комнату!</b>")
                return
        else:
            room_num = int(room_match.group(1))
        
        level_match = re.search(r'Уровень:\s*(\d+)', text)
        if not level_match:
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Не удалось определить уровень!</b>")
            return
        
        current_lvl = int(level_match.group(1))
        
        profit_match = re.search(r'Прибыль:\s*([\d,]+)', text)
        current_profit = int(profit_match.group(1).replace(',', '')) if profit_match else None
        
        try:
            await message.delete()
        except Exception:
            pass
        
        result = self._calculate_single_room(room_num, current_lvl, target_people, current_profit)
        await self.client.send_message(chat_id, result)

    async def bxpcmd(self, message) -> None:
        """Показать вместимость всех комнат (реплай на бункер)"""
        chat_id = utils.get_chat_id(message)
        
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Ответьте на сообщение с бункером!</b>")
            return
        
        text = reply.text
        try:
            await message.delete()
        except Exception:
            pass
        
        current_rooms = self._parse_rooms_ordered(text)
        
        if not current_rooms or all(lvl == 1 for lvl in current_rooms[:16]):
            await self.client.send_message(chat_id, f"{self._get_display_emoji('warn_display')} <b>Не удалось получить данные о комнатах!</b>")
            return
        
        clean = re.sub(r'<[^>]+>', '', text)
        clean = unescape(clean)
        people_match = re.search(r'🧍\s*Людей\s*в\s*бункере:\s*([\d,]+)', clean)
        current_people = int(people_match.group(1).replace(',', '')) if people_match else 0
        
        max_cap_match = re.search(r'Макс\.\s*вместимость\s*людей:\s*(\d+)', clean)
        max_capacity = int(max_cap_match.group(1)) if max_cap_match else 0
        
        rooms_opened = 0
        for i in range(len(self._room_names)):
            if i < len(current_rooms) and current_rooms[i] > 1:
                rooms_opened = i + 1
        
        total_profit = 0
        total_value = 0
        
        total_rooms_count = len(self._room_names)
        for i in range(total_rooms_count):
            current_lvl = current_rooms[i] if i < len(current_rooms) else 1
            base_profit = self._base_profit[i]
            profit_per_lvl = self._profit_per_level[i]
            
            room_profit = base_profit + (current_lvl - 1) * profit_per_lvl
            total_profit += room_profit
            
            room_value = 0
            for lvl in range(1, current_lvl):
                profit_at_lvl = base_profit + (lvl - 1) * profit_per_lvl
                room_value += profit_at_lvl * self._cost_multiplier
            total_value += room_value
        
        result = f"{self._get_display_emoji('file_box')} <b>Вместимость бункера</b>\n\n"
        
        for i in range(total_rooms_count):
            room_num = i + 1
            current_lvl = current_rooms[i] if i < len(current_rooms) else 1
            base_people = self._base_people[i]
            
            current_people_room = base_people + (current_lvl - 1) * self._people_per_level
            
            if current_people_room < current_people:
                status = f"🔼"
            elif current_people_room > current_people:
                status = f"✓"
            else:
                status = f"＝"
            
            people_str = f"{current_people_room:,}".replace(",", " ")
            
            result += f"{self._get_display_emoji('diamond_custom', use_custom_format=True)} K{room_num} - {people_str} чел. {status}\n"
        
        result += f"\n{self._get_display_emoji('people_display')} <b>Чел сейчас:</b> {current_people:,}\n".replace(",", " ")
        result += f"{self._get_display_emoji('shield_bunker')} <b>Макс. вместимость:</b> {max_capacity:,} чел.\n".replace(",", " ")
        result += f"{self._get_display_emoji('rooms')} <b>Комнат открыто:</b> {rooms_opened}/{total_rooms_count}\n"
        result += f"{self._get_display_emoji('diamond_custom', use_custom_format=True)} <b>Общая прибыль:</b> {total_profit:,} крышек\n".replace(",", " ")
        result += f"{self._get_display_emoji('note_custom', use_custom_format=True)} <b>Стоимость бункера:</b> {total_value:,} крышек".replace(",", " ")
        
        result = f"<blockquote expandable>{result}</blockquote>"
        await self.client.send_message(chat_id, result, parse_mode='html')

    async def upbcmd(self, message) -> None:
        """Проверить и установить обновление модуля из облака"""
        await utils.answer(message, f"{self._get_display_emoji('gear')} <b>Проверяю облако на наличие обновлений...</b>")
        cloud_v = await self._check_update()
        
        if not cloud_v:
            await utils.answer(message, f"{self._get_display_emoji('warn_display')} <b>Не удалось связаться с репозиторием обновлений!</b>")
            return
            
        local_v_str = ".".join(map(str, __version__))
        cloud_v_str = ".".join(map(str, cloud_v))
        
        if cloud_v > __version__:
            await utils.answer(
                message, 
                f"🚀 <b>Доступно новое обновление модуля!</b>\n"
                f" Настоящая версия: <code>v{local_v_str}</code>\n"
                f" Облачная версия: <code>v{cloud_v_str}</code>\n\n"
                f"<b>Для установки нажми на команду ниже:</b>\n"
                f"<code>.dl {self.URL_RAW}</code>"
            )
        else:
            await utils.answer(message, f"🟢 <b>У вас уже установлена самая актуальная версия v{local_v_str}!</b>")

    async def _send_to_bot(self, command: str) -> str | None:
        try:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await self.client.send_message(self._bot_id, command)
            
            try:
                await asyncio.wait_for(self._response_event.wait(), timeout=10)
                return self._last_response
            except asyncio.TimeoutError:
                return None
        except Exception:
            return None

    def _parse_rooms_ordered(self, text: str) -> List[int]:
        """Парсит уровни всех комнат из сообщения о бункере по названиям"""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = unescape(clean)
        
        rooms = [1] * 19
        
        lines = clean.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for idx, room_name in enumerate(self._room_names):
                if room_name in line:
                    level_match = re.search(r'(\d+)\s*ур\.', line) or re.search(r'(\d+)$', line)
                    if level_match:
                        level = int(level_match.group(1))
                        rooms[idx] = level
                    break
        
        return rooms

    def _calculate_upgrade(self, current_rooms: List[int], target_people: int, real_current_profit: Optional[int] = None, profit_percent: int = 0) -> str:
        total_cost = 0
        total_current_profit = 0
        total_future_profit = 0
        
        file_emoji = self._get_display_emoji('file_box')
        note_emoji = self._get_display_emoji('note_custom', use_custom_format=True)
        diamond_emoji = self._get_display_emoji('diamond_custom', use_custom_format=True)
        shield_emoji = self._get_display_emoji('shield_bunker')
        warn_emoji = self._get_display_emoji('upgrade_display')
        bell_emoji = self._get_display_emoji('bell')

        text = f"{file_emoji} <b>Для {target_people} людей:</b>\n\n"
        
        total_rooms_count = len(self._room_names)
        for i in range(total_rooms_count):
            room_num = i + 1
            current_lvl = current_rooms[i] if i < len(current_rooms) else 1
            base_people = self._base_people[i]
            base_profit = self._base_profit[i]
            profit_per_lvl = self._profit_per_level[i]
            room_name = self._room_names[i]
            
            current_people = base_people + (current_lvl - 1) * self._people_per_level
            
            current_profit = base_profit + (current_lvl - 1) * profit_per_lvl
            total_current_profit += current_profit
            
            if current_people >= target_people:
                total_future_profit += current_profit
                text += f"{shield_emoji} K{room_num}: ✓ ({current_people:,} чел.)\n".replace(",", " ")
                continue
            
            if target_people <= base_people:
                needed_lvl = 1
            else:
                needed_lvl = ((target_people - base_people + self._people_per_level - 1) 
                             // self._people_per_level) + 1
            
            if needed_lvl <= current_lvl:
                total_future_profit += current_profit
                text += f"{shield_emoji} K{room_num}: ✓ ({current_people:,} чел.)\n".replace(",", " ")
                continue
            
            levels_to_upgrade = needed_lvl - current_lvl
            upgrade_cost = 0
            
            for lvl in range(current_lvl, needed_lvl):
                profit_at_lvl = base_profit + (lvl - 1) * profit_per_lvl
                upgrade_cost += profit_at_lvl * self._cost_multiplier
            
            total_cost += upgrade_cost
            
            future_profit = base_profit + (needed_lvl - 1) * profit_per_lvl
            total_future_profit += future_profit
            
            text += (f"{warn_emoji} K{room_num} ({room_name}): +{levels_to_upgrade} ур. "
                    f"({current_people:,}→{target_people:,}) = {upgrade_cost:,} кр.\n").replace(",", " ")
        
        text += f"\n{note_emoji} <b>Общая стоимость:</b> {total_cost:,} кр.\n".replace(",", " ")
        
        if real_current_profit:
            if profit_percent != 0:
                base_real_profit = int(real_current_profit / (1 + profit_percent / 100))
                boost_in_kk = real_current_profit - base_real_profit
            else:
                base_real_profit = real_current_profit
                boost_in_kk = 0
            
            profit_ratio = base_real_profit / total_current_profit
            
            future_base = int(total_future_profit * profit_ratio)
            
            if profit_percent != 0:
                future_real = int(future_base * (1 + profit_percent / 100))
            else:
                future_real = future_base
            
            current_base = int(total_current_profit * profit_ratio)
            
            base_increase = future_base - current_base
            
            text += f"{diamond_emoji} <b>Текущая прибыль:</b> {real_current_profit:,} кр/час".replace(",", " ")
            if boost_in_kk > 0:
                text += f" (+{boost_in_kk:,})\n".replace(",", " ")
            else:
                text += "\n"
            
            text += f"{bell_emoji} <b>Прибыль после:</b> {future_real:,} кр/час".replace(",", " ")
        else:
            text += f"{diamond_emoji} <b>Текущая прибыль:</b> {total_current_profit:,} кр/час\n".replace(",", " ")
            text += f"{bell_emoji} <b>Прибыль после:</b> {total_future_profit:,} кр/час".replace(",", " ")
        
        return text

    def _calculate_single_room(self, room_num: int, current_lvl: int, target_people: int, current_profit: Optional[int] = None) -> str:
        i = room_num - 1
        if i < 0 or i >= len(self._room_names):
            return f"{self._get_display_emoji('warn_display')} <b>Неверный номер комнаты!</b>"
        
        base_people = self._base_people[i]
        base_profit = self._base_profit[i]
        profit_per_lvl = self._profit_per_level[i]
        room_name = self._room_names[i]
        
        current_people = base_people + (current_lvl - 1) * self._people_per_level
        
        if current_people >= target_people:
            current_profit_val = current_profit or (base_profit + (current_lvl - 1) * profit_per_lvl)
            return (f"{self._get_display_emoji('gear')} <b>Расчёт апгрейда: {room_name}</b>\n"
                   f"{self._get_display_emoji('ready_display')} <b>Уровень:</b> {current_lvl} (достаточно)\n"
                   f"{self._get_display_emoji('people_display')} <b>Вместимость:</b> {current_people:,} чел. > {target_people:,} чел.\n"
                   f"{self._get_display_emoji('diamond_custom', use_custom_format=True)} <b>Доход:</b> {current_profit_val:,} кр./час").replace(",", " ")
        
        if target_people <= base_people:
            needed_lvl = 1
        else:
            needed_lvl = ((target_people - base_people + self._people_per_level - 1) 
                         // self._people_per_level) + 1
        
        upgrade_cost = 0
        for lvl in range(current_lvl, needed_lvl):
            profit_at_lvl = base_profit + (lvl - 1) * profit_per_lvl
            upgrade_cost += profit_at_lvl * self._cost_multiplier
        
        new_profit = base_profit + (needed_lvl - 1) * profit_per_lvl
        
        return (f"{self._get_display_emoji('gear')} <b>Расчёт апгрейда: {room_name}</b>\n"
               f"{self._get_display_emoji('info_display')} <b>Уровень:</b> {current_lvl} → {needed_lvl}\n"
               f"{self._get_display_emoji('note_custom', use_custom_format=True)} <b>Стоимость:</b> {upgrade_cost:,} кр.\n"
               f"{self._get_display_emoji('diamond_custom', use_custom_format=True)} <b>Новый доход:</b> {new_profit:,} кр./час\n"
               f"{self._get_display_emoji('people_display')} <b>Вместимость:</b> {current_people:,} → {target_people:,} чел.").replace(",", " ")

    async def on_unload(self) -> None:
        self._pending_command = None
