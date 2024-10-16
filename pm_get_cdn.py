"""
получаем cdn площадку для проверки КМ в разрешительном режиме
"""
import configparser
import logging
import datetime
import os
import requests
from decouple import Config, RepositoryEnv
import time
from typing import List


current_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H_%M_%S')
script_name = os.path.splitext(os.path.basename(__file__))[0]
logging.basicConfig(
    filename=f"d:\\files\\{script_name}_{current_time}.log",
    filemode='a',
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s - %(funcName)s: %(lineno)d - %(message)s",
    datefmt='%H:%M:%S')

logger_cdn: logging.Logger = logging.getLogger(__name__)
logger_cdn.setLevel(logging.DEBUG)


# Создание объекта конфигурации
config = configparser.ConfigParser()
path_to_ini = os.path.dirname(os.path.abspath(__file__))
config.read(path_to_ini + '//config.ini')
# читаем наш токен
path_to_env = os.path.dirname(os.path.abspath(__file__))
config_hs = Config(RepositoryEnv(path_to_env + '//.env'))


def get_cdn(token: str = '') -> List|None:
    """
    получаем список CDN серверов ЧЗ
    :param token:
    :return:
    """
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": token
    }
    url = config['crpt_prod']['url_cdn_info'] + '/api/v4/true-api/cdn/info'
    try:
        response = requests.get(url, headers=headers)
        logger_cdn.debug(f'получили список cdn {response.text}')
        if response.status_code == 200:
            cdn_data = response.json()
            if cdn_data['code'] == 0:
                return cdn_data['hosts']
        return None
    except Exception as e:
        logger_cdn.debug(f"Ошибка получения CDN-площадок: {e}")
        return None


def check_cdn_health(cdn_url, token) -> float:
    """
    Функция для измерения времени отклика CDN
    :param cdn_url: адрес площадки
    :param token: str авторизационный токен платформы
    :return: float время ответа
    """
    health_check_url = f"{cdn_url}/api/v4/true-api/cdn/health/check"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": token
    }
    logger_cdn.debug(f'зашли в замер времени cdn площадки {cdn_url}')
    try:
        start_time = time.time()
        response = requests.get(health_check_url, headers=headers)
        end_time = time.time()
        if response.status_code == 200:
            latency = (end_time - start_time) * 1000  # Время в мс
            logger_cdn.debug(f'померели время {latency}')
            return latency
        return float('inf')  # Если ошибка, ставим максимальное значение
    except Exception as e:
        print(f"Ошибка проверки здоровья CDN {cdn_url}: {e}")
        return float('inf')


def prioritize_cdns(cdn_hosts: List, token: str) -> List:
    """
    сортировка cdn площадок по времени ответа
    :param cdn_hosts: список площадок
    :param token: токен авторизации на платформе
    :return: List отсортированный список урлов
    """
    logger_cdn.debug(f'зашли в сортировку cdn площадок')
    cdn_latencies = []
    for cdn in cdn_hosts:
        cdn_url = cdn['host']
        latency = check_cdn_health(cdn_url, token)
        cdn_latencies.append((cdn_url, latency))
    # Сортировка по задержке
    sorted_cdns = sorted(cdn_latencies, key=lambda x: x[1])
    logger_cdn.debug(f'осортировали cdn площадки')
    return sorted_cdns


def main():
    token = config_hs('token_pm', default=None)
    cdn_hosts = get_cdn(token=token)
    if cdn_hosts:
        prioritized_cdns = prioritize_cdns(cdn_hosts, token)
        return prioritized_cdns[0][0]
    else:
        return None

if __name__ == '__main__':
    main()