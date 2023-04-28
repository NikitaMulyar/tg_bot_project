# -*- coding: utf-8 -*-
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup
import aiohttp
import math
from consts import *
import openai
import string

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
        name = i.get_text('###').split('###')[-2] + '\n'
        link = 'https://life.ru' + i.get('href')
        arr.append((name, link))
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
    db_sess.close()


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
    db_sess.close()


async def get_nearest_metro_station(coords=None, place=None):
    if place is None:
        place = await get_address_text(coords)
    elif coords is None:
        coords = await get_coords(place)
    if place == '-1' or coords == -1:
        return 'Неверно введен адрес.'
    try:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        url = f'https://geocode-maps.yandex.ru/1.x/?apikey=40d1649f-0493-4b70-98ba-98533de7710b&geocode=' \
              f'{",".join([str(i) for i in coords][::-1])}&kind=metro&format=json'
        async with session.get(url) as res:
            name = await res.json()
            res.close()
        await session.close()
        pos = name['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos'].split()
        pos = [float(i) for i in pos]
        dist = lonlat_distance(pos, (coords[1], coords[0]))
        metrost = name['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['name']
        return f'Ближайшая станция метро рядом с {place}: ' + metrost + f'.\nРасстояние до {metrost}: {int(dist)} метров.'
    except Exception as e:
        await session.close()
        return 'Данные о ближайшей станции отсутствуют.'


def lonlat_distance(a, b):
    degree_to_meters_factor = 111000
    a_lon, a_lat = a
    b_lon, b_lat = b

    radians_lattitude = math.radians((a_lat + b_lat) / 2.0)
    lat_lon_factor = math.cos(radians_lattitude)

    dx = abs(a_lon - b_lon) * degree_to_meters_factor * lat_lon_factor
    dy = abs(a_lat - b_lat) * degree_to_meters_factor

    distance = math.sqrt(dx * dx + dy * dy)

    return distance


if __name__ == '__main__':
    print(get_answer('Приветики-пистолетики! Как настроение?'))
