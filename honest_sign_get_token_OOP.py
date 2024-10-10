import uuid
from sys import exit
import logging
import requests
import os
import datetime
import win32com.client
import json
from typing import Any, Dict
from decouple import config as conf_token
import copy_env_to_script_py
from honest_sign_list_org import InnToCode
import socket
import telebot
import configparser

CAPICOM_LOCAL_MACHINE_STORE = 2
INN_BELETAG = '5902025531'

logging.basicConfig(
    filename=os.environ.get('Temp') + '\\' + os.path.basename(__file__)[:-3] + '_' + datetime.date.today().strftime(
        '%Y-%m-%d') + '.log',
    filemode='a',
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S')

# Создание объекта конфигурации
config = configparser.ConfigParser()
config.read('config.ini')


def get_uuid_data():
    """
    функция получения uuid и data для дальнейшего получения токена ЧЗ
    делаем запрос в ЧЗ
    :return:
    """
    try:
        url = config['crpt_prod']['url'] + '/api/v3/true-api/auth/key'
        r = requests.get(url=url)
    except Exception as exc:
        logging.debug(exc)
        send_telegram(error_text='{0}'.format(exc))
        exit(99)
    return r.json()


class GetTokenHonestSign:

    def __init__(self, org_inn: str = '43000000000', org_sklad: list = None, i_uuid='', i_data='') -> None:
        """
        конструктор класса, инициализируем сразу и дата и ююид
        и серийник сертификата
        """
        if org_sklad is None:
            org_sklad = []
        self.org = ''
        self.uuid = i_uuid
        self.data = i_data
        self.inn = org_inn
        self.destination_folder = org_sklad
        # self.serial_sert = conf_token('serial_number', default=None)
        self.error = False
        self.signed_string = self.get_signed_string()
        self.permission_mode_token = None
        self.token = None

    def getSignerCertificate(self) -> Any:
        """
        получаем сертификат по его серийнику
        из хранилища сертификатов
        :return:
        """
        oStore = win32com.client.Dispatch("CAdESCOM.Store")
        oStore.Open(CAPICOM_LOCAL_MACHINE_STORE)
        pattern = 'CN='
        for elem in oStore.Certificates:
            sert_subject = elem.SubjectName
            list_sert_subject = sert_subject.split(', ')
            if self.inn in elem.SubjectName:
                self.org = [x for x in list_sert_subject if x.find(pattern) >= 0][0].replace(pattern, '')
                return elem
        o_error = 'нет подходящего сертификата для организации с ИНН: ' + self.inn
        logging.debug(o_error)
        raise ValueError(o_error)

    def get_signed_string(self) -> str:
        """
        метод подписи строки дата нашим сертификатом
        :return: str наш токен для работы с API честного знака
        понятия не имею как это работает, скопировал из
        документации криптопро
        """
        cades_bes = 1
        capicom_encode_base64 = 0
        capicom_certificate_include_end_entity_only = 2
        try:
            oSigner = win32com.client.Dispatch('CAdESCOM.CPSigner')
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 100 проблема с плагином криптопро')
            send_telegram(error_text='инн={1}, ошибка={0}'.format(exc, self.inn))
            exit(100)
        try:
            oSigner.Certificate = self.getSignerCertificate()
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 101 проблема с сертификатом')
            send_telegram(error_text='инн={1}, орг={2}, ошибка={0}'.format(exc, self.inn, self.org))
            self.error = True
            return 'error'
        try:
            oSignedData = win32com.client.Dispatch('CAdESCOM.CadesSignedData')
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 102 проблема с подписью данных')
            send_telegram(error_text='инн={1}, ошибка={0}'.format(exc, self.inn))
            # exit(102)
        logging.debug(oSigner)
        logging.debug(oSignedData)
        oSigner.Options = capicom_certificate_include_end_entity_only
        oSignedData.Content = self.data
        out_data = ''
        try:
            out_data = oSignedData.SignCades(oSigner, cades_bes, False, capicom_encode_base64)
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 103')
            send_telegram(error_text='инн={1}, ошибка={0}'.format(exc, self.inn))
            # exit(103)
        out_data3 = out_data.replace('\r\n', '')
        return out_data3

    def get_token(self):
        """
        получение авторизационного токена на получение приватной информации по КМ
        короче это не тот токен что при разрешительном режиме
        :return:
        """
        i_dict = {
            'uuid': self.uuid,
            'data': self.signed_string
        }
        headers = {
            "content-type": "application/json;charset=UTF-8",
        }
        url = config['crpt_prod']['url'] + '/api/v3/true-api/auth/simpleSignIn'
        data = json.dumps(i_dict)
        try:
            r = requests.post(url=url, data=data, headers=headers)
            logging.debug(r.text)
        except Exception as exc:
            logging.debug(exc)
            logging.debug(r.status_code)
            send_telegram(error_text='орг={0}, инн={1}, ошибка получения токена'.format(self.org, self.inn))
        if r.status_code == 200:
            i_token = r.json()['token']
        else:
            i_token = ''
        logging.debug('орг={org}, ПОЛУЧИЛИ ТОКЕН: {token}'.format(org=self.org,
                                                                  token=i_token))
        return i_token

    def get_token_permission_mode(self):
        """
        получение токена разрешительного режима на получение публичной информации по КМ
        :return:
        """
        headers = {
            "Content-Type": "application/json"
        }
        url = config['crpt_prod']['url'] + '/api/v3/true-api/auth/permissive-access'
        data = {
            "data": self.signed_string
        }
        try:
            r = requests.post(url=url, headers=headers, data=json.dumps(data))
        except Exception as exc:
            logging.debug(
                f'org={self.org} инн={self.inn} запрос токена разрешительного режима закончился ошибкой {exc}')
        if r.status_code == 200:
            i_token = r.json()["access_token"]
        else:
            i_token = ''
        logging.debug('орг={org}, ПОЛУЧИЛИ ТОКЕН: {token}'.format(org=self.org,
                                                                  token=i_token))
        return i_token


def make_env(tokens, mode: str = 'w') -> None:
    """
    функция сохранения токена в файл .env
    :param i_token:
    :return:
    """
    with open('token.env', mode) as f_env:
        for key, value in tokens.items():
            # Записываем в список каждую пару "ключ = значение"
            f_env.write(f'{key} = {value}\n')


def send_token_to_site(token: str = ''):
    """
    функция отправки токена на сайт бельетаж
    им тоже нужен
    :param token:
    :return:
    """
    params = []
    params.append(token)
    url = conf_token('url_beletag')
    r = requests.post(url=url, json=params)
    logging.debug('токен отправлен на сайт бельетаж ' + r.text)


def copy_env():
    pass


def send_telegram(error_text: str = 'not error'):
    """
    функция отправки ошибок в телеграм в общий чат
    :param error_text:
    :return:
    """
    f_name = socket.gethostname().upper()
    my_dict = {
        'shop': f_name,
        'text': f'{error_text}'
    }

    my_bot = telebot.TeleBot(conf_token('tg_token', None))
    my_bot.send_message(conf_token('tg_id', None), '<b>{0}</b>'.format(my_dict), parse_mode='html')
    # ниже это id кожина романа, в проде поменять на нужный
    id_roman = conf_token('tg_roman', None)
    my_bot.send_message(id_roman, '<b>{0}</b>'.format(my_dict), parse_mode='html')


def make_token_dict(inn, code_sklad, auth_data) -> Dict:
    """
    функция получения словаря токенов, полный токен и токен разрешительного режима
    :return: dict токены ЧЗ
    """
    if auth_data is None:
        auth_data['uuid'] = uuid.uuid1()
        auth_data['data'] = 'random string'
    i_honest_sign = GetTokenHonestSign(org_inn=inn,
                                       org_sklad=code_sklad,
                                       i_uuid=auth_data['uuid'],
                                       i_data=auth_data['data'])
    tokens = {}
    tokens['description'] = f"file .env make in comp {os.environ['COMPUTERNAME']}"
    tokens['org'] = i_honest_sign.org
    tokens['inn'] = i_honest_sign.inn
    tokens['url_crpt'] = f"{config['crpt_prod']['url']}/api/v3/true-api/auth/permissive-access"
    tokens['url_cdn_info'] = f"{config['crpt_prod']['url_cdn_info']}/api/v3/true-api/auth/permissive-access"
    tokens['token_full'] = i_honest_sign.get_token()
    tokens['token_pm'] = i_honest_sign.get_token_permission_mode()
    return tokens


def main():
    inn_to_code = InnToCode()
    inn_to_code.read_f_make_inn_code_sklad()
    for inn, code_sklad in inn_to_code.dict_inn_code.items():
        auth_data = get_uuid_data()
        logging.debug('ЗАШЛИ В ИНН: ' + inn)
        logging.debug(f'зашли в получение uuid и data')
        logging.debug(f'получили uuid и data {auth_data}')
        token_dict = make_token_dict(inn, code_sklad, auth_data)
        make_env(token_dict, mode='w')
        if inn == INN_BELETAG:
            # отправка токена на сайт бельетажа, им тоже надо чипы проверять
            send_token_to_site(token=token_dict.get('token_full', None))
        write_path = '\\\\shoprsync\\rsync\\script_py\\'
        file_to_copy = 'token.env'
        new_name_file = '.env'
        sub_dir = 'honest_sign'
        logging.debug(f'словарь токенов = {token_dict}')
        if token_dict.get('token_pm', None):
            list_folders = code_sklad
            try:
                copy_env_to_script_py.make_subfolder(root_folder=write_path, top_folders=list_folders,
                                                     sub_folder=sub_dir)  # это если папки назначения нет
            except Exception as exc:
                logging.debug(exc)
                logging.debug('error 102')
                send_telegram(error_text='{0}'.format(exc))
                exit(102)
            try:
                copy_env_to_script_py.copy_file_to_folders(file_to_copy, write_path, list_folders, sub_dir=sub_dir,
                                                           f_new_name=new_name_file)  # копирования файла по всем папка назначения
            except Exception as exc:
                logging.debug(exc)
                logging.debug('error 103')
                send_telegram(error_text='{0}'.format(exc))
                exit(103)


if __name__ == '__main__':
    main()
