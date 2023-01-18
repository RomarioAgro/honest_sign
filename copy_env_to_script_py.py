import logging
import os
import re
import shutil
"""
скрипт раскопирования скриптов py по папкам магазинов
"""

def slice_elem(elem):
    """
    очищаем элементы от лишнего первого символа
    :param elem:
    :return:
    """
    return elem[1:]


def read_file(i_path):
    """
    функция поиска папок магазинов в котрых win10
    :param i_path: str путь до фала который расссматриваем
    и в котором ищем список папок с магазинами win10
    :return: list список папок
    """
    pattern = r';\w\w'
    list_folders = []
    with open(i_path, 'r', encoding='cp866') as i_file:
        for line in i_file:
            intermediate_list = re.findall(pattern, line)
            if len(intermediate_list) > 0:
                print(line, end='')
                list_folders = list(map(slice_elem, intermediate_list))
    return list_folders

def copy_file_to_folders(i_file: str = '', i_path: str = '', subfolder_list: list = [], sub_dir:str = 'TT', f_new_name: str = 'test.txt') -> None:
    """
    функция копирования файла по суб папкам
    :param i_file: str имя файла
    :param i_path: str имя папки
    :param subfolder_list: list списокпапок по которым будем копировать
    :param sub_dir наша папка внутри списка папок в которую надо скопировать
    :return: None
    """
    for fold in subfolder_list:
        if fold != '__':
            full_path = i_path + '\\' + fold + '\\' + sub_dir + '\\'
            if os.path.exists(full_path):
                new_file = os.path.basename(i_file)
                shutil.copy(i_file, full_path+os.path.basename(f_new_name))
                print(full_path)
                logging.debug(full_path)

def make_subfolder(root_folder:str = 'R:\\', top_folders:list = [], sub_folder:str = '__', ):
    """
    функция создания подпкапки а нашем списке папок
    :param root_folder: str корневая попка
    :param top_folders: list список подпапок корневой папки внутри которых надо создать папку
    :param sub_folder: str наша папка которую создаем
    :return: None
    """
    for fold in top_folders:
        if fold != '__':
            full_path = root_folder + '\\' + fold + '\\' + sub_folder + '\\'
            if os.path.exists(full_path) is False:
                os.makedirs(full_path)
                print(full_path)

def main():
    write_path = '\\\\shoprsync\\rsync\\script_py\\'
    file_to_copy = 'token.env'
    new_name_file = '.env'
    sub_dir = 'honest_sign'
    list_folders = os.listdir(write_path)
    make_subfolder(root_folder=write_path, top_folders=list_folders, sub_folder=sub_dir)  #это если папки назначения нет
    copy_file_to_folders(file_to_copy, write_path, list_folders, sub_dir=sub_dir, f_new_name=new_name_file)  #копирования файла по всем папка назначения
if __name__ == '__main__':
    main()
