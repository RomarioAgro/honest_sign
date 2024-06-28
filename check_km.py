import requests
from decouple import config as conf_token
from typing import List
import json
from sys import argv, exit
import logging
import datetime
import os
import re
import http
import getpass

os.chdir('d:\\kassa\\script_py\\honest_sign\\')

httpclient_logger = logging.getLogger("http.client")
def httpclient_logging_patch(level=logging.DEBUG):
    """Enable HTTPConnection debug logging to the logging framework"""
    def httpclient_log(*args):
        httpclient_logger.log(level, " ".join(args))
    # mask the print() built-in in the http.client module to use
    # logging instead
    http.client.print = httpclient_log
    # enable debugging
    http.client.HTTPConnection.debuglevel = 1

logging.basicConfig(
    filename='d:\\files\\' + os.path.basename(__file__)[:-3] + '_' + datetime.date.today().strftime('%Y-%m-%d') + '.log',
    filemode='a',
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S')

USER_SBIS = {
    'kassir1': "КАССИР1",
    'kassir2': "КАССИР2",
    'kassir3': "КАССИР3",
    'kassir4': "КАССИР4",
    'kassir5': "КАССИР5"
}

class CheckKM:
    """
    конструктор класса проверки КМ в честном знаке
    """

    def __init__(self, f_name: str = '') -> None:
        with open(f_name, 'r') as rm_file:
            i_dict_km = json.load(rm_file)
        self.token = conf_token('token', default=None)
        self.km = preparation_km(i_dict_km['km'])
        self.inn = i_dict_km['inn']
        self.operation = i_dict_km['operation']
        self.owner_inn = ''
        self.status_km = ''
        self.answer = None
        self.status_code = None

    def check_km(self) -> None:
        """
        метод проверки КМ в честном знаке
        :return:
        """
        url = 'https://markirovka.crpt.ru/api/v3/true-api/cises/info'
        headers = {
            'Authorization': 'Bearer ' + self.token,
            "content-type": "application/json;charset=UTF-8",
            'accept': '*/*'
        }
        i_data = self.km
        params = {
            "childsWithBrackets": True
        }
        logging.debug('json {0}'.format(i_data))
        try:
            r = requests.post(url=url, headers=headers, params=params, json=self.km, timeout=30)
        except Exception as exc:
            logging.debug('error ' + str(exc))
            exit(504)
        logging.debug('результат проверки в ЧЗ: {0}'.format(r.text))
        self.status_code = r.status_code
        print(r.json())
        if r.status_code == 200 and r.text != '{}':
            with open('status_KI.txt', 'w', encoding='utf-8') as i_file:
                i_file.write(json.dumps(r.json(), ensure_ascii=False, indent=4))
            inf_about_km = r.json()[0]['cisInfo']
            self.owner_inn = inf_about_km.get('ownerInn', None)
            self.status_km = inf_about_km.get('status', None)
            self.answer = r.json()
        else:
            logging.debug('связь есть, но ошибка в запросе, потому что ответ равен: {0}'.format(r.text))
            exit(r.status_code)

    def check_water(self) -> None:
        """
        метод проверки КМ в честном знаке
        :return:
        """
        url = 'https://markirovka.crpt.ru/api/v3/true-api/cises/short/list'
        headers = {
            'Authorization': 'Bearer ' + self.token,
            "content-type": "application/json",
            'accept': '*/*'
        }
        i_data = {
            'cis': self.km[0]
        }
        j_data = json.dumps(self.km)
        logging.debug('json {0}'.format(i_data))
        try:
            r = requests.post(url=url, headers=headers, data=j_data)
        except Exception as exc:
            logging.debug('error ' + str(exc))
            exit(504)
        logging.debug('результат проверки в ЧЗ: {0}'.format(r.text))
        self.status_code = r.status_code
        print(r.json())
        if r.status_code == 200 and r.text != '{}':
            with open('status_KI.txt', 'w', encoding='utf-8') as i_file:
                i_file.write(json.dumps(r.json(), ensure_ascii=False, indent=4))
            inf_about_km = r.json()[0]['result']
            self.owner_inn = inf_about_km.get('ownerInn', None)
            self.status_km = inf_about_km.get('status', None)
            self.answer = r.json()
        else:
            logging.debug('связь есть, но ошибка в запросе, потому что ответ равен: {0}'.format(r.text))
            exit(400)

    def verdict(self) -> int:
        """
        метод возврата результата проверки,
        возвращаем цифровые коды, сбис потом будет их
        идентифицировать
        :return:
        """
        # если по какой-либо причине проверка не удалась
        if self.status_code != 200:
            return self.status_code
        if self.operation == 'status':
            # запрос status переделан под 1 код
            # и надо сохранить все в файл
            self.save_answer()
            return 99  #результат сохранен в файл и кассовое ПО должно этот файл прочитать и сообщить ответ
        if self.inn == self.owner_inn:
            # это если запрос индивидуальынй по одному коду
            if self.operation == 'sale' and self.status_km == 'INTRODUCED':  #  "продажа" и статус "в обороте"
                return 0  # ошибок нет
            if self.operation == 'return_sale' and self.status_km == 'RETIRED':  #  "возврат" и статус "выбыл"
                return 0  # ошибок нет
            if self.operation == 'sale' and self.status_km != 'INTRODUCED':  #  "продажа" и статус не совпадает с "в обороте"
                logging.debug('операция из сбис: {0}, статус в ЧЗ ЧЗ: {1}'.format(self.operation, self.status_km))
                return 101  # ошибка надо прерывать операцию
            if self.operation == 'return_sale' and self.status_km != 'RETIRED':  #  "возврат" и статус не равен "выбыл"
                logging.debug('операция из сбис: {0}, статус в ЧЗ ЧЗ: {1}'.format(self.operation, self.status_km))
                return 102  #  ошибка надо прерывать операцию
            return 103  #  неизвестная ошибка
        else:
            logging.debug('инн из сбис: {0}, инн из ЧЗ: {1}'.format(self.inn, self.owner_inn))
            return 100  #  если у нас даже ИНН продавца и владельца не совпадают, то ваще кранты

    def save_answer(self) -> None:
        """
        метод сохранения результата запроса в текстовый файл
        :return:
        """
        list_str = []

        f_name = 'status_KI_' + USER_SBIS.get(getpass.getuser(), "кассир1") + '.txt'
        with open('r:\\' + f_name, 'w') as o_file:
            for km in self.answer:
                list_str.append(km['cisInfo']['status'])
                list_str.append(km['cisInfo']['ownerInn'])
                list_str.append(km['cisInfo']['ownerName'])
                list_str.append('\n')
                o_str = ';'.join(list_str)
                o_file.write(o_str)
                list_str.clear()

def preparation_km(in_km: List[str]) -> List[str]:
    """
    функция подготовки кода маркировки к отправке в честный знак
    выделяем cis сам код перед символами 91 и 92
    :param in_km: list список строк с кодами маркировки
    :return: list
    pattern нам нужно совпадение после 30 символа
    """
    pattern = r'91\S+92'
    out_km = []
    for elem in in_km:
        list_break_pattern = re.split(pattern, elem[30:])
        out_km.append(elem[:30] + list_break_pattern[0])
    return out_km

def main():
    logging.debug('начало ')
    logging.debug(argv)
    try:
        o_check = CheckKM(f_name=argv[1])
    except Exception as exc:
        logging.debug('error ' + str(exc))
        return 401
    logging.debug('создали объект ')
    try:
        o_check.check_km()
        # o_check.check_water()
    except Exception as exc:
        logging.debug('error ' + str(exc))
    logging.debug('проверили км ')
    o_exit = o_check.verdict()
    return o_exit


if __name__ == '__main__':
    exit(main())

