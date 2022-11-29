import requests
from decouple import config as conf_token
import json
from sys import argv, exit
import logging
import datetime
import os
os.chdir('d:\\kassa\\script_py\\honest_sign\\')

logging.basicConfig(
    filename='d:\\files\\' + os.path.basename(__file__)[:-3] + '_' + datetime.date.today().strftime('%Y-%m-%d') + '.log',
    filemode='a',
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S')


class CheckKM:
    """
    конструктор класса проверки КМ в честном знаке
    """

    def __init__(self) -> None:
        with open(argv[1], 'r') as rm_file:
            i_dict_km = json.load(rm_file)
        self.token = conf_token('token', default=None)
        self.km = i_dict_km['km']
        self.inn = i_dict_km['inn']
        self.operation = i_dict_km['operation']
        self.owner_inn = ''
        self.status_km = ''
        self.answer = None
        logging.debug(i_dict_km)

    def check_km(self) -> None:
        """
        метод проверки КМ в честном знаке
        :return:
        """
        url = 'https://ismp.crpt.ru/api/v4/facade/cis/cis_list'
        headers = {
            'Authorization': 'Bearer ' + self.token,
            "content-type": "application/json;charset=UTF-8",
            'accept': '*/*'
        }
        i_data = {
            'cises': self.km,
            'childrenPaging': False
        }
        r = requests.post(url=url, headers=headers, json=i_data)
        logging.debug(json.dumps(r.json()))
        with open('status_KI.txt', 'w') as i_file:
            i_file.write(json.dumps(r.json(), ensure_ascii=False, indent=4))
        inf_about_km = r.json().get(self.km[0], None)
        self.owner_inn = inf_about_km.get('ownerInn', None)
        self.status_km = inf_about_km.get('status', None)
        self.answer = r.json()

    def verdict(self) -> int:
        """
        метод возврата результата проверки,
        возвращаем цифровые коды, сбис потом будет их
        идентифицировать
        :return:
        """
        if self.operation == 'status':
            # запрос status может быть у 1000 кодов
            # и надо сохранить все в файл
            self.save_answer()
            return 0
        if self.inn == self.owner_inn:
            # это если запрос индивидуальынй по одному коду
            if self.operation == 'sale' and self.status_km == 'INTRODUCED':  #  "продажа" и статус "в обороте"
                return 0  # ошибок нет
            if self.operation == 'return_sale' and self.status_km == 'RETIRED':  #  "возврат" и статус "выбыл"
                return 0  # ошибок нет
            if self.operation == 'sale' and self.status_km != 'INTRODUCED':  #  "продажа" и статус не совпадает с "в обороте"
                return 101  # ошибка надо прерывать операцию
            if self.operation == 'return_sale' and self.status_km != 'RETIRED':  #  "возврат" и статус не равен "выбыл"
                return 102  #  ошибка надо прерывать операцию
            return 103  #  неизвестная ошибка
        else:
            return 100  #  если у нас даже ИНН продавца и владельца не совпадают, то ваще кранты

    def save_answer(self) -> None:
        """
        метод сохранения результата запроса в текстовый файл
        :return:
        """
        list_str = []
        with open('r:\\status_KI_all.txt', 'a') as o_file:
            for km in self.answer:
                list_str.append(km)
                list_str.append(self.answer[km]['status'])
                list_str.append(self.answer[km]['ownerInn'])
                list_str.append(self.answer[km]['ownerName'])
                list_str.append('\n')
                o_str = ';'.join(list_str)
                o_file.write(o_str)
                list_str.clear()


def main():
    o_check = CheckKM()
    o_check.check_km()
    return o_check.verdict()


if __name__ == '__main__':
    exit(main())

