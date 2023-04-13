# ----------------------------------------------------------------------------------------------------------------------
# anecdotica.py - Python-библиотека для работы с API сайта anecdotica.ru
# Python 3.8
# ver. 1.2, 03.09.2022, Андрей Шевченко <anecdotika@yandex.ru>
# Изменения:
# + параметр country для API Lev. 1 (getRandItem)
# + API Lev. 3 (getRandItemT)
# доработан метод send_query в AnecdoticaApiCore
# ----------------------------------------------------------------------------------------------------------------------
import json
import hashlib
import logging
import requests
import time
from urllib.parse import quote_plus

# ----------------------------------------------------------------------------------------------------------------------
# Общие настройки
# ----------------------------------------------------------------------------------------------------------------------
API_URL = 'http://anecdotica.ru/api'  # http-адрес API
# Настройки для режима отладки
API_LOGFILE = 'api_errors.log'  # путь к файлу лога
API_LOGGING = 0  # логирование (0 - выкл., 1 - вкл.)

if API_LOGGING:
    logging.basicConfig(filename=API_LOGFILE, level=logging.INFO, format='%(asctime)s : %(levelname)s : %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')  # настройка формата вывода в лог
# ----------------------------------------------------------------------------------------------------------------------


class AnecdoticaApiCore:
    """Базовый класс"""
    DEFAULT_SETTINGS = {'charset': 'utf-8', 'format': 'json'}
    reply = None
    called_from = None

    def __init__(self, profile, settings=None, handler=None):
        self.profile = profile
        self.settings = settings
        self.handler = handler

    def set_param(self, name, value):
        self.settings[name] = value

    @staticmethod
    def log_error(result):
        """Запись информации об ошибке в лог"""
        if API_LOGGING and result:  # если логирование включено
            msg = str(result.get_error()) + ' (' + result.get_err_msg() + ')'
            logging.error(msg)  # пишем в лог

    @staticmethod
    def set_error(err_code, err_msg):
        """Возвращаем информацию об ошибке"""
        return json.dumps({'result': {'error': err_code, 'errMsg': err_msg}})

    @staticmethod
    def get_setting(settings, name):
        """Получение значения параметра с именем name"""
        return settings.get(name)

    @staticmethod
    def send_query(params, profile):
        """Выполнение запроса к API"""
        content = None
        params['uts'] = int(time.time())

        try:
            url_params = ''
            for key in params:
                if url_params == '':
                    und = ''
                else:
                    und = '&'
                if params[key] is not None:
                    if isinstance(params[key], str):
                        params[key] = quote_plus(params[key])
                    url_params = url_params + und + key + '=' + str(params[key])

            md5hash = hashlib.md5((url_params + profile['key']).encode())
            api_url = API_URL + '?' + url_params + '&hash=' + md5hash.hexdigest()

            if profile['http_method'] == 'GET':
                content = requests.get(api_url)  # GET-запрос
            elif profile['http_method'] == 'POST':
                content = requests.post(api_url)  # POST-запрос
            else:
                content = AnecdoticaApiCore.set_error(7, 'FORBIDDEN_HTTP_METHOD')

            if content is None:
                content = AnecdoticaApiCore.set_error(103, 'NO_CONTENT_RECEIVED')
            elif hasattr(content, 'status_code'):
                if content.status_code == 200:  # 200
                    content = content.text
                else:  # http-error
                    content = AnecdoticaApiCore.set_error(102, 'HTTP_REQUEST_FAILED')

        except (ConnectionError, ConnectionRefusedError):
            content = AnecdoticaApiCore.set_error(102, 'HTTP_REQUEST_FAILED')
        except Exception as e:
            content = AnecdoticaApiCore.set_error(102, 'HTTP_REQUEST_FAILED')

        reply = json.loads(content)
        return reply

    def get_next_reply(self, handler=None):
        self.reply = self._get_reply(self.called_from, self.profile, self.settings,
                                     self.handler if handler is None else handler)
        return self.reply

    @staticmethod
    def _get_reply(cls, profile, settings=None, handler=None):
        params = cls.set_params(profile, settings)
        reply = ApiReply(cls.send_query(params, profile))
        if reply.is_error():
            AnecdoticaApiCore.log_error(reply.get_result())
            if handler is not None:
                handler.on_error(reply.get_result())
        else:
            if handler is not None:
                handler.on_success(reply.get_data())
        return reply


