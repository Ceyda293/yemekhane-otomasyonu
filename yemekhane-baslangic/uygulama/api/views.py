import json
import uuid
import bcrypt
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from . import veri_katmani, redis_istemci


@csrf_exempt
def giris_yap(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)

    try:
        veri = json.loads(request.body)
        eposta = veri.get('eposta', '').strip()
        sifre = veri.get('sifre', '')
    except json.JSONDecodeError:
        return JsonResponse({'hata': 'Geçersiz JSON formatı.'}, status=400)

    kullanici = veri_katmani.kullanici_getir_eposta(eposta)
    if not kullanici:
        return JsonResponse({'hata': 'E-posta veya şifre hatalı.'}, status=401)

    sifre_dogru_mu = bcrypt.checkpw(
        sifre.encode('utf-8'),
        kullanici['sifre_hash'].encode('utf-8')
    )
    if not sifre_dogru_mu:
        return JsonResponse({'hata': 'E-posta veya şifre hatalı.'}, status=401)

    token = str(uuid.uuid4())
    oturum_bilgisi = {
        'id': kullanici['id'],
        'ad_soyad': f"{kullanici['ad']} {kullanici['soyad']}",
        'eposta': kullanici['eposta'],
        'rol': kullanici['rol'],
        'bakiye': float(kullanici['bakiye']),
    }
    redis_istemci.oturum_kaydet(token, oturum_bilgisi)

    return JsonResponse({
        'mesaj': 'Giriş başarılı.',
        'token': token,
        'kullanici': oturum_bilgisi
    })


@csrf_exempt
def cikis_yap(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)

    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    redis_istemci.oturum_sil(token)
    return JsonResponse({'mesaj': 'Çıkış yapıldı.'})


def menuler_listele(request):
    if request.method != 'GET':
        return JsonResponse({'hata': 'Sadece GET isteği kabul edilir.'}, status=405)

    tarih = request.GET.get('tarih')
    baslangic = request.GET.get('baslangic')
    bitis = request.GET.get('bitis')
    yemekhane_id = request.GET.get('yemekhane_id')
    ogun_id = request.GET.get('ogun_id')

    anahtar = f"{tarih or ''}:{baslangic or ''}:{bitis or ''}:{yemekhane_id or ''}:{ogun_id or ''}"
    onbellek = redis_istemci.menu_onbellek_getir(anahtar)
    if onbellek is not None:
        return JsonResponse({'menuler': onbellek, 'kaynak': 'redis'})

    satirlar = veri_katmani.menuleri_getir(
        tarih=tarih,
        baslangic=baslangic,
        bitis=bitis,
        yemekhane_id=yemekhane_id,
        ogun_id=ogun_id
    )

    menuler = {}
    for s in satirlar:
        m_id = s['menu_id']
        if m_id not in menuler:
            menuler[m_id] = {
                'menu_id': m_id,
                'tarih': str(s['tarih']),
                'yemekhane_id': s['yemekhane_id'],
                'yemekhane': s['yemekhane'],
                'ogun_id': s['ogun_id'],
                'ogun': s['ogun'],
                'rezervasyon_son': str(s['rezervasyon_son']) if s['rezervasyon_son'] is not None else None,
                'ogrenci_fiyati': float(s['ogrenci_fiyati']),
                'personel_fiyati': float(s['personel_fiyati']),
                'kapasite': s['kapasite'],
                'rezerve': s['rezerve'],
                'bos_yer': s['bos_yer'],
                'doluluk_yuzde': float(s['doluluk_yuzde']) if s['doluluk_yuzde'] is not None else 0.0,
                'oy_sayisi': s['oy_sayisi'] or 0,
                'ortalama_puan': float(s['ortalama_puan']) if s['ortalama_puan'] is not None else None,
                'toplam_kalori': 0,
                'yemekler': []
            }

        if s['yemek_id']:
            kalori = s['kalori'] or 0
            menuler[m_id]['toplam_kalori'] += kalori
            menuler[m_id]['yemekler'].append({
                'yemek_id': s['yemek_id'],
                'yemek': s['yemek'],
                'kategori': s['kategori'],
                'kalori': kalori,
                'vejetaryen': bool(s['vejetaryen']),
                'alerjenler': s['alerjenler']
            })

    menu_listesi = list(menuler.values())
    redis_istemci.menu_onbellek_kaydet(anahtar, menu_listesi)
    return JsonResponse({'menuler': menu_listesi, 'kaynak': 'mysql'})


