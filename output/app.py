import logging
import random
import requests

from telegram import Bot, ReplyKeyboardRemove
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ConversationHandler, \
    CallbackQueryHandler

from config import BOT_TOKEN
from funcs_backend import *
from yandex_cloud import *
from datetime import timedelta
import pandas as pd
from matplotlib import pyplot as plt
from data import db_session
from data.users import User
from data.big_data import Big_data
from data.statistics import Statistic

openai.api_key = AI_KEY

logging.basicConfig(
    filename='out/logs.log', filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
bot = Bot(BOT_TOKEN)


class ConfigVoice:
    async def start(self, update, context):
        put_to_db(update)
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return
        context.user_data['skip_voice'] = False
        context.user_data['voice'] = 'alena'
        await update.message.reply_text(
            'Привет! Давай знакомиться. Я - Великий Гуру, умею общаться с людьми голосом!',
            reply_markup=ReplyKeyboardRemove())
        return await self.config_voice(update, context)

    async def config_voice(self, update, context):
        context.user_data['skip_voice'] = False
        keyboard = [
            [
                InlineKeyboardButton("Филипп", callback_data="1"),
                InlineKeyboardButton("Алена", callback_data="2"),
            ],
            [
                InlineKeyboardButton("Ермил", callback_data="3"),
                InlineKeyboardButton("Джейн", callback_data="4")
            ],
            [
                InlineKeyboardButton("Захар", callback_data="5"),
                InlineKeyboardButton("Омаж", callback_data="6")
            ],
            [
                InlineKeyboardButton("Мадирус", callback_data="7"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выбери голос:', reply_markup=reply_markup)
        return 1

    async def inline_button(self, update, context):
        query = update.callback_query
        await query.answer()
        if context.user_data.get('skip_voice'):
            chat = query.message.chat.id
            context.user_data['in_conversation'] = False
            await bot.send_message(chat, "Выбор голоса пропущен. Пропишите команду еще раз.")
            return ConversationHandler.END
        num = query.data
        context.user_data['voice'] = VOICES[num][0]
        await query.edit_message_text(text=f"Выбранный голос: {VOICES[num][1]}")
        return ConversationHandler.END

    async def get_out(self, update, context):
        context.user_data['skip_voice'] = True
        context.user_data['in_conversation'] = False
        # chat = update.message.chat.id
        # await bot.send_message(chat, "Выбор голоса пропущен. Пропишите команду еще раз.")
        return ConversationHandler.END


class Dialog:
    async def start_dialog(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        context.user_data['in_conversation'] = True
        await update.message.reply_text(
            'Давай поболтаем! Отправляй мне воисы - а я тебе их расшифровку, и наоборот!\n'
            'Но учти - если воис не на русском языке, я не гарантирую хороший перевод!')
        return 1

    async def send_tts_msg_dialog(self, update, context):
        total_msg_func(update)
        t = ' '.join([i.strip() for i in update.message.text.split('\n') if i.strip() != ''])
        result = await get_audio(t, context.user_data['voice'])
        chat = update.message.chat.id
        if result != -1:
            await bot.sendVoice(chat, result)
            return
        await update.message.reply_text('Длина сообщений должна быть <= 4000 символам.')
        return 1

    async def send_stt_msg_dialog(self, update, context):
        path = await update.message.voice.get_file()
        file = await path.download_as_bytearray()
        total_msg_func(update, msg_format="voice")
        chat = update.message.chat.id
        result = get_text_api_v3(file, chat, logger)
        await bot.sendMessage(chat, result)
        return 1

    async def stop_dialog(self, update, context):
        total_msg_func(update)
        context.user_data['in_conversation'] = False
        await update.message.reply_text('Возвращайся скорее!')
        return ConversationHandler.END


class MapRoute:
    async def navigator_start(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        context.user_data['in_conversation'] = True
        reply_markup = await choose_way()
        if context.user_data.get('voice') is None:
            context.user_data['voice'] = 'alena'
        await update.message.reply_text(
            'Привет. Чтобы узнать информацию о маршруте, для начала выбери, '
            'как ты пришлешь место отправления:', reply_markup=reply_markup)
        return 1

    async def from_address(self, update, context):
        query = update.callback_query
        await query.answer()
        num = query.data
        chat = query.message.chat.id
        if num == '1':
            await query.edit_message_text(text="Выбранный способ: Геопозицией")
            kbrd = await location_kbrd()
            await bot.send_message(chat, 'Что ж, тогда присылай геопозицию.', reply_markup=kbrd)
            return 2
        else:
            await query.edit_message_text(text="Выбранный способ: Текстом (напишу адрес)")
            await bot.send_message(chat, 'Что ж, тогда пиши адрес места, откуда ты начнешь путь.')
            return 3

    async def address_loc(self, update, context):
        total_msg_func(update)
        user_location = update.message.location
        context.user_data['geopos'] = {'from': (user_location.latitude, user_location.longitude)}
        reply_markup = await choose_way()
        await update.message.reply_text(
            'Вау! А теперь выбери, как ты пришлешь место назначения:', reply_markup=reply_markup)
        return 4

    async def address_name(self, update, context):
        total_msg_func(update)
        reply_markup = await choose_way()
        res = await get_coords(update.message.text)
        if res == -1:
            await update.message.reply_text('Такого адреса нет. Давай еще разок.')
            return 3
        context.user_data['geopos'] = {'from': res}
        await update.message.reply_text(
            'Вау! А теперь выбери, как ты пришлешь место назначения:', reply_markup=reply_markup)
        return 4

    async def to_address(self, update, context):
        query = update.callback_query
        await query.answer()
        num = query.data
        chat = query.message.chat.id
        if num == '1':
            await query.edit_message_text(text="Выбранный способ: Геопозицией")
            kbrd = await location_kbrd()
            await bot.send_message(chat, 'Что ж, тогда присылай геопозицию.', reply_markup=kbrd)
            return 5
        else:
            await query.edit_message_text(text="Выбранный способ: Текстом (напишу адрес)")
            await bot.send_message(chat, 'Что ж, тогда пиши адрес места, куда ты хочешь приехать.')
            return 6

    async def address_loc_to(self, update, context):
        user = update.message.from_user
        user_location = update.message.location
        context.user_data['geopos']['to'] = (user_location.latitude, user_location.longitude)
        res = await make_path(context.user_data['geopos'])
        if res == -1:
            await update.message.reply_text('Увы, но пути нет.', reply_markup=ReplyKeyboardRemove())
        else:
            pass
        return ConversationHandler.END

    async def address_name_to(self, update, context):
        total_msg_func(update)
        context.user_data['in_conversation'] = False
        res = await get_coords(update.message.text)
        if res == -1:
            await update.message.reply_text('Такого адреса нет. Давай еще разок.')
            return 6
        context.user_data['geopos']['to'] = res
        res = await make_path(context.user_data['geopos'])
        if res == -1:
            await update.message.reply_text('Увы, но пути нет.')
        else:
            chat = update.message.chat.id
            name_from = await get_address_text(context.user_data['geopos']['from'])
            name_to = await get_address_text(context.user_data['geopos']['to'])
            text = f'Путь от {name_from} до {name_to}.\n'
            text += "\n".join([i[0] + ' ' + i[1][0].replace('~', 'около').replace('₽', ' рублей') +
                               ' ' + ", ".join(i[1][1:]) + '..' for i in res[0]])
            audio = await get_audio(text, context.user_data['voice'])
            await bot.send_photo(chat, res[1])
            text = f'Путь от {name_from} до {name_to}.\n'
            text += "\n".join(
                [i[0] + ': ' + i[1][0] + ' (' + ", ".join(i[1][1:]) + ')' for i in res[0]])
            await bot.send_message(chat, text, reply_markup=ReplyKeyboardRemove())
            await bot.send_voice(chat, audio)
        return ConversationHandler.END

    async def stop_navigator(self, update, context):
        total_msg_func(update)
        context.user_data['in_conversation'] = False
        await update.message.reply_text('Ну раз не хочешь, ну и ладно!',
                                        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


class MainSettings:
    async def help(self, update, context):
        await bot.send_message(update.message.chat.id,
                               prepare_for_markdown("Если у вас возникли какие-либо вопросы, "
                                                    "пишите одному из админов: @delikatny_pon, @Matthew_Davidyan или "
                                                    "обратитесь к документации: ",
                                                    spoiler=False) + f"[Документация]({prepare_for_markdown('https://telegra.ph/Kak-polzovatsya-botom-Velikij-Guru-opisanie-komand-04-16', spoiler=False)})",
                               parse_mode="MarkdownV2")

    async def about(self, update, context):
        await bot.send_message(update.message.chat.id,
                               """
Не каждый может позволить себе телеграм-премиум. Но бывает очень неудобно слушать аудио: в общественных или очень тихих местах... А кому-то лень читать большие сообщения, и он просто хочет послушать голосом!\n
Telegram Premium (цены):\n
2000 рублей/год\n
Наш бот по распознаванию и синтезу голоса: бесплатно\n
Есть вопросы?
                               """)

    async def report(self, update, context):
        await bot.send_message(update.message.chat.id, f"Скоро!")


class GameTowns:
    def __init__(self):
        with open('cities.json', mode='rb') as c:
            self.TOWNS = json.load(c)
        self.LETTERS = 'АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЭЮЯ'

    def get_random_town(self, lett=''):
        if lett == '':
            lett = random.choice(self.LETTERS)
        return random.choice(self.TOWNS[lett])

    async def start_game(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        context.user_data['in_conversation'] = True
        chat = update.message.chat.id
        s = 'Привет! Давай поиграем в города! Ты должен называть города, ' \
            'начинающиеся на ту букву, на которую заканчивается ' \
            'название предыдущего города! Напоминаю правило: буквы ы, ъ, ь выкидываются! Я начинаю.'
        await update.message.reply_text(s)
        await bot.send_voice(chat, await get_audio(s, context.user_data['voice']))
        town = self.get_random_town()
        await bot.send_message(chat, town)
        await bot.send_voice(chat, await get_audio(town, context.user_data['voice']))

        context.user_data['bot_town'] = town
        context.user_data['towns_used'] = [town]
        return 1

    async def get_name(self, update, context):
        total_msg_func(update)
        chat = update.message.chat.id
        city = update.message.text
        res = self.TOWNS.get(city[0].upper())
        if res is None or res == set():
            await update.message.reply_text('Города на такую букву нет!')
            await bot.send_voice(chat,
                                 await get_audio('Города на такую букву нет!',
                                                 context.user_data['voice']))
            return 1
        if city.capitalize() not in res:
            await update.message.reply_text('Такого города я не знаю! Давай другой.')
            await bot.send_voice(chat,
                                 await get_audio('Такого города я не знаю! Давай другой.',
                                                 context.user_data['voice']))
            return 1
        formatted_city = city.replace('ы', '').replace('ь', '').replace('ъ', '').replace('ё', 'е')
        last = formatted_city[-1]
        first = formatted_city[0].lower()
        res = self.TOWNS.get(last.upper())
        if res is None or res == set():
            await update.message.reply_text('Попробуй другой город.')
            await bot.send_voice(chat,
                                 await get_audio('Попробуй другой город.',
                                                 context.user_data['voice']))
            return 1
        if context.user_data['bot_town'].lower().replace('ы', '').replace('ь', '') \
                .replace('ъ', '').replace('ё', 'е')[-1] != first:
            await update.message.reply_text('Неверная первая буква.')
            await bot.send_voice(chat,
                                 await get_audio('Неверная первая буква.',
                                                 context.user_data['voice']))
            return 1
        if city in context.user_data['towns_used']:
            await update.message.reply_text('Город уже был!')
            await bot.send_voice(chat,
                                 await get_audio('Город уже был!', context.user_data['voice']))
            return 1
        context.user_data['towns_used'].append(city)
        town = self.get_random_town(lett=last.upper())
        while town in context.user_data['towns_used']:
            town = self.get_random_town(lett=last.upper())
        await update.message.reply_text(town)
        await bot.send_voice(chat, await get_audio(town, context.user_data['voice']))
        context.user_data['bot_town'] = town
        context.user_data['towns_used'].append(town)
        return 1

    async def end_game(self, update, context):
        total_msg_func(update)
        context.user_data['in_conversation'] = False
        chat = update.message.chat.id
        await update.message.reply_text('Ха-ха, сдаешься? Ну ладно!')
        await bot.send_voice(chat, await get_audio('Ха-ха, сдаешься? Ну ладно!',
                                                   context.user_data['voice']))
        context.user_data['bot_town'] = None
        context.user_data['towns_used'] = []
        return ConversationHandler.END


class ChatGPTDialog:
    async def start(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        context.user_data['in_conversation'] = True
        chat = update.message.chat.id
        await update.message.reply_text('|| Доброго времени суток\! Давай поболтаем \- присылай '
                                        'мне воисы или сообщения\, а я отвечу на них\.\.\. ||',
                                        parse_mode='MarkdownV2')
        await bot.send_voice(chat, await get_audio('Доброго времени суток! Давай поболтаем - '
                                                   'присылай мне воисы или сообщения, а я отвечу '
                                                   'на них...', context.user_data['voice']))
        return 1

    async def audio_request(self, update, context):
        total_msg_func(update, msg_format="voice")
        chat = update.message.chat.id
        info_msg = await bot.send_message(chat, 'Время ожидания ответа: 5-20с')
        path = await update.message.voice.get_file()
        file = await path.download_as_bytearray()
        result = get_text_api_v3(file, chat, logger)
        return await self.send_response(update, context, result, info_msg, chat)

    async def text_request(self, update, context):
        total_msg_func(update)
        chat = update.message.chat.id
        info_msg = await bot.send_message(chat, 'Время ожидания ответа: 5-20с')
        return await self.send_response(update, context, update.message.text, info_msg, chat)

    async def send_response(self, update, context, request, info_msg, chat):
        resp = get_answer(request)
        audio = await get_audio(resp, context.user_data['voice'])
        await info_msg.delete()
        await update.message.reply_text(prepare_for_markdown(resp), parse_mode='MarkdownV2')
        await bot.send_voice(chat, audio)
        return 1

    async def stop_ai(self, update, context):
        total_msg_func(update)
        context.user_data['in_conversation'] = False
        chat = update.message.chat.id
        await update.message.reply_text('|| До встречи\! ||', parse_mode='MarkdownV2')
        await bot.send_voice(chat, await get_audio('До встречи!', context.user_data['voice']))
        return ConversationHandler.END


class News:
    def __init__(self):
        self.count = 0
        self.maximum = 30
        self.voices = {}

    async def send_news(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return
        text = (await get_news_list())[self.count % self.maximum]
        self.count += 1
        keyboard = [[InlineKeyboardButton("Следующую", callback_data="1")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text[1], reply_markup=reply_markup)

        chat = update.message.chat.id
        context.user_data['in_conversation'] = True
        msg = await bot.send_voice(chat, await get_audio(text[2], context.user_data['voice']))
        self.voices[chat] = msg.id

        return 1

    async def send_news_new(self, update, context):
        query = update.callback_query
        await query.answer()
        text = (await get_news_list())[self.count % self.maximum]
        self.count += 1
        keyboard = [[InlineKeyboardButton("Следующую", callback_data="1")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text[1], reply_markup=reply_markup)

        chat = query.message.chat.id
        await bot.delete_message(chat, self.voices[chat])
        msg = await bot.send_voice(chat, await get_audio(text[2], context.user_data['voice']))
        self.voices[chat] = msg.id

        return 1

    async def end_new(self, update, context):
        await bot.send_message(update.message.chat.id, 'Пока!')
        context.user_data['in_conversation'] = False
        return ConversationHandler.END


class Weather:
    def __init__(self):
        self.voices = {}

    async def weather_start(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        context.user_data['in_conversation'] = True
        if context.user_data.get('voice') is None:
            context.user_data['voice'] = 'alena'
        await update.message.reply_text('Привет. Чтобы узнать информацию о погоде, напиши интересующий адрес:')
        return 1

    async def weather_address(self, update, context):
        total_msg_func(update)
        res = await get_coords(update.message.text)
        if res == -1:
            await update.message.reply_text('Такого адреса нет. Попробуй написать ещё раз.')
            return 1
        else:
            chat = update.message.chat.id
            self.name_from = await get_address_text(res)
            params = {"lat": res[0],
                      "lon": res[1],
                      "lang": "ru_RU",
                      "limit": "7",
                      "hours": "false",
                      "extra": "true"}
            headers = {"X-Yandex-API-Key": "97fa72d6-6cec-42c1-90ac-969b3a5c9418"}
            self.response = requests.get('https://api.weather.yandex.ru/v2/forecast', params=params,
                                         headers=headers).json()
            text, for_robot = await get_weather(self.response, self.name_from)
            keyboard = [[InlineKeyboardButton("Сейчас", callback_data="2")],
                        [InlineKeyboardButton("Завтра", callback_data="3")],
                        [InlineKeyboardButton("Послезавтра", callback_data="4")],
                        [InlineKeyboardButton("Через 2 дня", callback_data="5")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await bot.send_message(chat, text, reply_markup=reply_markup)

            chat = update.message.chat.id
            msg = await bot.send_voice(chat, await get_audio(for_robot, context.user_data['voice']))
            self.voices[chat] = msg.id
            # await bot.send_voice(chat, await get_audio(for_robot, context.user_data['voice']))
        return 2

    async def change_date(self, update, context):
        query = update.callback_query
        await query.answer()
        num = query.data
        chat = query.message.chat.id
        keyboard = [[InlineKeyboardButton("Сейчас", callback_data="2")],
                    [InlineKeyboardButton("Завтра", callback_data="3")],
                    [InlineKeyboardButton("Послезавтра", callback_data="4")],
                    [InlineKeyboardButton("Через 2 дня", callback_data="5")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if num == '2':
            text, for_robot = await get_weather(self.response, self.name_from)
        else:
            text, for_robot = await get_weather(self.response, self.name_from, date=int(num) - 3)
        await query.edit_message_text(text, reply_markup=reply_markup)

        chat = query.message.chat.id
        await bot.delete_message(chat, self.voices[chat])
        msg = await bot.send_voice(chat, await get_audio(for_robot, context.user_data['voice']))
        self.voices[chat] = msg.id

        return 2

    async def stop_weather(self, update, context):
        await bot.send_message(update.message.chat.id, 'Пока!')
        context.user_data['in_conversation'] = False
        return ConversationHandler.END


class Stats:
    def get_sessions(self, data):
        total = 0
        durs = []
        last = None
        dur_curr = timedelta(minutes=0)
        for i in data:
            if last is None:
                last = i.start_date
                continue
            if i.start_date - last >= timedelta(minutes=5):
                if dur_curr.total_seconds() >= 0:
                    total += 1
                    durs.append(dur_curr.total_seconds())
                dur_curr = timedelta(minutes=0)
            else:
                dur_curr += i.start_date - last
            last = i.start_date
        if i.start_date - last >= timedelta(minutes=5):
            if dur_curr.total_seconds() >= 0:
                total += 1
                durs.append(dur_curr.total_seconds())
        return durs, total if total else 1

    def make_pic(self, dau_text, dau_voice, user_id):
        if len(dau_text.index):
            plt.bar(dau_text.index, dau_text.values, width=0.3, label='Текстовые', color="#005da8")
        if len(dau_voice.index):
            plt.bar(dau_voice.index, dau_voice.values, width=0.3, label='Воисы', color="#4CAF50")
        plt.title('Статистика кол-ва сообщений по дням')
        plt.legend()
        plt.savefig(f'out/{user_id}_stat.png')
        plt.close('all')

    def get_user_stat(self, user_id, res, user=True):
        df = pd.DataFrame({"msg_type": [i.type for i in res.messages],
                           "send_time": [i.start_date for i in res.messages]})
        df['day'] = df['send_time'].dt.strftime('%Y-%m-%d')
        dau_text = df[df['msg_type'] == 'text']
        dau_text = dau_text.groupby('day')['msg_type'].count()
        dau_voice = df[df['msg_type'] == 'voice']
        dau_voice = dau_voice.groupby('day')['msg_type'].count()
        if user:
            self.make_pic(dau_text, dau_voice, user_id)
        total_types = df.groupby('msg_type')['send_time'].count()
        sessions = self.get_sessions(res.messages)
        days_act = len(df.groupby('day'))
        return total_types.to_dict(), sessions, days_act

    def get_all_stat(self):
        db_sess = db_session.create_session()
        res = db_sess.query(User).all()
        df = pd.DataFrame({"ind": [], 'name': [], 'total_len': [], 'total_seconds': [], 'daily_act': []})
        cnt = 0
        for user in res:
            df2 = pd.DataFrame({"ind": [cnt], 'name': [user.name], 'total_len': [user.stat[0].total_len],
                                'total_seconds': [user.stat[0].total_seconds.total_seconds()],
                                'daily_act': [self.get_user_stat(user.telegram_id, user,
                                                                 user=False)[-1]]})
            cnt += 1
            df = df.append(df2)
        df = df.sort_values(by=['daily_act', 'total_len', 'total_seconds'], ascending=False)[:10].set_index("name")
        return df

    async def send_msg_user_stat(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        user_id = update.message.from_user.id
        db_sess = db_session.create_session()
        res = db_sess.query(User).filter(User.telegram_id == user_id).first()
        types_total, sessions, days_act = self.get_user_stat(user_id, res)
        im = open(f'out/{user_id}_stat.png', mode='rb')
        try:
            r = f'{int(sum(sessions[0]) / len(sessions[0]))} секунд'
        except Exception:
            r = 'Нет данных'
        s = f'📊 Ваша статистика 📊\nДней активности: {days_act}\n==========\n' \
            f'Число сессий: {sessions[1]}\nСредняя продолжительность сессии: ' \
            f'{r}\n==========\nОбщее число сообщений: ' \
            f'{int(sum(types_total.values()))}\nЧисло текстовых сообщений: {int(types_total.get("text", 0))}\n' \
            f'Число воисов: {types_total.get("voice", 0)}\nСуммарная длина сообщений: ' \
            f'{int(res.stat[0].total_len)} символов\nСуммарная продолжительность воисов: ' \
            f'{int(res.stat[0].total_seconds.total_seconds())} секунд\n\n❔Сессия - общение человека с ботом с перерывом' \
            f' не более 5 минут. Сессии отсчитываются, если было прописано хотя бы 2 сообщения'
        await bot.send_photo(update.message.chat.id, im, caption=s)

    async def send_all_stat(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        res = self.get_all_stat().to_dict('index')
        s = "🏆ТОП пользователей🏆\n\n"
        cnt = 1
        for i in res:
            s += f"{cnt}. {i}\nКол-во активных дней: {int(res[i]['daily_act'])}\nСумм. длина сообщ.: " \
                 f"{int(res[i]['total_len'])} символов\nСумм. продолж. воисов: {int(res[i]['total_seconds'])} секунд\n\n"
            cnt += 1
        await bot.send_message(update.message.chat.id, s)


class NearStation:
    async def start(self, update, context):
        total_msg_func(update)
        if context.user_data.get('in_conversation'):
            await update.message.reply_text('Для начала выйди из предыдущего диалога.')
            return ConversationHandler.END
        context.user_data['in_conversation'] = True
        reply_markup = await choose_way()
        if context.user_data.get('voice') is None:
            context.user_data['voice'] = 'alena'
        await update.message.reply_text(
            'Привет. Чтобы узнать название станции метро поблизости, выбери, как ты пришлешь адрес:',
            reply_markup=reply_markup)
        return 1

    async def from_address(self, update, context):
        query = update.callback_query
        await query.answer()
        num = query.data
        chat = query.message.chat.id
        if num == '1':
            await query.edit_message_text(text="Выбранный способ: Геопозицией")
            kbrd = await location_kbrd()
            await bot.send_message(chat, 'Что ж, тогда присылай геопозицию.', reply_markup=kbrd)
            return 2
        else:
            await query.edit_message_text(text="Выбранный способ: Текстом (напишу адрес)")
            await bot.send_message(chat,
                                   'Что ж, тогда пиши адрес места.')
            return 3

    async def address_loc(self, update, context):
        user_location = update.message.location
        context.user_data['metro'] = {'coords': (user_location.latitude, user_location.longitude)}
        res = await get_nearest_metro_station(coords=context.user_data['metro']['coords'], place=None)
        await bot.send_message(update.message.chat.id, prepare_for_markdown(res),
                               reply_markup=ReplyKeyboardRemove(), parse_mode='MarkdownV2')
        await bot.send_voice(update.message.chat.id, await get_audio(res, context.user_data['voice']))
        context.user_data['in_conversation'] = False
        return ConversationHandler.END

    async def address_name(self, update, context):
        total_msg_func(update)
        context.user_data['metro'] = {'place': update.message.text}
        res = await get_nearest_metro_station(place=context.user_data['metro']['place'], coords=None)
        await bot.send_message(update.message.chat.id, prepare_for_markdown(res),
                               reply_markup=ReplyKeyboardRemove(), parse_mode='MarkdownV2')
        await bot.send_voice(update.message.chat.id, await get_audio(res, context.user_data['voice']))
        context.user_data['in_conversation'] = False
        return ConversationHandler.END

    async def stop(self, update, context):
        await bot.send_message(update.message.chat.id, 'Возвращайся!', reply_markup=ReplyKeyboardRemove())
        context.user_data['in_conversation'] = False
        return ConversationHandler.END


async def send_anecdot(update, context):
    total_msg_func(update)
    if context.user_data.get('in_conversation'):
        await update.message.reply_text('Для начала выйди из предыдущего диалога.')
        return
    chat = update.message.chat.id
    text = await get_anecdot()
    audio = await get_audio(text, context.user_data['voice'])
    await bot.send_message(chat, text)
    await bot.send_voice(chat, audio)


def main():
    try:
        if not os.path.exists('out/'):
            os.mkdir("out/")
    except:
        pass
    application = Application.builder().token(BOT_TOKEN).build()
    dialog = Dialog()
    navi = MapRoute()
    voice_config_start = ConfigVoice()
    game_towns = GameTowns()
    ai_dialog = ChatGPTDialog()
    news_dialog = News()
    weather_dialog = Weather()
    stats = Stats()
    station = NearStation()
    settings = MainSettings()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start_dialog', dialog.start_dialog)],
        states={
            1: [MessageHandler(filters.VOICE, dialog.send_stt_msg_dialog),
                MessageHandler(filters.TEXT & ~filters.COMMAND, dialog.send_tts_msg_dialog)]
        },
        fallbacks=[CommandHandler('stop_dialog', dialog.stop_dialog)], block=True, conversation_timeout=60
    )
    navigator_dialog = ConversationHandler(
        entry_points=[CommandHandler('route', navi.navigator_start)],
        states={
            1: [CallbackQueryHandler(navi.from_address)],
            2: [MessageHandler(filters.LOCATION, navi.address_loc)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, navi.address_name)],
            4: [CallbackQueryHandler(navi.to_address)],
            5: [MessageHandler(filters.LOCATION, navi.address_loc_to)],
            6: [MessageHandler(filters.TEXT & ~filters.COMMAND, navi.address_name_to)]
        },
        fallbacks=[CommandHandler('stop_route', navi.stop_navigator)], block=True, conversation_timeout=60
    )
    config_voice_handler = ConversationHandler(
        entry_points=[CommandHandler("start", voice_config_start.start),
                      CommandHandler("config_voice", voice_config_start.config_voice)],
        states={
            1: [CallbackQueryHandler(voice_config_start.inline_button)]
        },
        fallbacks=[MessageHandler(filters.ALL, voice_config_start.get_out)], block=True, conversation_timeout=60
    )
    game_towns_conv = ConversationHandler(
        entry_points=[CommandHandler('towns', game_towns.start_game)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, game_towns.get_name)]
        },
        fallbacks=[CommandHandler('end_game', game_towns.end_game)], block=True, conversation_timeout=60
    )
    ai_dialog_conv = ConversationHandler(
        entry_points=[CommandHandler('ai', ai_dialog.start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_dialog.text_request),
                MessageHandler(filters.VOICE, ai_dialog.audio_request)]
        },
        fallbacks=[CommandHandler('stop_ai', ai_dialog.stop_ai)], block=True, conversation_timeout=60
    )

    news_dialog_handler = ConversationHandler(
        entry_points=[CommandHandler("news", news_dialog.send_news)],
        states={
            1: [CallbackQueryHandler(news_dialog.send_news_new)]
        },
        fallbacks=[CommandHandler('end_news', news_dialog.end_new)], block=True, conversation_timeout=60
    )
    weather_dialog_handler = ConversationHandler(
        entry_points=[CommandHandler('pogoda', weather_dialog.weather_start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, weather_dialog.weather_address)],
            2: [CallbackQueryHandler(weather_dialog.change_date)]
        },
        fallbacks=[CommandHandler('stop_pogoda', weather_dialog.stop_weather)], block=True, conversation_timeout=60
    )
    nearest_station_conv = ConversationHandler(
        entry_points=[CommandHandler('metro', station.start)],
        states={
            1: [CallbackQueryHandler(station.from_address)],
            2: [MessageHandler(filters.LOCATION, station.address_loc)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, station.address_name)]
        },
        fallbacks=[CommandHandler('stop_metro', station.stop)], block=True,
        conversation_timeout=60
    )
    application.add_handlers(handlers={
        1: [conv_handler], 2: [navigator_dialog], 3: [config_voice_handler], 4: [game_towns_conv],
        5: [ai_dialog_conv], 6: [CommandHandler('anecdot', send_anecdot)],
        7: [news_dialog_handler], 14: [weather_dialog_handler],
        8: [CommandHandler('profile', stats.send_msg_user_stat)],
        9: [CommandHandler('stat', stats.send_all_stat)],
        10: [nearest_station_conv], 11: [CommandHandler('about', settings.about)],
        12: [CommandHandler('help', settings.help)], 13: [CommandHandler('report', settings.report)]
    }
    )

    application.run_polling()


if __name__ == '__main__':
    db_session.global_init("database/telegram_bot.db")
    main()
