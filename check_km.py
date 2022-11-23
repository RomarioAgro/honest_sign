import requests
from decouple import config as conf_token
import json
from sys import argv, exit


class CheckKM:
    def __init__(self, ):
        self.token = conf_token('token', default=None)
        i_dict_km = self.read_json_file()
        self.km = i_dict_km['km']
        self.inn = i_dict_km['inn']
        self.operation = i_dict_km['operation']
        self.owner_inn = ''
        self.status_km = ''
        self.answer = None

    def read_json_file(self):
        with open(argv[1], 'r') as rm_file:
            o_dict = json.load(rm_file)

        return o_dict

    def check_km(self):
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
        # print(r.json())

        with open('status_KI.txt', 'w') as i_file:
            i_file.write(json.dumps(r.json(), ensure_ascii=False, indent=4))
        inf_about_km = r.json().get(self.km[0], None)
        self.owner_inn = inf_about_km.get('ownerInn', None)
        self.status_km = inf_about_km.get('status', None)
        self.answer = r.json()

    def verdict(self):
        if self.operation == 'status':
            # тут надо вывести окно с организацией, наим и статус
            pass
            return 0
        if self.km == self.owner_inn:
            if self.operation == 'sale' and self.status_km == 'INTRODUCED':
                return 0
            if self.operation == 'return_sale' and self.status_km == 'RETIRED':
                return 0
            if self.operation == 'sale' and self.status_km != 'INTRODUCED':
                return 101
            if self.operation == 'return_sale' and self.status_km != 'RETIRED':
                return 102
        else:
            return 100


def main():
    o_check = CheckKM()
    o_check.check_km()

    pass


if __name__ == '__main__':
    main()

