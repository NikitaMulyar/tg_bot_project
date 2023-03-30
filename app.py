import logging
from telegram.ext import Application, MessageHandler, filters
from telegram import Bot, Chat
from config import BOT_TOKEN
import os
import aiohttp
import asyncio
from pyaspeller import YandexSpeller
import json
from pathlib import Path


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)

logger = logging.getLogger(__name__)


'''IAM_TOKEN = "CggaATEVAgA..."
ID_FOLDER = "b1gdt133kktmm89lr51l"
OAUTH_TOKEN = "y0_AgAAAAAmLq4dAATuwQAAAADfsx7bRjjHC7ycRfCVmVVaTuuAwIQ6d_Y"
URL = 'https://iam.api.cloud.yandex.net/iam/v1/tokens'
'''
# API_KEY = os.environ["API_KEY"]


API_KEY = 'AQVN3NK_pQrIYcIOpcTNP2CBosKeu2Nd0LgVI_bj'
URL_REC = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize'
URL_SYN = 'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize'
AUDIO_NUM = 1
TEXT_NUM = 1
PATH_AUDIO = ''  # пока вместо алхимии
PATH_TEXT = ''


session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
speller = YandexSpeller()
bot = Bot(BOT_TOKEN)


async def get_audio(text, session):
    global AUDIO_NUM, PATH_AUDIO
    headers = {
        "Authorization": f"Api-Key {API_KEY}"
    }
    sp_txt = speller.spelled_text(text)
    if len(sp_txt) > 80:
        return -1
    async with session.post(URL_SYN, data={"text": sp_txt},
                            headers=headers) as res:
        filename = f"{AUDIO_NUM}.ogg"
        AUDIO_NUM += 1
        with open(f"out/{filename}", "wb") as out:
            k = await res.read()
            out.write(k)
            PATH_AUDIO = f'out/{AUDIO_NUM}.ogg'
    res.close()
    return k


async def get_text(file, session):
    global TEXT_NUM, PATH_TEXT
    headers = {'Authorization': f'Api-Key {API_KEY}'}
    async with session.post(URL_REC, data=file, headers=headers) as res:
        decode_res = await res.read()
        decode_res = decode_res.decode('UTF-8')  # декодируем
        text = json.loads(decode_res)  # загружаем в json
        filename = f"{TEXT_NUM}.txt"
        TEXT_NUM += 1
        with open(f"out/{filename}", "w") as out:
            if text.get('error_code') is None:
                text = text.get('result')  # забираем текст из json по ключу result
                out.write(text)
            else:
                out.write(text.get('error_code'))
            PATH_TEXT = f'out/{PATH_TEXT}.txt'
    return open(f"out/{filename}", "r").read()


async def make_voice(update, context):
    t = ' '.join([i.strip() for i in update.message.text.split('\n') if i.strip() != ''])
    result = await get_audio(t, session)
    chat = update.message.chat.id
    if result != -1:
        await bot.sendVoice(chat, result)
        return
    await update.message.reply_text('В бете длина сообщений должна быть <= 80 символам.')


async def make_text(update, context):
    path = await update.message.voice.get_file()
    file = await path.download_as_bytearray()
    result = await get_text(file, session)
    chat = update.message.chat.id
    await bot.sendMessage(chat, result)


def main():
    try:
        if not os.path.exists('out/'):
            os.mkdir("out")
    except:
        pass
    application = Application.builder().token(BOT_TOKEN).build()
    text_handler = MessageHandler(filters.TEXT, make_voice)
    voice_handler = MessageHandler(filters.VOICE, make_text)
    application.add_handler(text_handler)
    application.add_handler(voice_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
