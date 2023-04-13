# coding=utf8
import logging

import grpc

import yandex.cloud.ai.stt.v3.stt_pb2 as stt_pb2
import yandex.cloud.ai.stt.v3.stt_service_pb2_grpc as stt_service_pb2_grpc

import aiohttp
import json
import os

from pyaspeller import YandexSpeller
from consts import *


"""
async def update_iam_token():
    global IAM_TOKEN
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    async with session.post(URL_IAM_TOKEN, params={"yandexPassportOauthToken": OAUTH_TOKEN}) as res:
        k = await res.json()
        with open('TOKEN.txt', mode='w', encoding='utf-8') as file:
            file.write(k['iamToken'])
            IAM_TOKEN = k['iamToken']
        await session.close()
"""


async def get_audio(text, voice):
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    speller = YandexSpeller()
    headers = {
        "Authorization": f"Api-Key {API_KEY}"
    }
    sp_txt = speller.spelled_text(text)
    if len(sp_txt) > MAX_LEN:
        return -1
    async with session.post(URL_SYN, data={"text": sp_txt, "voice": voice, "speed": 1.3},
                            headers=headers) as res:
        k = await res.read()
    res.close()
    await session.close()
    return k


# API V1. Не использовать.
async def get_text(file):
    headers = {'Authorization': f'Api-Key {API_KEY}'}
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
    async with session.post(URL_REC, data=file, headers=headers) as res:
        decode_res = await res.read()
        decode_res = decode_res.decode('UTF-8')  # декодируем
        text = json.loads(decode_res)  # загружаем в json
        if text.get('error_code') is None:
            text = text.get('result')  # забираем текст из json по ключу result
        else:
            text = text.get('error_code')
        res.close()
    await session.close()
    return text


def generate_text(audio_file):
    # Specify the recognition settings.
    recognize_options = stt_pb2.StreamingOptions(
        recognition_model=stt_pb2.RecognitionModelOptions(
            audio_format=stt_pb2.AudioFormatOptions(
                container_audio=stt_pb2.ContainerAudio(
                    container_audio_type=stt_pb2.ContainerAudio.OGG_OPUS
                )
            ),
            text_normalization=stt_pb2.TextNormalizationOptions(
                text_normalization=stt_pb2.TextNormalizationOptions.TEXT_NORMALIZATION_ENABLED,
                literature_text=True
            ),
            language_restriction=stt_pb2.LanguageRestrictionOptions(
                restriction_type=stt_pb2.LanguageRestrictionOptions.WHITELIST,
                language_code=['ru-RU']
            ),
            audio_processing_type=stt_pb2.RecognitionModelOptions.FULL_DATA
        )
    )
    # Send a message with recognition settings.
    yield stt_pb2.StreamingRequest(session_options=recognize_options)
    # Read the audio file and send its contents in portions.
    with open(audio_file, 'rb') as f:
        data = f.read(CHUNK_SIZE)
        while data != b'':
            yield stt_pb2.StreamingRequest(chunk=stt_pb2.AudioChunk(data=data))
            data = f.read(CHUNK_SIZE)


def get_text_api_v3(audio_file, chat_id, logger: logging.Logger):
    name = f'out/{chat_id}_audio.ogg'
    with open(name, mode='wb') as f:
        f.write(audio_file)
    name = os.path.abspath(name)

    # Establish a connection with the server.
    cred = grpc.ssl_channel_credentials()
    channel = grpc.secure_channel('stt.api.cloud.yandex.net:443', cred)
    stub = stt_service_pb2_grpc.RecognizerStub(channel)
    # Send data for recognition.
    # update_iam_token()
    it = stub.RecognizeStreaming(generate_text(name),
                                 metadata=(('authorization', f'Api-Key {API_KEY}'),
                                           ('x-folder-id', ID_FOLDER)))
    # Process the server responses and output the result to the console.
    try:
        for r in it:
            event_type, alternatives = r.WhichOneof('Event'), None
            if event_type == 'final_refinement':
                # Предложение полностью составлено
                alternatives = [a.text for a in r.final_refinement.normalized_text.alternatives]
                os.remove(name)
                return '\n'.join(alternatives)
    except grpc._channel._Rendezvous as err:
        logger.error(f'Error code {err._state.code}, message: {err._state.details}')
        # raise err
        return f'Error code {err._state.code}, message: {err._state.details}'