def _oturum_kullanici(request):
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    return redis_istemci.oturum_getir(token), token


@csrf_exempt
def rezervasyon_yap(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)

    kullanici, token = _oturum_kullanici(request)
    if not kullanici:
        return JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)

    try:
        veri = json.loads(request.body)
        menu_id = int(veri.get('menu_id'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'hata': 'Geçerli bir menu_id göndermelisiniz.'}, status=400)

    try:
        sonuc = veri_katmani.rezervasyon_yap(kullanici['id'], menu_id)
        kullanici['bakiye'] = float(sonuc['bakiye'])
        redis_istemci.oturum_kaydet(token, kullanici)
        redis_istemci.menu_onbellek_temizle()
        return JsonResponse({
            'mesaj': 'Rezervasyon oluşturuldu.',
            'rezervasyon_id': sonuc['rezervasyon_id'],
            'ucret': float(sonuc['ucret']),
            'bakiye': float(sonuc['bakiye']),
        })
    except veri_katmani.IsKuraliHatasi as e:
        return JsonResponse({'hata': str(e)}, status=400)


@csrf_exempt
def rezervasyon_iptal(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)

    kullanici, token = _oturum_kullanici(request)
    if not kullanici:
        return JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)

    try:
        veri = json.loads(request.body)
        rezervasyon_id = int(veri.get('rezervasyon_id'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'hata': 'Geçerli bir rezervasyon_id göndermelisiniz.'}, status=400)

    try:
        sonuc = veri_katmani.rezervasyon_iptal(kullanici['id'], rezervasyon_id)
        kullanici['bakiye'] = float(sonuc['bakiye'])
        redis_istemci.oturum_kaydet(token, kullanici)
        redis_istemci.menu_onbellek_temizle()
        return JsonResponse({
            'mesaj': 'Rezervasyon iptal edildi.',
            'rezervasyon_id': sonuc['rezervasyon_id'],
            'iade': float(sonuc['iade']),
            'bakiye': float(sonuc['bakiye']),
        })
    except veri_katmani.IsKuraliHatasi as e:
        return JsonResponse({'hata': str(e)}, status=400)


@csrf_exempt
def bakiye_yukle(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)

    kullanici, token = _oturum_kullanici(request)
    if not kullanici:
        return JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)

    try:
        veri = json.loads(request.body)
        tutar = float(veri.get('tutar'))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'hata': 'Geçerli bir tutar göndermelisiniz.'}, status=400)

    try:
        sonuc = veri_katmani.bakiye_yukle(kullanici['id'], tutar)
        kullanici['bakiye'] = float(sonuc['bakiye'])
        redis_istemci.oturum_kaydet(token, kullanici)
        return JsonResponse({
            'mesaj': 'Bakiye yüklendi.',
            'hareket_id': sonuc['hareket_id'],
            'bakiye': float(sonuc['bakiye']),
        })
    except veri_katmani.IsKuraliHatasi as e:
        return JsonResponse({'hata': str(e)}, status=400)


def rezervasyonlarim(request):
    if request.method != 'GET':
        return JsonResponse({'hata': 'Sadece GET isteği kabul edilir.'}, status=405)

    kullanici, _ = _oturum_kullanici(request)
    if not kullanici:
        return JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)

    satirlar = veri_katmani.kullanici_rezervasyonlari_getir(kullanici['id'])
    for s in satirlar:
        s['ucret'] = float(s['ucret'])
    return JsonResponse({'rezervasyonlar': satirlar})


def bakiye_hareketleri(request):
    if request.method != 'GET':
        return JsonResponse({'hata': 'Sadece GET isteği kabul edilir.'}, status=405)

    kullanici, _ = _oturum_kullanici(request)
    if not kullanici:
        return JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)

    satirlar = veri_katmani.kullanici_bakiye_hareketleri_getir(kullanici['id'])
    for s in satirlar:
        s['tutar'] = float(s['tutar'])
    return JsonResponse({'hareketler': satirlar})


