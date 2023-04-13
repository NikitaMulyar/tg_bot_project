from telegram.ext import Application, MessageHandler, filters, CommandHandler, ConversationHandler, \
    CallbackQueryHandler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from config import BOT_TOKEN
from yandex_cloud import *
from consts import *
from funcs_backend import *


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)

session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
bot = Bot(BOT_TOKEN)


async def start(update, context):
    context.user_data['skip_voice'] = False
    context.user_data['voice'] = 'alena'
    await update.message.reply_text('Привет! Давай знакомиться. Я - Великий Гуру, умею общаться с людьми голосом!')
    await config_voice(update, context)
    return 1


async def start_dialog(update, context):
    await update.message.reply_text('Давай поболтаем! Отправляй мне воисы - а я тебе их расшифровку, и наоборот!\n'
                                    'Но учти - если воис не на русском языке, я не гарантирую хороший перевод!')
    return 1


async def send_tts_msg_dialog(update, context):
    t = ' '.join([i.strip() for i in update.message.text.split('\n') if i.strip() != ''])
    result = await get_audio(t, context.user_data['voice'])
    chat = update.message.chat.id
    if result != -1:
        await bot.sendVoice(chat, result)
        return
    await update.message.reply_text('Длина сообщений должна быть <= 4000 символам.')
    return 1


async def send_stt_msg_dialog(update, context):
    path = await update.message.voice.get_file()
    file = await path.download_as_bytearray()
    chat = update.message.chat.id
    result = get_text_api_v3(file, chat, logger)
    await bot.sendMessage(chat, result)
    return 1


async def stop_dialog(update, context):
    await update.message.reply_text('Возвращайся скорее!')
    return ConversationHandler.END


async def config_voice(update, context):
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


async def inline_button(update, context):
    query = update.callback_query
    await query.answer()
    if context.user_data.get('skip_voice'):
        chat = query.message.chat.id
        await bot.send_message(chat, "Выбор голоса пропущен. Пропишите команду еще раз.")
        return ConversationHandler.END
    num = query.data
    context.user_data['voice'] = VOICES[num][0]
    await query.edit_message_text(text=f"Выбранный голос: {VOICES[num][1]}")
    return ConversationHandler.END


async def get_out(update, context):
    context.user_data['skip_voice'] = True
    chat = update.message.chat.id
    await bot.send_message(chat, "Выбор голоса пропущен. Пропишите команду еще раз.")
    return ConversationHandler.END


async def navigator_start(update, context):
    reply_markup = await choose_way()
    if context.user_data.get('voice') is None:
        context.user_data['voice'] = 'alena'
    await update.message.reply_text('Привет. Чтобы узнать информацию о маршруте, для начала выбери, '
                                    'как ты пришлешь место отправления:', reply_markup=reply_markup)
    return 1


async def from_address(update, context):
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


async def address_loc(update, context):
    user_location = update.message.location
    context.user_data['geopos'] = {'from': (user_location.latitude, user_location.longitude)}
    reply_markup = await choose_way()
    await update.message.reply_text(
        'Вау! А теперь выбери, как ты пришлешь место назначения:', reply_markup=reply_markup)
    return 4


async def address_name(update, context):
    reply_markup = await choose_way()
    res = await get_coords(update.message.text)
    if res == -1:
        await update.message.reply_text('Такого адреса нет. Давай еще разок.')
        return 3
    context.user_data['geopos'] = {'from': res}
    await update.message.reply_text(
        'Вау! А теперь выбери, как ты пришлешь место назначения:', reply_markup=reply_markup)
    return 4


async def to_address(update, context):
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


async def address_loc_to(update, context):
    user = update.message.from_user
    user_location = update.message.location
    context.user_data['geopos']['to'] = (user_location.latitude, user_location.longitude)
    res = await make_path(context.user_data['geopos'])
    if res == -1:
        await update.message.reply_text('Увы, но пути нет.')
    else:
        pass
    return ConversationHandler.END


async def address_name_to(update, context):
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
        text += "\n".join([i[0] + ': ' + i[1][0] + ' (' + ", ".join(i[1][1:]) + ')' for i in res[0]])
        await bot.send_message(chat, text)
        await bot.send_voice(chat, audio)
    return ConversationHandler.END


async def stop_navigator(update, context):
    await update.message.reply_text('Ну раз не хочешь, ну и ладно!')
    return ConversationHandler.END


def main():
    try:
        if not os.path.exists('out/'):
            os.mkdir("out/")
    except:
        pass
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start_dialog', start_dialog)],
        states={
            1: [MessageHandler(filters.VOICE, send_stt_msg_dialog),
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_tts_msg_dialog)]
        },
        fallbacks=[CommandHandler('stop_dialog', stop_dialog)]
    )
    navigator_dialog = ConversationHandler(
        entry_points=[CommandHandler('route', navigator_start)],
        states={
            1: [CallbackQueryHandler(from_address)],
            2: [MessageHandler(filters.LOCATION, address_loc)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_name)],
            4: [CallbackQueryHandler(to_address)],
            5: [MessageHandler(filters.LOCATION, address_loc_to)],
            6: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_name_to)]
        },
        fallbacks=[CommandHandler('stop_route', stop_navigator)]
    )
    config_voice_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),
                      CommandHandler("config_voice", config_voice)],
        states={
            1: [CallbackQueryHandler(inline_button)]
        },
        fallbacks=[MessageHandler(filters.ALL, get_out)]
    )
    application.add_handler(config_voice_handler)
    application.add_handler(conv_handler)
    application.add_handler(navigator_dialog)

    application.run_polling()


if __name__ == '__main__':
    main()
