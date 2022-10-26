import requests
import win32com.client
import json
# черновой рабочий вариант
# надо убирать \n \r из подписанной строки
# суть такая получаем строку двоичных данных, потом ее подписываем на сайте по ссылке
# подпись строки УКЭП, либо локально через объекты COM
# https://www.cryptopro.ru/sites/default/files/products/cades/demopage/cades_bes_sample.html
# получаем подписанный data и с этим подписанным data и uuid обращаемся за токеном к апи гис мт, а потом уже с токеном получаем доступ к апи


# в батнике,вместо *** user_id "отпечаток" у сертификата в криптопро
# chcp 1251
# c:
# cd C:\Program Files\Crypto Pro\CSP
# call csptest -sfsign -sign -in %~dp0code.txt -out %~dp0out.txt -my *** -detached -base64 -add


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
# запрос к ГИС ЧЗ за статусом КИ
i_dict = {
    'uuid': r.json()['uuid'],
    'data': out_data3
}
headers = {
       "content-type": "application/json;charset=UTF-8",
}
url = 'https://ismp.crpt.ru/api/v3/auth/cert/'
data = json.dumps(i_dict)

rr = requests.post(url=url, data=data, headers=headers)
token = rr.json()['token']
url = 'https://ismp.crpt.ru/api/v4/facade/cis/cis_list'
headers = {
    'Authorization': 'Bearer ' + token,
    "content-type": "application/json;charset=UTF-8",
    'accept': '*/*'
}
i_data = {
    'cises': ['010290000070625521,X=v-?>h7EaT)'],
    'childrenPaging': False
}

rrr = requests.post(url=url, headers=headers, json=i_data)
print(rrr.json())
with open('status_KI.txt', 'w') as i_file:
    i_file.write(json.dumps(rrr.json(), ensure_ascii=False, indent=4))