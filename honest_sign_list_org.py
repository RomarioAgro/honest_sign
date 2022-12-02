from decouple import config
import re
"""
скрипт перебора файла \\shoprsync\rsync\prg\__\_МассивСкладКодвИНН.prg
будем из этого файла доставать данные к какому ИНН относятся буквенные коды складов
ищем строку вида Выбор "4E":Вернуть("7448213692")
"""


class InnToCode:
    """
    класс в котором будем хранить соответствие ИНН и кодов складов
    """
    def __init__(self):
        self.path = config('path_prg')
        self.pattern_inn = r'"\d+"'
        self.pattern_code = r'"\w\w"'
        self.dict_inn_code = dict

    def read_f_make_inn_code_sklad(self):
        i_dict = {}
        with open(self.path, 'r') as i_file:
            for line in i_file:
                match_inn = re.search(self.pattern_inn, line)
                match_code = re.search(self.pattern_code, line)
                if match_inn and match_code:
                    i_list = i_dict.get(match_inn[0].strip('\"'), [])
                    i_list.append(match_code[0].strip('\"'))
                    i_dict[match_inn[0].strip('\"')] = i_list
        self.dict_inn_code = i_dict


def main():
    inntocode = InnToCode()
    inntocode.read_f_make_inn_code_sklad()


if __name__ == '__main__':
    main()