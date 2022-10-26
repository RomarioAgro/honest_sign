import win32com.client

CAPICOM_LOCAL_MACHINE_STORE = 2
cades_bes = 1
capicom_encode_base64 = 0
capicom_certificate_include_end_entity_only = 2
oSigner = win32com.client.Dispatch('CAdESCOM.CPSigner')
i_data = 'UUQYHXDZDZIVYTDEMSGMGYRNMJSTWU'
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
print(out_data)

