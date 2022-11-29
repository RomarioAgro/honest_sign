from sys import exit
import logging
import requests
import os
import datetime
import win32com.client
import json
from typing import Any
from decouple import config as conf_token
import copy_env_to_script_py

CAPICOM_LOCAL_MACHINE_STORE = 2

logging.basicConfig(
    filename=os.environ.get('Temp') + '\\' + os.path.basename(__file__)[:-3] + '_' + datetime.date.today().strftime('%Y-%m-%d') + '.log',
    filemode='a',
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S')


class GetTokenHonestSign:

    def __init__(self) -> None:
        """
        конструктор класса, инициализируем сразу и дата и ююид
        и серийник сертификата
        """
        try:
            url = 'https://ismp.crpt.ru/api/v3/auth/cert/key'
            r = requests.get(url=url)
        except Exception as exc:
            logging.debug(exc)
            exit(99)
        self.uuid = r.json()['uuid']
        self.data = r.json()['data']
        self.serial_sert = conf_token('serial_number', default=None)
        self.signed_string = self.get_signed_string()
        self.token = self.get_token()

    def getSignerCertificate(self) -> Any:
        """
        получаем сертификат по его серийнику
        из хранилища сертификатов
        :return:
        """
        oStore = win32com.client.Dispatch("CAdESCOM.Store")
        oStore.Open(CAPICOM_LOCAL_MACHINE_STORE)
        for elem in oStore.Certificates:
            if elem.SerialNumber == self.serial_sert:
                return elem

    def get_signed_string(self) -> str:
        """
        меотд подписи строки дата нашим сертификатом
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
            logging.debug('error 100')
            exit(100)
        try:
            oSigner.Certificate = self.getSignerCertificate()
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 101')
            exit(101)
        try:
            oSignedData = win32com.client.Dispatch('CAdESCOM.CadesSignedData')
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 102')
            exit(102)
        logging.debug(oSigner)
        logging.debug(oSignedData)
        oSigner.Options = capicom_certificate_include_end_entity_only
        oSignedData.Content = self.data
        try:
            out_data = oSignedData.SignCades(oSigner, cades_bes, False, capicom_encode_base64)
        except Exception as exc:
            logging.debug(exc)
            logging.debug('error 103')
            exit(103)
        out_data3 = out_data.replace('\r\n', '')
        return out_data3

    def get_token(self):
        i_dict = {
            'uuid': self.uuid,
            'data': self.signed_string
        }
        headers = {
            "content-type": "application/json;charset=UTF-8",
        }
        url = 'https://ismp.crpt.ru/api/v3/auth/cert/'
        data = json.dumps(i_dict)
        r = requests.post(url=url, data=data, headers=headers)
        return r.json()['token']



def make_env(i_token: str = '') -> None:
    """
    функция сохранения токена в файл .env
    :param i_token:
    :return:
    """
    o_token = 'token = ' + i_token + '\n'
    o_string = '#file .env make in comp {0}'.format(os.environ['COMPUTERNAME'])
    with open('token.env', 'w') as f_env:
        f_env.write(o_token)
        # f_env.write('\n')
        f_env.write(o_string)


def copy_env():
    pass


def main():
    i_honest_sign = GetTokenHonestSign()
    print('пошли дальше')
    print(i_honest_sign.token)
    make_env(i_token=i_honest_sign.token)
    write_path = '\\\\shoprsync\\rsync\\script_py\\'
    file_to_copy = 'token.env'
    new_name_file = '.env'
    sub_dir = 'honest_sign'
    list_folders = os.listdir(write_path)
    try:
        copy_env_to_script_py.make_subfolder(root_folder=write_path, top_folders=list_folders,
                                             sub_folder=sub_dir)  # это если папки назначения нет
    except Exception as exc:
        logging.debug(exc)
        logging.debug('error 102')
        exit(102)
    try:
        copy_env_to_script_py.copy_file_to_folders(file_to_copy, write_path, list_folders, sub_dir=sub_dir,
                                                   f_new_name=new_name_file)  # копирования файла по всем папка назначения
    except Exception as exc:
        logging.debug(exc)
        logging.debug('error 103')
        exit(103)



if __name__ == '__main__':
    main()
