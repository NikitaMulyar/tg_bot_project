import logging
import random

from telegram import Bot, ReplyKeyboardRemove
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ConversationHandler, \
    CallbackQueryHandler

from config import BOT_TOKEN
from funcs_backend import *
from yandex_cloud import *

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
        context.user_data['in_conversation'] = False
        await update.message.reply_text('Возвращайся скорее!')
        return ConversationHandler.END


class MapRoute:
    async def navigator_start(self, update, context):
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
        context.user_data['in_conversation'] = False
        await update.message.reply_text('Ну раз не хочешь, ну и ладно!',
                                        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


class MainSettings:
    async def help(self, update, context):
        pass

    async def about(self, update, context):
        pass

    async def report(self, update, context):
        pass


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
        context.user_data['in_conversation'] = False
        chat = update.message.chat.id
        await update.message.reply_text('|| До встречи\! ||', parse_mode='MarkdownV2')
        await bot.send_voice(chat, await get_audio('До встречи!', context.user_data['voice']))
        return ConversationHandler.END


async def send_news(update, context):
    if context.user_data.get('in_conversation'):
        await update.message.reply_text('Для начала выйди из предыдущего диалога.')
        return
    chat = update.message.chat.id
    news = random.sample(await get_news_list(), k=3)
    text = '\n'.join([i[0] + '...' for i in news])
    md_text = '\n'.join(f'[{prepare_for_markdown(i[0], spoiler=False)}]({i[1]})' for i in news)
    await update.message.reply_text(md_text, parse_mode='MarkdownV2')
    await bot.send_voice(chat, await get_audio(text, context.user_data['voice']))


async def send_anecdot(update, context):
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
    application.add_handlers(handlers={
        1: [conv_handler], 2: [navigator_dialog], 3: [config_voice_handler], 4: [game_towns_conv],
        5: [ai_dialog_conv], 6: [CommandHandler('anecdot', send_anecdot)],
        7: [CommandHandler('news', send_news)]
    })

    application.run_polling()


if __name__ == '__main__':
    db_session.global_init("database/telegram_bot.db")
    main()
