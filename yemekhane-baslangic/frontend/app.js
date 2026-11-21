const API = '/api';

let token = localStorage.getItem('token');
let kullanici = JSON.parse(localStorage.getItem('kullanici') || 'null');
let kullaniciAlerjenleri = [];

const el = (id) => document.getElementById(id);

function bildirimGoster(mesaj, tip = 'basari') {
    const kutu = el('bildirim');
    kutu.textContent = mesaj;
    kutu.className = `bildirim ${tip}`;
    setTimeout(() => kutu.classList.add('gizli'), 4000);
}

async function apiIstek(yol, secenekler = {}) {
    const basliklar = { 'Content-Type': 'application/json', ...(secenekler.headers || {}) };
    if (token) basliklar['Authorization'] = `Bearer ${token}`;

    const yanit = await fetch(`${API}${yol}`, { ...secenekler, headers: basliklar });
    const veri = await yanit.json();
    if (!yanit.ok) throw new Error(veri.hata || 'Bir hata oluştu.');
    return veri;
}

async function kullaniciAlerjenleriniCek() {
    try {
        const veri = await apiIstek('/profil/alerjenler/');
        kullaniciAlerjenleri = veri.alerjen_idleri || [];
    } catch {
        kullaniciAlerjenleri = [];
    }
}

async function arayuzuGuncelle() {
    if (token && kullanici) {
        el('giris-bolumu').classList.add('gizli');
        el('ana-panel').classList.remove('gizli');
        el('kullanici-bilgi').classList.remove('gizli');
        el('ad-soyad').textContent = `${kullanici.ad_soyad} (${kullanici.rol})`;
        el('bakiye-gosterge').textContent = Number(kullanici.bakiye).toFixed(2);
        el('yonetici-sekme-btn').classList.toggle('gizli', kullanici.rol !== 'yonetici');
        await kullaniciAlerjenleriniCek();
        menuleriYukle();
    } else {
        el('giris-bolumu').classList.remove('gizli');
        el('ana-panel').classList.add('gizli');
        el('kullanici-bilgi').classList.add('gizli');
    }
}

el('giris-formu').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const veri = await apiIstek('/giris/', {
            method: 'POST',
            body: JSON.stringify({ eposta: el('eposta').value, sifre: el('sifre').value })
        });
        token = veri.token;
        kullanici = veri.kullanici;
        localStorage.setItem('token', token);
        localStorage.setItem('kullanici', JSON.stringify(kullanici));
        bildirimGoster('Hoş geldiniz, ' + kullanici.ad_soyad);
        arayuzuGuncelle();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
});

el('cikis-btn').addEventListener('click', async () => {
    try { await apiIstek('/cikis/', { method: 'POST' }); } catch {}
    token = null;
    kullanici = null;
    kullaniciAlerjenleri = [];
    localStorage.clear();
    arayuzuGuncelle();
});

document.querySelectorAll('.sekme').forEach((btn) => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.sekme').forEach(b => b.classList.remove('aktif'));
        document.querySelectorAll('.sekme-icerik').forEach(s => s.classList.add('gizli'));
        btn.classList.add('aktif');
        el(`sekme-${btn.dataset.sekme}`).classList.remove('gizli');

        if (btn.dataset.sekme === 'menuler') menuleriYukle();
        if (btn.dataset.sekme === 'rezervasyonlar') rezervasyonlariYukle();
        if (btn.dataset.sekme === 'bakiye') hareketleriYukle();
        if (btn.dataset.sekme === 'profil') profilAlerjenleriYukle();
        if (btn.dataset.sekme === 'yonetici') yoneticiVerileriniYukle();
    });
});