class ApiReply:
    """Класс ответа сервера"""
    item = None
    items = None

    def __init__(self, data):
        self.result = Result(data.get('result'))
        if data.get('item') is not None:
            self.item = Item(data.get('item'))
        if data.get('items') is not None:
            self.items = Items(data.get('items'), data.get('info'))

    def is_error(self):
        return self.result.is_error()

    def get_result(self):
        return self.result

    def get_item(self):
        return self.item

    def get_items(self):
        return self.items

    def get_data(self):
        data = None
        if self.item is not None:
            data = self.item
        elif self.items is not None:
            data = self.items
        return data


class DataElement:
    """Класс элемента данных"""
    data = {}

    def __init__(self, data):
        self.data = data

    def as_array(self):
        return self.data


class Result(DataElement):
    """Класс элемента данных Result"""

    def get_error(self):
        return None if self.data['error'] == '' else self.data['error']

    def get_err_msg(self):
        return None if self.data['errMsg'] == '' else self.data['errMsg']

    def is_error(self):
        return not (self.data['error'] == '' or self.data['error'] == 0)


class Item(DataElement):
    """Класс записи Item"""

    def get_text(self):
        text = self.data.get('text')
        if text is None:
            text = ''
        return text

    def get_note(self):
        text = self.data.get('note')
        if text is None:
            text = ''
        return text


class Items(DataElement):
    """Класс списка записей Items"""
    info = None
    index = 0

    def __init__(self, items, info):
        super().__init__(items)
        self.info = info

    def reset(self):
        self.index = 0

    def get_item(self, index=None):
        if index is None:
            index = self.index
            self.index += 1
        return Item(self.data[index])

    def has_item(self, index=None):
        if index is None:
            index = self.index
        if 0 <= index < len(self.data):
            result = self.data[index] is not None
        else:
            result = False
        return result

    def get_num(self):
        return 0 if self.info.get('n') is None else self.info.get('n')

    def get_size(self):
        return 0 if self.info.get('size') is None else self.info.get('size')

    def get_page(self):
        return 0 if self.info.get('page') is None else self.info.get('page')

    def get_max_page(self):
        return 0 if self.info.get('max_page') is None else self.info.get('max_page')

    def get_ipp(self):
        return 0 if self.info.get('ipp') is None else self.info.get('ipp')


class RandomItemApi(AnecdoticaApiCore):
    """API Level 1"""
    DEF_METHOD = 'getRandItem'

    def __init__(self, profile, settings=None, handler=None):
        super().__init__(profile, settings, handler)
        self.called_from = __class__

    @staticmethod
    def get_reply(profile, settings=None, handler=None):
        reply = AnecdoticaApiCore._get_reply(__class__, profile, settings, handler)
        return reply

    @staticmethod
    def set_params(profile, settings):
        return {
            'pid': profile['pid'],
            'method': __class__.DEF_METHOD,
            'format': __class__.DEFAULT_SETTINGS['format'],
            'charset': __class__.DEFAULT_SETTINGS['charset'],
            'category': __class__.get_setting(settings, 'category'),
            'genre': __class__.get_setting(settings, 'genre'),
            'country': __class__.get_setting(settings, 'country'),
            'lang': __class__.get_setting(settings, 'lang'),
            'markup': __class__.get_setting(settings, 'markup'),
            'note': __class__.get_setting(settings, 'note')
        }


class RandomItemParamApi(AnecdoticaApiCore):
    """API Level 2"""
    DEF_METHOD = 'getRandItemP'

    def __init__(self, profile, settings=None, handler=None):
        super().__init__(profile, settings, handler)
        self.called_from = __class__

    @staticmethod
    def get_reply(profile, settings=None, handler=None):
        reply = AnecdoticaApiCore._get_reply(__class__, profile, settings, handler)
        return reply

    @staticmethod
    def set_params(profile, settings):
        return {
            'pid': profile['pid'],
            'method': __class__.DEF_METHOD,
            'format': __class__.DEFAULT_SETTINGS['format'],
            'charset': __class__.DEFAULT_SETTINGS['charset'],
            'tag': __class__.get_setting(settings, 'tag'),
            'category': __class__.get_setting(settings, 'category'),
            'series': __class__.get_setting(settings, 'series'),
            'country': __class__.get_setting(settings, 'country'),
            'genre': __class__.get_setting(settings, 'genre'),
            'lang': __class__.get_setting(settings, 'lang'),
            'wlist': __class__.get_setting(settings, 'wlist'),
            'censor': __class__.get_setting(settings, 'censor'),
            'markup': __class__.get_setting(settings, 'markup'),
            'note': __class__.get_setting(settings, 'note')
        }


