from django.db import connections, DatabaseError, transaction


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def kullanici_getir_eposta(eposta):
    with connections['replica'].cursor() as cursor:
        cursor.execute(
            "SELECT id, ad, soyad, eposta, sifre_hash, rol, ogrenci_no, bakiye "
            "FROM kullanicilar WHERE eposta = %s AND aktif = 1",
            [eposta]
        )
        sonuclar = dictfetchall(cursor)
        return sonuclar[0] if sonuclar else None


def menuleri_getir(tarih=None, baslangic=None, bitis=None, yemekhane_id=None, ogun_id=None):
    sorgu = """
        SELECT 
            d.menu_id, d.tarih, d.yemekhane_id, d.yemekhane,
            d.ogun_id, d.ogun, d.ogun_sira, d.rezervasyon_son,
            d.ogrenci_fiyati, d.personel_fiyati,
            d.yemek_id, d.yemek, d.kategori, d.kategori_sira,
            d.kalori, d.vejetaryen, d.alerjenler, d.alerjen_idler,
            dol.kapasite, dol.rezerve, dol.bos_yer, dol.doluluk_yuzde,
            p.oy_sayisi, p.ortalama_puan
        FROM v_menu_detay d
        LEFT JOIN v_menu_doluluk dol ON d.menu_id = dol.menu_id
        LEFT JOIN v_menu_puan p ON d.menu_id = p.menu_id
        WHERE 1=1
    """
    parametreler = []

    if tarih:
        sorgu += " AND d.tarih = %s"
        parametreler.append(tarih)
    elif baslangic and bitis:
        sorgu += " AND d.tarih BETWEEN %s AND %s"
        parametreler.extend([baslangic, bitis])
    else:
        sorgu += " AND d.tarih = CURDATE()"

    if yemekhane_id:
        sorgu += " AND d.yemekhane_id = %s"
        parametreler.append(yemekhane_id)

    if ogun_id:
        sorgu += " AND d.ogun_id = %s"
        parametreler.append(ogun_id)

    sorgu += " ORDER BY d.tarih, d.yemekhane_id, d.ogun_sira, d.kategori_sira, d.yemek"

    with connections['replica'].cursor() as cursor:
        cursor.execute(sorgu, parametreler)
        return dictfetchall(cursor)


class IsKuraliHatasi(Exception):
    pass


def _sp_cagir(sp_adi, parametreler):
    placeholders = ", ".join(["%s"] * len(parametreler))
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(f"CALL {sp_adi}({placeholders})", parametreler)
            sonuclar = dictfetchall(cursor)
            return sonuclar[0] if sonuclar else None
    except DatabaseError as e:
        hata_kodu = e.args[0] if len(e.args) > 0 else None
        hata_mesaji = e.args[1] if len(e.args) > 1 else "İşlem sırasında bir hata oluştu."
        if hata_kodu == 1644:
            raise IsKuraliHatasi(hata_mesaji)
        raise


def rezervasyon_yap(kullanici_id, menu_id, porsiyon='tam'):
    return _sp_cagir("sp_rezervasyon_yap", [kullanici_id, menu_id, porsiyon])


def rezervasyon_iptal(kullanici_id, rezervasyon_id):
    return _sp_cagir("sp_rezervasyon_iptal", [kullanici_id, rezervasyon_id])


def bakiye_yukle(kullanici_id, tutar):
    return _sp_cagir("sp_bakiye_yukle", [kullanici_id, tutar])


def kullanici_rezervasyonlari_getir(kullanici_id):
    sorgu = """
        SELECT 
            r.id AS rezervasyon_id, r.menu_id, r.durum, r.porsiyon, r.ucret,
            r.olusturma, r.kullanma_zamani, r.iptal_zamani,
            m.tarih, m.yemekhane, m.ogun, m.rezervasyon_son,
            d.puan, d.yorum
        FROM rezervasyonlar r
        JOIN v_menu_doluluk m ON r.menu_id = m.menu_id
        LEFT JOIN degerlendirmeler d 
            ON d.menu_id = r.menu_id AND d.kullanici_id = r.kullanici_id
        WHERE r.kullanici_id = %s
        ORDER BY m.tarih DESC, r.olusturma DESC
    """
    with connections['replica'].cursor() as cursor:
        cursor.execute(sorgu, [kullanici_id])
        return dictfetchall(cursor)


def kullanici_bakiye_hareketleri_getir(kullanici_id):
    sorgu = """
        SELECT id, tur, tutar, rezervasyon_id, aciklama, olusturma
        FROM bakiye_hareketleri
        WHERE kullanici_id = %s
        ORDER BY olusturma DESC
        LIMIT 50
    """
    with connections['replica'].cursor() as cursor:
        cursor.execute(sorgu, [kullanici_id])
        return dictfetchall(cursor)


