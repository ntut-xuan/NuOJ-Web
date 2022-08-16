import base64
from Crypto.Hash import SHA1
from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

def GenerateKey():
    key = RSA.generate(2048)

    privateKey = key.export_key()
    with open("/etc/nuoj/private.pem", "wb") as f:
        f.write(privateKey)

    publicKey = key.public_key().export_key()
    with open("/etc/nuoj/public.pem", "wb") as f:
        f.write(publicKey)

def GetPrivkey():
    key = open("/etc/nuoj/private.pem", "rb").read()
    key = RSA.import_key(key)
    return key

def GetPubkey():
    key = open("/etc/nuoj/public.pem", "rb").read()
    key = RSA.import_key(key)
    return key

def Decrypt(cipher):
    PrivateKey = GetPrivkey()
    cipher = base64.b64decode(cipher)
    Decryptor = PKCS1_OAEP.new(PrivateKey, SHA256, lambda x,y: pss.MGF1(x,y, SHA1))
    data = Decryptor.decrypt(cipher).decode('utf-8')
    return data

def Encrypt(plain):
    PublicKey = GetPubkey()
    Encryptor = PKCS1_OAEP.new(PublicKey, SHA256, lambda x,y: pss.MGF1(x,y, SHA1))
    encrypted = Encryptor.encrypt(plain)
    return encrypted