class RandomItemTagsApi(AnecdoticaApiCore):
    """API Level 3"""
    DEF_METHOD = 'getRandItemT'

    def __init__(self, profile, settings=None, handler=None):
        super().__init__(profile, settings, handler)
        self.called_from = __class__

    @staticmethod
    def get_reply(profile, settings=None, handler=None):
        reply = AnecdoticaApiCore._get_reply(__class__, profile, settings, handler)
        return reply

    @staticmethod
    def set_params(profile, settings):
        return {
            'pid': profile['pid'],
            'method': __class__.DEF_METHOD,
            'format': __class__.DEFAULT_SETTINGS['format'],
            'charset': __class__.DEFAULT_SETTINGS['charset'],
            'tags': __class__.get_setting(settings, 'tags'),
            'precision': __class__.get_setting(settings, 'precision'),
            'priority': __class__.get_setting(settings, 'priority'),
            'category': __class__.get_setting(settings, 'category'),
            'series': __class__.get_setting(settings, 'series'),
            'country': __class__.get_setting(settings, 'country'),
            'genre': __class__.get_setting(settings, 'genre'),
            'lang': __class__.get_setting(settings, 'lang'),
            'wlist': __class__.get_setting(settings, 'wlist'),
            'censor': __class__.get_setting(settings, 'censor'),
            'markup': __class__.get_setting(settings, 'markup'),
            'note': __class__.get_setting(settings, 'note')
        }


class ItemsApi(AnecdoticaApiCore):
    """API Level 4"""
    DEF_METHOD = 'getItems'

    def __init__(self, profile, settings=None, handler=None):
        super().__init__(profile, settings, handler)
        self.called_from = __class__

    def get_page(self, page=0, handler=None):
        self.settings['page'] = page
        self.reply = self._get_reply(self.called_from, self.profile, self.settings,
                                     self.handler if handler is None else handler)
        return self.reply

    @staticmethod
    def get_reply(profile, settings=None, handler=None):
        reply = AnecdoticaApiCore._get_reply(__class__, profile, settings, handler)
        return reply

    @staticmethod
    def set_params(profile, settings):
        return {
            'pid': profile['pid'],
            'method': __class__.DEF_METHOD,
            'format': __class__.DEFAULT_SETTINGS['format'],
            'charset': __class__.DEFAULT_SETTINGS['charset'],
            'page': __class__.get_setting(settings, 'page'),
            'ipp': __class__.get_setting(settings, 'ipp'),
            'tag': __class__.get_setting(settings, 'tag'),
            'category': __class__.get_setting(settings, 'category'),
            'series': __class__.get_setting(settings, 'series'),
            'country': __class__.get_setting(settings, 'country'),
            'genre': __class__.get_setting(settings, 'genre'),
            'lang': __class__.get_setting(settings, 'lang'),
            'wlist': __class__.get_setting(settings, 'wlist'),
            'censor': __class__.get_setting(settings, 'censor'),
            'markup': __class__.get_setting(settings, 'markup'),
            'note': __class__.get_setting(settings, 'note')
        }


class ApiHandlerInterface:
    """Класс обработки результатов запроса"""

    # Замечание по использованию собственных обработчиков:
    # 1) создать класс, наследующий ApiHandlerInterface
    # 2) переопределить методы класса on_success и on_error.

    def on_success(self, data):  # data: Item | Items
        """Пользовательский обработчик при успешном запросе"""
        # Вызывается при отсутствии ошибки
        pass

    def on_error(self, error: Result):
        """Пользовательский обработчик ошибки"""
        # Вызывается в случае ошибки (код и описание ошибки)
        pass