def degerlendirme_kaydet(kullanici_id, menu_id, puan, yorum=None):
    with connections['default'].cursor() as cursor:
        cursor.execute(
            "SELECT id FROM rezervasyonlar "
            "WHERE kullanici_id = %s AND menu_id = %s AND durum = 'kullanildi' LIMIT 1",
            [kullanici_id, menu_id]
        )
        if not cursor.fetchone():
            raise IsKuraliHatasi("Yalnızca kullandığınız menüleri değerlendirebilirsiniz.")

        cursor.execute(
            "SELECT id FROM degerlendirmeler WHERE kullanici_id = %s AND menu_id = %s LIMIT 1",
            [kullanici_id, menu_id]
        )
        mevcut = cursor.fetchone()
        if mevcut:
            cursor.execute(
                "UPDATE degerlendirmeler SET puan = %s, yorum = %s WHERE id = %s",
                [puan, yorum, mevcut[0]]
            )
        else:
            cursor.execute(
                "INSERT INTO degerlendirmeler (kullanici_id, menu_id, puan, yorum) "
                "VALUES (%s, %s, %s, %s)",
                [kullanici_id, menu_id, puan, yorum]
            )


def alerjenleri_getir():
    with connections['replica'].cursor() as cursor:
        cursor.execute("SELECT id, ad FROM alerjenler ORDER BY id")
        return dictfetchall(cursor)


def kullanici_alerjenleri_getir(kullanici_id):
    with connections['replica'].cursor() as cursor:
        cursor.execute(
            "SELECT alerjen_id FROM kullanici_alerjenleri WHERE kullanici_id = %s ORDER BY alerjen_id",
            [kullanici_id]
        )
        return [satir[0] for satir in cursor.fetchall()]


def kullanici_alerjenleri_kaydet(kullanici_id, alerjen_idleri):
    with transaction.atomic(using='default'):
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "DELETE FROM kullanici_alerjenleri WHERE kullanici_id = %s",
                [kullanici_id]
            )
            for a_id in set(alerjen_idleri):
                cursor.execute(
                    "INSERT INTO kullanici_alerjenleri (kullanici_id, alerjen_id) VALUES (%s, %s)",
                    [kullanici_id, a_id]
                )


def yonetici_referans_verileri():
    with connections['replica'].cursor() as cursor:
        cursor.execute("SELECT * FROM yemekhaneler ORDER BY id")
        yemekhaneler = dictfetchall(cursor)

        cursor.execute("SELECT * FROM ogunler ORDER BY id")
        ogunler = dictfetchall(cursor)

        cursor.execute("SELECT * FROM yemek_kategorileri ORDER BY id")
        kategoriler = dictfetchall(cursor)

        cursor.execute("SELECT id, kategori_id, ad, kalori, vejetaryen FROM yemekler ORDER BY kategori_id, ad")
        yemekler = dictfetchall(cursor)

    return {
        'yemekhaneler': yemekhaneler,
        'ogunler': ogunler,
        'kategoriler': kategoriler,
        'yemekler': yemekler,
    }


def yemek_ekle(kategori_id, ad, kalori, vejetaryen):
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                "INSERT INTO yemekler (kategori_id, ad, kalori, vejetaryen) VALUES (%s, %s, %s, %s)",
                [kategori_id, ad, kalori, 1 if vejetaryen else 0]
            )
            return cursor.lastrowid
    except DatabaseError as e:
        if len(e.args) > 0 and e.args[0] == 1062:
            raise IsKuraliHatasi("Bu isimde bir yemek zaten kayıtlı.")
        raise


def menu_olustur(yemekhane_id, tarih, ogun_id, ogrenci_fiyati, personel_fiyati, yemek_idleri):
    try:
        with transaction.atomic(using='default'):
            with connections['default'].cursor() as cursor:
                cursor.execute(
                    "INSERT INTO menuler (yemekhane_id, tarih, ogun_id, ogrenci_fiyati, personel_fiyati) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [yemekhane_id, tarih, ogun_id, ogrenci_fiyati, personel_fiyati]
                )
                menu_id = cursor.lastrowid

                for y_id in yemek_idleri:
                    cursor.execute(
                        "INSERT INTO menu_yemekleri (menu_id, yemek_id) VALUES (%s, %s)",
                        [menu_id, y_id]
                    )
                return menu_id
    except DatabaseError as e:
        if len(e.args) > 0 and e.args[0] == 1062:
            raise IsKuraliHatasi("Bu yemekhane, tarih ve öğün için zaten bir menü tanımlı.")
        raise