@csrf_exempt
def degerlendirme_yap(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)

    kullanici, _ = _oturum_kullanici(request)
    if not kullanici:
        return JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)

    try:
        veri = json.loads(request.body)
        menu_id = int(veri.get('menu_id'))
        puan = int(veri.get('puan'))
        yorum = (veri.get('yorum') or '').strip()[:500] or None
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'hata': 'Geçerli bir menu_id ve puan (1-5) göndermelisiniz.'}, status=400)

    if puan < 1 or puan > 5:
        return JsonResponse({'hata': 'Puan 1 ile 5 arasında olmalıdır.'}, status=400)

    try:
        veri_katmani.degerlendirme_kaydet(kullanici['id'], menu_id, puan, yorum)
        redis_istemci.menu_onbellek_temizle()
        return JsonResponse({'mesaj': 'Değerlendirmeniz kaydedildi.'})
    except veri_katmani.IsKuraliHatasi as e:
        return JsonResponse({'hata': str(e)}, status=400)


def _yonetici_kontrol(request):
    kullanici, _ = _oturum_kullanici(request)
    if not kullanici:
        return None, JsonResponse({'hata': 'Oturum açmanız gerekiyor.'}, status=401)
    if kullanici['rol'] != 'yonetici':
        return None, JsonResponse({'hata': 'Bu işlem için yönetici yetkisi gerekiyor.'}, status=403)
    return kullanici, None


def yonetici_referanslar(request):
    if request.method != 'GET':
        return JsonResponse({'hata': 'Sadece GET isteği kabul edilir.'}, status=405)
    _, hata = _yonetici_kontrol(request)
    if hata:
        return hata
    return JsonResponse(veri_katmani.yonetici_referans_verileri())


@csrf_exempt
def yonetici_yemek_ekle(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)
    _, hata = _yonetici_kontrol(request)
    if hata:
        return hata

    try:
        veri = json.loads(request.body)
        kategori_id = int(veri.get('kategori_id'))
        ad = (veri.get('ad') or '').strip()
        kalori = int(veri.get('kalori'))
        vejetaryen = bool(veri.get('vejetaryen', False))
        if not ad or kalori < 0:
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'hata': 'Geçerli kategori, yemek adı ve kalori girmelisiniz.'}, status=400)

    try:
        yemek_id = veri_katmani.yemek_ekle(kategori_id, ad, kalori, vejetaryen)
        return JsonResponse({'mesaj': 'Yemek eklendi.', 'yemek_id': yemek_id}, status=201)
    except veri_katmani.IsKuraliHatasi as e:
        return JsonResponse({'hata': str(e)}, status=400)


@csrf_exempt
def yonetici_menu_olustur(request):
    if request.method != 'POST':
        return JsonResponse({'hata': 'Sadece POST isteği kabul edilir.'}, status=405)
    _, hata = _yonetici_kontrol(request)
    if hata:
        return hata

    try:
        veri = json.loads(request.body)
        yemekhane_id = int(veri.get('yemekhane_id'))
        tarih = (veri.get('tarih') or '').strip()
        ogun_id = int(veri.get('ogun_id'))
        ogrenci_fiyati = float(veri.get('ogrenci_fiyati'))
        personel_fiyati = float(veri.get('personel_fiyati'))
        yemek_idleri = [int(x) for x in veri.get('yemek_idleri', [])]
        if not tarih or not yemek_idleri:
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'hata': 'Tüm alanları ve en az bir yemek seçimini eksiksiz gönderin.'}, status=400)

    try:
        menu_id = veri_katmani.menu_olustur(
            yemekhane_id, tarih, ogun_id, ogrenci_fiyati, personel_fiyati, yemek_idleri
        )
        redis_istemci.menu_onbellek_temizle()
        return JsonResponse({'mesaj': 'Menü oluşturuldu.', 'menu_id': menu_id}, status=201)
    except veri_katmani.IsKuraliHatasi as e:
        return JsonResponse({'hata': str(e)}, status=400)