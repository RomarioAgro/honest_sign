import requests
import win32com.client
import json
# запрос к ГИС Честного знака чтоб получить токен для дальнейшей работы с api честного знака
# надо убирать \n \r из подписанной строки
# суть такая получаем строку двоичных данных, потом ее подписываем локально через объекты COM
# получаем подписанный data и с этим подписанным data и uuid обращаемся за токеном к апи гис мт, а потом уже с токеном получаем доступ к api

url = 'https://ismp.crpt.ru/api/v3/auth/cert/key'
r = requests.get(url=url)
# print(r.json())

# здесь у нас идет подпись строки данных через COM объект
CAPICOM_LOCAL_MACHINE_STORE = 2
cades_bes = 1
capicom_encode_base64 = 0
capicom_certificate_include_end_entity_only = 2
oSigner = win32com.client.Dispatch('CAdESCOM.CPSigner')
i_data = r.json()['data']
sSerialNumber = '0352999F00DAADE08B468E1BA579D22560'
def getSignerCertificate(sSerialNumber: str = ''):
    oStore = win32com.client.Dispatch("CAdESCOM.Store")
    oStore.Open(CAPICOM_LOCAL_MACHINE_STORE)
    for elem in oStore.Certificates:
        if elem.SerialNumber == sSerialNumber:
            return elem

oSigner.Certificate = getSignerCertificate(sSerialNumber=sSerialNumber)
oSigner.Options = capicom_certificate_include_end_entity_only
oSignedData = win32com.client.Dispatch('CAdESCOM.CadesSignedData')

oSignedData.Content = i_data
out_data = oSignedData.SignCades(oSigner, cades_bes, False, capicom_encode_base64)
out_data2 = out_data.split('\n')
out_data3 = ''
for elem in out_data2:
    out_data3 += elem.replace('\r', '')
# здесь у нас идет подпись строки данных через COM объект