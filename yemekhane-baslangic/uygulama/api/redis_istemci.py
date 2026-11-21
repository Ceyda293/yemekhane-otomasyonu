import json
import os
import redis

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

istemci = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

OTURUM_SURESI = 60 * 60 * 24
MENU_ONBELLEK_SURESI = 60 * 5

def oturum_kaydet(token, kullanici_id):
    istemci.setex(f"oturum:{token}", OTURUM_SURESI, str(kullanici_id))

def oturum_getir(token):
    deger = istemci.get(f"oturum:{token}")
    return int(deger) if deger else None

def oturum_sil(token):
    istemci.delete(f"oturum:{token}")

def menu_onbellek_getir(anahtar):
    veri = istemci.get(f"menu:{anahtar}")
    return json.loads(veri) if veri else None

def menu_onbellek_kaydet(anahtar, veri):
    istemci.setex(f"menu:{anahtar}", MENU_ONBELLEK_SURESI, json.dumps(veri))

def menu_onbellek_temizle():
    for anahtar in istemci.scan_iter("menu:*"):
        istemci.delete(anahtar)