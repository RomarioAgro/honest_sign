import sys

import requests
from decouple import Config, RepositoryEnv
from typing import List, Tuple, Dict
import json
from sys import argv, exit
import logging
import datetime
import time
import os
import tkinter as tk
from tkinter import messagebox
from shtrih.preparation_km_to_honest_sign import preparation_km as km_with_gs
import importlib


logging.basicConfig(
    filename='d:\\files\\' + os.path.basename(__file__)[:-3] + '_' + datetime.date.today().strftime('%Y-%m-%d') + '.log',
    filemode='a',
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S')

# Создание объекта конфигурации
path_to_env = os.path.dirname(os.path.abspath(__file__))
config_hs = Config(RepositoryEnv(path_to_env + '\\.env'))

# сопоставление юзеров компа и сбис
USER_SBIS = {
    'kassir1': "КАССИР1",
    'kassir2': "КАССИР2",
    'kassir3': "КАССИР3",
    'kassir4': "КАССИР4",
    'kassir5': "КАССИР5"
}


def show_error_message(errors):
    root = tk.Tk()
    root.withdraw()  # Скрываем основное окно
    # Устанавливаем фокус на окно
    root.lift()  # Поднять окно над всеми
    root.focus_force()  # Принудительно установить фокус
    messagebox.showerror("Ошибка", "\n".join(errors))  # Показываем окно с ошибками
    root.destroy()  # Закрываем основное окно после показа сообщения

def save_events_to_file(errors: List, name: str = "errors.txt") -> None:
    """
    сохранение ошибок проверки КМ в ЧЗ
    :param errors: list список строк с ошибками
    :param name: str часть имени файла
    :return: None
    """
    filename = config_hs('path_result_checking', 'd:\\files\\') + os.path.basename(__file__)[:-3] + '_' + name
    with open(filename, "a", encoding="utf-8") as file:
        for error in errors:
            file.write(error + "\n")

class CheckKM:
    """
    конструктор класса проверки КМ в честном знаке
    """

    def __init__(self, i_dict_km: Dict = {}) -> None:
        """
        заходим в клас со словарем кодов маркировки
        токены он сам читает
        :param i_dict_km:
        """
        self.token = config_hs('token_full', default=None)
        self.token_pm = config_hs('token_pm', default=None)
        self.km = preparation_km(i_dict_km['km'])
        self.operation = i_dict_km['operation']
        self.fn = i_dict_km.get('fn', None)
        self.file_name = i_dict_km.get('rec_name', 'status')
        self.inn = i_dict_km.get('inn', None)
        self.url_cdn = self.get_url_cdn()
        self.owner_inn = None
        self.status_km = None
        self.answer = None
        self.status_code = None

    def get_url_cdn(self) -> List:
        """
        метод получения url cdn, читаем из файла
        если файла нет, тогда запускаем скрипт который эти урлы получает с ЧЗ
        :return: List список урлов
        """
        path_cdn = config_hs('path_cdn_list', None) + 'cdn_list.json'
        self.prepare_cdn_file(path_cdn)
        with open(path_cdn, 'r') as f_cdn:
            cdn_data = json.load(f_cdn)
        if cdn_data:
            return cdn_data["cdn_host"]

    def prepare_cdn_file(self, path_cdn):
        """
        метод подготовки файла со списком cdn хостов
        path_cdn: str путь до файла со списком cdn хостов
        :return: None
        """
        just_do_it = False
        # если cdn списка нет или он устарел, тогда создаем новый
        if not os.path.exists(path_cdn):
            just_do_it = True
        else:
            t_diff = time.time() - os.path.getctime(path_cdn)
            if t_diff > 21599:
                just_do_it = True
        if just_do_it:
            path_to_import = os.path.dirname(os.path.abspath(__file__))
            sys.path.append(path_to_import)
            try:
                import pm_get_cdn
            except Exception as exc:
                logging.debug(f'ошибка импорта модуля {exc}')
            pm_get_cdn.main()


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

    def check_km_permission_mode(self):
        """
        проверка КМ в ЧЗ разрешительный режим
        :return:
        """
        headers = {
            'X-API-KEY': self.token_pm,
            "content-type": "application/json",
        }
        param = {
            "codes": self.km
        }
        for base_url in self.url_cdn:
            url = base_url + '/' + 'api/v4/true-api/codes/check'
            try:
                start_time = time.time()
                r = requests.post(url=url, headers=headers, json=param, timeout=(2, 2))
                elapsed_time = time.time() - start_time
                if elapsed_time > 2:
                    logging.debug(
                        f'Запрос к {base_url} занял более 2 секунд ({elapsed_time:.2f} секунд), переходим к следующему URL.')
                    continue
                logging.debug(f'результат запроса статуса КМ={r.text}')
                # Проверка успешного ответа
                if r.status_code == 200:
                    logging.debug(f'Успешный ответ от {base_url}: {r.text}')
                    print(r.text)
                    self.answer = r.json()
                    return True
            # Проверка кода 429 или 5xx
                elif r.status_code == 429:
                    logging.debug(f'Код 429 (Too Many Requests) от {base_url}, переходим к следующему URL.')
                elif 500 <= r.status_code < 600:
                    logging.debug(f'Код {r.status_code} от {base_url}, ошибка сервера, переходим к следующему URL.')
                else:
                    logging.debug(f'Неожиданный код ответа {r.status_code} от {base_url}, ответ: {r.text}')

            except requests.Timeout:
                logging.debug(f'Запрос к {base_url} превысил тайм-аут 1.5 секунд, переходим к следующему URL.')

            except requests.RequestException as e:
                logging.debug(f'Ошибка при запросе к {base_url}: {e}, переходим к следующему URL.')
        logging.debug('Не удалось получить успешный ответ ни от одного из URL.')
        self.answer = None


    def pm_show_errors_honest_sign(self) -> Tuple:
        """
        разбираем ответ честного знака про наши КМ
        вывод ошибки для пользователя,
        сохранение их в текст файл
        :return: tuple код ошибки, id запроса, время запроса
        """
        data = self.answer
        errors = []
        f_name = self.file_name + '_goods_km.txt'
        # Проверка каждого кода и вывод сообщения, если условия выполняются
        logging.debug(f'зашли в показ ошибок')
        if not data:
            self.status_code = 1
            errors.append('Не удалось получить успешный ответ ни от одного из URL\n ни один КМ не проверен')
        else:
            for code_info in data["codes"]:
                if not code_info.get("found", True):
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n не найден в ЧЗ")
                if not code_info.get("utilised", True):
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n в ЧЗ нет информации о нанесении кода")
                if not code_info.get("verified", True):
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n не подтвержден, пересканируйте код")
                if code_info.get("sold", False)\
                        and self.operation == 'sale':
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n продан, выбыл из оборота")
                if not code_info.get("sold", False) \
                        and self.operation == 'return_sale':
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n не продан, не выбывал из оборота")
                if self.operation == 'status':
                    if code_info.get("sold", False):
                        # будем считать что 0 это продан
                        self.status_code = 0
                        errors.append(f"Код {code_info['cis']}:\n продан, выбыл из оборота")
                    else:
                        # будем считать что 2 это возвращен
                        self.status_code = 2
                        errors.append(f"Код {code_info['cis']}:\n не продан, не выбывал из оборота")
                if code_info.get("isBlocked", True):
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n заблокирован по решению {code_info.get('ogvs', 'ХыЗы кого')}")
                if not code_info.get("realizable", True) \
                        and not code_info.get("sold", True):
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n нет информации о вводе кода в оборот")
                if not code_info.get("isOwner", True):
                    self.status_code = 1
                    errors.append(f"Код {code_info['cis']}:\n ваш ИНН и ИНН владельца кода не совпадают")
        if errors:
            # Вывод ошибки на экран для пользователя
            f_name = self.file_name + '_errors_km.txt'
            show_error_message(errors)
        else:
            self.status_code = 0
            errors.append(f"{self.answer['reqId']};{self.answer['reqTimestamp']}")
        save_events_to_file(errors, name=f_name)
        return self.status_code, self.answer['reqId'], self.answer['reqTimestamp']

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


def preparation_km(in_km: List[str]) -> List[str]:
    """
    функция подготовки кода маркировки к отправке в честный знак
    выделяем cis сам код перед символами 91 и 92
    :param in_km: list список строк с кодами маркировки
    :return: list
    pattern нам нужно совпадение после 30 символа
    """
    out_km = []
    for elem in in_km:
        out_km.append(km_with_gs(in_km=elem))
    return out_km

def make_dict_km(f_name: str = '') -> Dict:
    """
    читаем наш json с кодами маркировки на продажу
    :param f_name: путь до файла
    :return: Dict словарь наших КМов
    """
    with open(f_name, 'r') as rm_file:
        i_dict_km = json.load(rm_file)
    return i_dict_km

def main():
    logging.debug('начало ')
    logging.debug(argv)
    my_dict_km = make_dict_km(f_name=argv[1])
    try:
        o_check = CheckKM(i_dict_km=my_dict_km)
    except Exception as exc:
        logging.debug('error ' + str(exc))
        return 401
    logging.debug('создали объект ')
    # o_check.check_km()
    o_check.check_km_permission_mode()
    o_exit = o_check.pm_show_errors_honest_sign()
    logging.debug(f'проверили км {o_exit}')
    print(o_exit)
    return o_exit[0]


if __name__ == '__main__':
    exit(main())

