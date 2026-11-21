import json
import os
from datetime import datetime, timedelta
import redis

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

istemci = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

OTURUM_SURESI = 60 * 30


def gun_sonuna_kalan_saniye():
    simdi = datetime.now()
    yarin = (simdi + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((yarin - simdi).total_seconds()), 60)


def oturum_kaydet(token, oturum_bilgisi):
    istemci.setex(f"oturum:{token}", OTURUM_SURESI, json.dumps(oturum_bilgisi))


def oturum_getir(token):
    if not token:
        return None
    anahtar = f"oturum:{token}"
    deger = istemci.get(anahtar)
    if not deger:
        return None
    istemci.expire(anahtar, OTURUM_SURESI)
    return json.loads(deger)


def oturum_sil(token):
    if token:
        istemci.delete(f"oturum:{token}")


def menu_onbellek_getir(anahtar):
    veri = istemci.get(f"menu:{anahtar}")
    return json.loads(veri) if veri else None


def menu_onbellek_kaydet(anahtar, veri):
    istemci.setex(f"menu:{anahtar}", gun_sonuna_kalan_saniye(), json.dumps(veri))


def menu_onbellek_temizle():
    for anahtar in istemci.scan_iter("menu:*"):
        istemci.delete(anahtar)