async function menuleriYukle(haftalik = false) {
    let sorgu = '';
    if (haftalik) {
        const bugun = new Date();
        const bitis = new Date();
        bitis.setDate(bugun.getDate() + 6);
        sorgu = `?baslangic=${bugun.toISOString().slice(0, 10)}&bitis=${bitis.toISOString().slice(0, 10)}`;
    } else if (el('tarih-sec').value) {
        sorgu = `?tarih=${el('tarih-sec').value}`;
    }

    try {
        const veri = await apiIstek(`/menuler/${sorgu}`);
        const liste = el('menu-listesi');
        if (!veri.menuler.length) {
            liste.innerHTML = '<div class="kart">Seçili tarih için menü bulunamadı.</div>';
            return;
        }
        liste.innerHTML = veri.menuler.map(m => {
            const fiyat = kullanici.rol === 'ogrenci' ? m.ogrenci_fiyati : m.personel_fiyati;
            const yarimFiyat = fiyat * 0.60;
            const kahvaltiMi = m.ogun === 'Kahvaltı';

            const yemeklerHtml = m.yemekler.map(y => {
                const yemekAlerjenIdleri = y.alerjen_idler || [];
                const uyariVar = yemekAlerjenIdleri.some(id => kullaniciAlerjenleri.includes(id));
                return `
                    <li class="${uyariVar ? 'alerjen-uyari-satir' : ''}">
                        <div>
                            <span>${y.yemek} ${y.vejetaryen ? '<span class="etiket veg">Vej</span>' : ''}</span>
                            ${uyariVar ? '<span class="alerjen-uyari-rozet">⚠️ Alerjen Uyarısı</span>' : ''}
                            ${y.alerjenler ? `<div class="alerjen-bilgi">Alerjenler: ${y.alerjenler}</div>` : ''}
                        </div>
                        <span>${y.kalori} kcal</span>
                    </li>
                `;
            }).join('');

            const porsiyonSecimHtml = kahvaltiMi
                ? `<strong>Tam: ${fiyat.toFixed(2)} ₺</strong>`
                : `
                    <select id="porsiyon-${m.menu_id}" class="porsiyon-sec">
                        <option value="tam">Tam (${fiyat.toFixed(2)} ₺)</option>
                        <option value="yarim">Yarım (${yarimFiyat.toFixed(2)} ₺)</option>
                    </select>
                `;

            return `
                <div class="menu-kart">
                    <div>
                        <div class="menu-baslik">
                            <h3>${m.yemekhane} · ${m.ogun}</h3>
                            <div class="menu-meta">${m.tarih} | Toplam: ${m.toplam_kalori} kcal | Doluluk: %${m.doluluk_yuzde} (${m.bos_yer} boş)</div>
                            <div class="menu-meta">Puan: ${m.ortalama_puan ? m.ortalama_puan + ' / 5 (' + m.oy_sayisi + ' oy)' : 'Henüz oy yok'}</div>
                        </div>
                        <ul class="yemek-liste">${yemeklerHtml}</ul>
                    </div>
                    <div class="menu-alt">
                        ${porsiyonSecimHtml}
                        <button class="btn-birincil" onclick="rezervasyonYap(${m.menu_id})">Rezervasyon Yap</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

el('menu-getir-btn').addEventListener('click', () => menuleriYukle(false));
el('haftalik-btn').addEventListener('click', () => menuleriYukle(true));

async function rezervasyonYap(menuId) {
    const secim = el(`porsiyon-${menuId}`);
    const porsiyon = secim ? secim.value : 'tam';

    try {
        const veri = await apiIstek('/rezervasyon/yap/', {
            method: 'POST',
            body: JSON.stringify({ menu_id: menuId, porsiyon })
        });
        kullanici.bakiye = veri.bakiye;
        localStorage.setItem('kullanici', JSON.stringify(kullanici));
        el('bakiye-gosterge').textContent = veri.bakiye.toFixed(2);
        bildirimGoster(`${veri.mesaj} (${veri.porsiyon === 'yarim' ? 'Yarım' : 'Tam'}) Yeni bakiye: ${veri.bakiye.toFixed(2)} ₺`);
        menuleriYukle();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

async function rezervasyonlariYukle() {
    try {
        const veri = await apiIstek('/rezervasyonlarim/');
        const kutu = el('rezervasyon-listesi');
        if (!veri.rezervasyonlar.length) {
            kutu.innerHTML = '<div class="kart">Henüz rezervasyonunuz yok.</div>';
            return;
        }
        kutu.innerHTML = veri.rezervasyonlar.map(r => `
            <div class="kart" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <strong>${r.tarih} · ${r.yemekhane} (${r.ogun})</strong>
                    <div class="menu-meta">
                        Porsiyon: <strong>${r.porsiyon === 'yarim' ? 'Yarım' : 'Tam'}</strong> ·
                        Ücret: ${r.ucret.toFixed(2)} ₺ ·
                        <span class="durum ${r.durum}">${r.durum.toUpperCase()}</span>
                    </div>
                </div>
                <div>
                    ${r.durum === 'aktif' ? `<button class="btn-tehlike" onclick="rezervasyonIptal(${r.rezervasyon_id})">İptal Et</button>` : ''}
                    ${r.durum === 'kullanildi' ? `
                        <button class="btn-ikincil" onclick="puanVer(${r.menu_id})">
                            ${r.puan ? `Puanınız: ${r.puan}/5 (Güncelle)` : 'Değerlendir'}
                        </button>` : ''}
                </div>
            </div>
        `).join('');
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

async function rezervasyonIptal(rezervasyonId) {
    try {
        const veri = await apiIstek('/rezervasyon/iptal/', {
            method: 'POST',
            body: JSON.stringify({ rezervasyon_id: rezervasyonId })
        });
        kullanici.bakiye = veri.bakiye;
        localStorage.setItem('kullanici', JSON.stringify(kullanici));
        el('bakiye-gosterge').textContent = veri.bakiye.toFixed(2);
        bildirimGoster(`${veri.mesaj} İade: ${veri.iade.toFixed(2)} ₺`);
        rezervasyonlariYukle();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

async function puanVer(menuId) {
    const puan = prompt('Bu menüye 1 ile 5 arasında puan verin:');
    if (!puan) return;
    const yorum = prompt('Yorumunuz (isteğe bağlı):') || '';
    try {
        const veri = await apiIstek('/degerlendirme/', {
            method: 'POST',
            body: JSON.stringify({ menu_id: menuId, puan: Number(puan), yorum })
        });
        bildirimGoster(veri.mesaj);
        rezervasyonlariYukle();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

el('bakiye-formu').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const veri = await apiIstek('/bakiye/yukle/', {
            method: 'POST',
            body: JSON.stringify({ tutar: Number(el('yukleme-tutar').value) })
        });
        kullanici.bakiye = veri.bakiye;
        localStorage.setItem('kullanici', JSON.stringify(kullanici));
        el('bakiye-gosterge').textContent = veri.bakiye.toFixed(2);
        el('yukleme-tutar').value = '';
        bildirimGoster(`Bakiye yüklendi. Yeni bakiye: ${veri.bakiye.toFixed(2)} ₺`);
        hareketleriYukle();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
});

async function hareketleriYukle() {
    try {
        const veri = await apiIstek('/bakiye/hareketler/');
        el('hareket-tablosu').innerHTML = veri.hareketler.map(h => `
            <tr>
                <td>${h.olusturma.replace('T', ' ').slice(0, 16)}</td>
                <td>${h.tur}</td>
                <td><strong>${h.tutar.toFixed(2)} ₺</strong></td>
                <td>${h.aciklama || '-'}</td>
            </tr>
        `).join('');
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

async function profilAlerjenleriYukle() {
    try {
        const [tumVeri, kullaniciVeri] = await Promise.all([
            apiIstek('/alerjenler/'),
            apiIstek('/profil/alerjenler/')
        ]);
        kullaniciAlerjenleri = kullaniciVeri.alerjen_idleri || [];
        el('alerjen-listesi').innerHTML = tumVeri.alerjenler.map(a => `
            <label class="onay-kutu">
                <input type="checkbox" name="kullanici_alerjen" value="${a.id}" ${kullaniciAlerjenleri.includes(a.id) ? 'checked' : ''}>
                ${a.ad}
            </label>
        `).join('');
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

el('alerjen-formu').addEventListener('submit', async (e) => {
    e.preventDefault();
    const seciliIdler = Array.from(
        document.querySelectorAll('input[name="kullanici_alerjen"]:checked')
    ).map(cb => Number(cb.value));

    try {
        const veri = await apiIstek('/profil/alerjenler/', {
            method: 'POST',
            body: JSON.stringify({ alerjen_idleri: seciliIdler })
        });
        kullaniciAlerjenleri = veri.alerjen_idleri;
        bildirimGoster(veri.mesaj);
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
});

el('tarih-sec').value = new Date().toISOString().slice(0, 10);

async function yoneticiVerileriniYukle() {
    try {
        const veri = await apiIstek('/yonetici/referanslar/');
        el('yemek-kategori').innerHTML = veri.kategoriler
            .map(k => `<option value="${k.id}">${k.ad}</option>`).join('');
        el('menu-yemekhane').innerHTML = veri.yemekhaneler
            .map(y => `<option value="${y.id}">${y.ad}</option>`).join('');
        el('menu-ogun').innerHTML = veri.ogunler
            .map(o => `<option value="${o.id}">${o.ad}</option>`).join('');
        el('menu-yemek-listesi').innerHTML = veri.yemekler
            .map(y => `
                <label class="onay-kutu">
                    <input type="checkbox" name="menu_yemek" value="${y.id}">
                    ${y.ad} (${y.kalori} kcal)
                </label>
            `).join('');
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
}

el('yemek-ekle-formu').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const veri = await apiIstek('/yonetici/yemek-ekle/', {
            method: 'POST',
            body: JSON.stringify({
                kategori_id: Number(el('yemek-kategori').value),
                ad: el('yemek-ad').value,
                kalori: Number(el('yemek-kalori').value),
                vejetaryen: el('yemek-vejetaryen').checked
            })
        });
        bildirimGoster(veri.mesaj);
        el('yemek-ekle-formu').reset();
        yoneticiVerileriniYukle();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
});

el('menu-olustur-formu').addEventListener('submit', async (e) => {
    e.preventDefault();
    const seciliYemekler = Array.from(
        document.querySelectorAll('input[name="menu_yemek"]:checked')
    ).map(cb => Number(cb.value));

    if (!seciliYemekler.length) {
        bildirimGoster('En az bir yemek seçmelisiniz.', 'hata');
        return;
    }

    try {
        const veri = await apiIstek('/yonetici/menu-olustur/', {
            method: 'POST',
            body: JSON.stringify({
                yemekhane_id: Number(el('menu-yemekhane').value),
                tarih: el('menu-tarih').value,
                ogun_id: Number(el('menu-ogun').value),
                ogrenci_fiyati: Number(el('menu-ogrenci-fiyat').value),
                personel_fiyati: Number(el('menu-personel-fiyat').value),
                yemek_idleri: seciliYemekler
            })
        });
        bildirimGoster(veri.mesaj);
        el('menu-olustur-formu').reset();
    } catch (err) {
        bildirimGoster(err.message, 'hata');
    }
});

arayuzuGuncelle();