from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup
import aiohttp
import asyncio
from consts import *


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
    url = f'https://yandex.ru/maps/213/moscow/?ll={a[0]}%2C{a[1]}&mode=routes&routes%5BactiveComparisonMode%5D=auto&rtext={a[0]}%2C{a[1]}~{b[0]}%2C{b[1]}&rtt=comparison'
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    async with session.get(url) as res:
        txt = await res.text()
        res.close()
    await session.close()
    sp = BeautifulSoup(txt, 'html.parser')
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

    toponym = json_response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]\
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


if __name__ == '__main__':
    asyncio.run(get_time_paths())
