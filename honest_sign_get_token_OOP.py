import logging
import requests
import win32com.client
from decouple import config as conf_token
CAPICOM_LOCAL_MACHINE_STORE = 2

class GetTokenHonestSign:

    def __init__(self) -> None:
        """
        конструктор класса, инициализируем сразу и дата и ююид
        и серийник сертификата
        """
        url = 'https://ismp.crpt.ru/api/v3/auth/cert/key'
        r = requests.get(url=url)
        self.uuid = r.json()['uuid']
        self.data = r.json()['data']
        self.serial_sert = conf_token('serial_number', default=None)
        self.token = ''

    def get_token(self):
        """
        меотд подписи строки дата нашим сертификатом
        :return: str наш токен для работы с API честного знака
        """
        cades_bes = 1
        capicom_encode_base64 = 0
        capicom_certificate_include_end_entity_only = 2
        oSigner = win32com.client.Dispatch('CAdESCOM.CPSigner')
        oStore = win32com.client.Dispatch("CAdESCOM.Store")
        oStore.Open(CAPICOM_LOCAL_MACHINE_STORE)
        for elem in oStore.Certificates:
            if elem.SerialNumber == self.serial_sert:
                oSigner.Certificate = elem

        oSigner.Options = capicom_certificate_include_end_entity_only
        oSignedData = win32com.client.Dispatch('CAdESCOM.CadesSignedData')
        oSignedData.Content = self.data
        out_data = oSignedData.SignCades(oSigner, cades_bes, False, capicom_encode_base64)
        out_data2 = out_data.split('\n')
        for elem in out_data2:
            self.token += elem.replace('\r', '')


def main():
    i_honest_sign = GetTokenHonestSign()
    i_honest_sign.get_token()
    print(i_honest_sign.token)



if __name__ == '__main__':
    main()
