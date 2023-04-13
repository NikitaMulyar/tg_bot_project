from telegram.ext import Application, MessageHandler, filters, CommandHandler, ConversationHandler, \
    CallbackQueryHandler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from config import BOT_TOKEN
from yandex_cloud import *
from consts import *


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)

session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
bot = Bot(BOT_TOKEN)


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


async def start_dialog(update, context):
    await update.message.reply_text('Давай поболтаем! Отправляй мне воисы - а я тебе их расшифровку, и наоборот!\n'
                                    'Но учти - если воис не на русском языке, я не гарантирую хороший перевод!')
    return 1


async def stop_dialog(update, context):
    await update.message.reply_text('Возвращайся скорее!')
    return ConversationHandler.END


async def config_voice(update, context):
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


async def start(update, context):
    context.user_data['voice'] = 'alena'
    await update.message.reply_text('Привет! Давай знакомиться. Я - Великий Гуру, умею общаться с людьми голосом!')
    await config_voice(update, context)


async def inline_button(update, context):
    query = update.callback_query
    await query.answer()
    num = query.data
    context.user_data['voice'] = VOICES[num][0]
    await query.edit_message_text(text=f"Выбранный голос: {VOICES[num][1]}")


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
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(inline_button))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("config_voice", config_voice))
    application.run_polling()


if __name__ == '__main__':
    main()
