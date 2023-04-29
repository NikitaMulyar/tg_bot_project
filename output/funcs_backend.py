# -*- coding: utf-8 -*-
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup
import aiohttp
import asyncio
from consts import *
import openai
import string
import requests

from data import db_session
from data.users import User
from data.big_data import Big_data
from data.statistics import Statistic
import datetime


async def location_kbrd():
    btn_loc = KeyboardButton('Отправить геопозицию', request_location=True)
    # btn_loc2 = KeyboardButton('Не отправлять геопозицию', request_location=False)
    kbd = ReplyKeyboardMarkup([[btn_loc]], one_time_keyboard=True, resize_keyboard=True)
    return kbd


async def choose_way():
    keyboard = [
        [
            InlineKeyboardButton("Геопозицией", callback_data="1")
        ],
        [
            InlineKeyboardButton("Текстом (напишу адрес)", callback_data="2")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def get_time_paths(a, b):
    url = f'https://yandex.ru/maps/?ll={a[1]}%2C{a[0]}&mode=routes&routes%5BactiveComparisonMode%5D=auto&rtext={a[0]}%2C{a[1]}~{b[0]}%2C{b[1]}&rtt=comparison'
    print(url)
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    async with session.get(url) as res:
        txt = await res.text()
        res.close()
    await session.close()
    sp = BeautifulSoup(txt, 'html.parser')
    print(sp.text)
    res = []
    for i in sp.find_all('div', class_='comparison-route-snippet-view__route-title'):
        s = i.get_text(separator=';').split(';')
        res.append([s[0], s[1:]])
    cnt = 0
    for i in sp.find_all('div', class_='comparison-route-snippet-view__route-subtitle'):
        s = i.get_text()
        res[cnt][1].append(s)
        cnt += 1
    return res


async def make_path(geopos):
    res = await get_time_paths(geopos['from'], geopos['to'])
    if len(res) == 0:
        return -1
    image = await get_map(geopos['from'], geopos['to'])
    if image == -1:
        return -1
    return res, image


async def get_coords(address):
    geocoder_params = {
        "apikey": API_GEO,
        "geocode": address,
        "format": "json"}

    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    try:
        async with session.get(URL_GEOCODER, params=geocoder_params) as res:
            json_response = await res.json()
            res.close()
        await session.close()
    except Exception:
        await session.close()
        return -1

    toponym = json_response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
    toponym_coodrinates = toponym["Point"]["pos"]
    toponym_longitude, toponym_lattitude = toponym_coodrinates.split(" ")
    return float(toponym_lattitude), float(toponym_longitude)


async def get_address_text(pos):
    geocoder_params = {
        "apikey": API_GEO,
        "geocode": f"{pos[1]}, {pos[0]}",
        "format": "json"}

    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    try:
        async with session.get(URL_GEOCODER, params=geocoder_params) as res:
            json_response = await res.json()
            res.close()
            await session.close()
    except Exception:
        await session.close()
        return '-1'

    toponym = json_response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"] \
        ["metaDataProperty"]["GeocoderMetaData"]["text"]
    return toponym


async def get_map(a, b):
    map_params = {
        "ll": ",".join([str((a[1] + b[1]) / 2), str((a[0] + b[0]) / 2)]),
        "l": "map",
        "pt": "~".join([f"{a[1]},{a[0]},pm2am", f"{b[1]},{b[0]},pm2bm"])
    }
    print("~".join([f"{a[1]},{a[0]},pm2am", f"{b[1]},{b[0]},pm2bm"]))
    import requests
    try:
        image = requests.get(URL_MAPS, params=map_params).content
        return image
    except Exception:
        return -1
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    try:
        async with session.get(URL_MAPS, params=map_params) as res:
            image = await res.content.read()
            res.close()
            await session.close()
    except Exception:
        await session.close()
        return -1

    return image


async def get_w(txt):
    if txt == 'clear':
        txt = '🌞 Ясно'
    elif txt == 'partly-cloudy':
        txt = '🌤 Малооблачно'
    elif txt == 'cloudy':
        txt = '⛅Облачно с прояснениями'
    elif txt == 'overcast':
        txt = '☁ Пасмурно'
    elif txt == 'drizzle':
        txt = '🌂Морось'
    elif txt == 'light-rain':
        txt = '💧Небольшой дождь'
    elif txt == 'rain':
        txt = '☔Дождь'
    elif txt == 'moderate-rain':
        txt = '🌧Умеренно сильный дождь'
    elif txt == 'heavy-rain':
        txt = '🌧Сильный дождь'
    elif txt == 'continuous-heavy-rain':
        txt = '🌧🌧Длительный сильный дождь'
    elif txt == 'showers':
        txt = '🌧🌧🌧Ливень'
    elif txt == 'wet-snow':
        txt = '💧❄Дождь со снегом'
    elif txt == 'light-snow':
        txt = '❄Небольшой снег'
    elif txt == 'snow':
        txt = '❄☃Снег'
    elif txt == 'snow-showers':
        txt = '🌨Снегопад'
    elif txt == 'hail':
        txt = '😵Град'
    elif txt == 'thunderstorm':
        txt = '⚡Гроза'
    elif txt == 'thunderstorm-with-rain':
        txt = '⛈Дождь с грозой'
    elif txt == 'thunderstorm-with-hail':
        txt = '⛈⛈Гроза с градом'
    return txt


async def get_dir(dir_, tmp=1):
    if tmp == 1:
        if dir_ == 'nw':
            return '↘ С-З'
        if dir_ == 'n':
            return '⬇ С'
        if dir_ == 'ne':
            return '↙ С-В'
        if dir_ == 'e':
            return '⬅ В'
        if dir_ == 'se':
            return '↖ Ю-В'
        if dir_ == 's':
            return '⬆ Ю'
        if dir_ == 'sw':
            return '↗ Ю-З'
        if dir_ == 'w':
            return '➡ З'
        return 'Штиль'
    else:
        if dir_ == 'nw':
            return 'северо-западное.'
        if dir_ == 'n':
            return 'северное'
        if dir_ == 'ne':
            return 'северо-восточное'
        if dir_ == 'e':
            return 'восточное'
        if dir_ == 'se':
            return 'юго-восточное'
        if dir_ == 's':
            return 'южное'
        if dir_ == 'sw':
            return 'юго-западное'
        if dir_ == 'w':
            return 'западное'
        return 'Штиль'


async def get_cl(cl):
    if cl == 0:
        return 'Ясно'
    if cl == 0.25:
        return 'Малооблачно'
    if cl == 0.5 or cl == 0.75:
        return 'Облачно с прояснениями'
    return 'Пасмурно'


async def get_weather(response, name_from, date="fact"):
    phenom = {"fog": "туман",
              "mist": "дымка",
              "smoke": "смог",
              "dust": "пыль",
              "dust-suspension": "пылевая взвесь",
              "duststorm": "пыльная буря",
              "thunderstorm-with-duststorm": "пыльная буря с грозой",
              "drifting-snow": "слабая метель",
              "blowing-snow": "метель",
              "ice-pellets": "ледяная крупа",
              "freezing-rain": "ледяной дождь",
              "tornado": "торнадо",
              "volcanic-ash": "вулканический пепел"}
    for_robot = f"Погода в {name_from}.\nОсновная информация:\n\n"
    text = f"🌍 Погода в {name_from} на дату {response['forecasts'][0]['date']}\nОсновная информация:\n\n"
    text + "На текущий момент наблюдается:\n"
    for_robot += "На текущий момент наблюдается:\n"
    if date == "fact":
        now = response['fact']
    else:
        now = response["forecasts"][date]["parts"]["day"]
    text += f"Ощущаемая температура °C: 🌡{now['feels_like']}\n"
    for_robot += f"Ощущаемая температура {now['feels_like']} градусов.\n"
    text += f"Описание: {await get_w(now['condition'])}\n"
    for_robot += f"Описание: {await get_w(now['condition'])}.\n"
    text += f"Скорость ветра до 💨{now['wind_speed']} м\с\n"
    for_robot += f"Скорость ветра до {now['wind_speed']} метров в секунду.\n"
    text += f"Давление в пределах {now['pressure_mm']} мм.рт.ст\n"
    for_robot += f"Давление в пределах {now['pressure_mm']} миллиметров ртутного столба.\n"
    text += f"\nДополнительная информация:\n"
    for_robot += "Дополнительная информация:"
    if now.get('temp_water'):
        text += f"Температура воды 🌊{now['temp_water']} °C\n"
        for_robot += f"Температура воды {now['temp_water']} градусов."
    text += f"Направление ветра 💨 {await get_dir(now['wind_dir'])}\n"
    for_robot += f"Направление ветра 💨 {await get_dir(now['wind_dir'], tmp=2)}.\n"
    text += f"Влажность составляет {now['humidity']}%\n"
    for_robot += f"Влажность составляет {now['humidity']} процентов.\n"
    text += f"Облачность: {await get_cl(now['cloudness'])}\n"
    for_robot += f"Облачность: {await get_cl(now['cloudness'])}\n"
    if now.get('phenom_condition'):
        text += f"Доп. погодные условия: {phenom[now['phenom_condition']]}"
        for_robot += f"Дополнительные погодные условия: {phenom[now['phenom_condition']]}"
    return text, for_robot


async def get_anecdot():
    url = 'http://anecdotica.ru/'
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    async with session.get(url) as res:
        page = await res.text()
        res.close()
    await session.close()
    sp = BeautifulSoup(page, 'html.parser')
    res = []
    for i in sp.find_all('div', class_='item_text'):
        res.append(i.get_text())
    return '\n'.join(res)


def get_answer(prompt):
    completion = openai.Completion.create(engine="text-davinci-003", prompt=prompt, temperature=0.7,
                                          max_tokens=1000)
    return completion.choices[0]['text']


def prepare_for_markdown(text, spoiler=True):
    res = ''
    if spoiler:
        res += '|| '
    for i in text:
        if i in string.punctuation:
            res += '\\' + i
        else:
            res += i
    if spoiler:
        return res + ' ||'
    return res


async def get_news_list():
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    async with session.get('https://life.ru/s/novosti') as res:
        page = await res.text()
    sp = BeautifulSoup(page, 'html.parser')
    arr = []
    for i in sp.find_all('a', class_='styles_root__2aHN8 styles_l__3AE69 styles_news__15P0n'):
        tmp = i.get_text('###').split('###')
        themes = "🔥 " + " ".join([f"#{el.replace(' ', '_')}" for el in tmp[:-2]]) + "\n\n"
        name = "⚡ " + tmp[-2] + "\n\n"
        time = "🕜 " + tmp[-1]
        link = 'https://life.ru' + i.get('href')
        arr.append((name, f"{themes + name + time}\nПодробнее 👉{link}"))
    return arr


def put_to_db(update):
    db_sess = db_session.create_session()
    user__id = update.message.from_user.id
    if db_sess.query(User).filter(User.telegram_id == user__id).first():
        if not db_sess.query(User).filter(User.telegram_id == user__id, User.chat_id == update.message.chat.id).first():
            user = User(chat_id=update.message.chat.id, telegram_id=user__id, name=update.message.from_user.name)
            db_sess.add(user)
    else:
        user = User(chat_id=update.message.chat.id, telegram_id=user__id, name=update.message.from_user.name)
        db_sess.add(user)
        db_sess.commit()
        db_sess = db_session.create_session()
        statistic = Statistic(user_id=user__id)
        db_sess.add(statistic)
    db_sess.commit()


def total_msg_func(update, msg_format="text"):
    db_sess = db_session.create_session()
    put_to_db(update)
    user = db_sess.query(Statistic).filter(Statistic.user_id == update.message.from_user.id).first()
    if msg_format == "text":
        user.total_len += len("".join(update.message.text.split()))
        user.total_msgs += 1
    else:
        user.total_seconds += datetime.timedelta(seconds=update.message.voice.duration)
        user.total_voices += 1
    big_data = Big_data(user_id=user.user_id, type=msg_format)
    db_sess.add(big_data)
    db_sess.commit()


if __name__ == '__main__':
    print(get_answer('Приветики-пистолетики! Как настроение?'))
