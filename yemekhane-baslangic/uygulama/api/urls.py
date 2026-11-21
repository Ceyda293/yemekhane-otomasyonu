from django.urls import path
from . import views

urlpatterns = [
    path('giris/', views.giris_yap),
    path('cikis/', views.cikis_yap),
    path('menuler/', views.menuler_listele),
    path('rezervasyon/yap/', views.rezervasyon_yap),
    path('rezervasyon/iptal/', views.rezervasyon_iptal),
    path('rezervasyonlarim/', views.rezervasyonlarim),
    path('bakiye/yukle/', views.bakiye_yukle),
    path('bakiye/hareketler/', views.bakiye_hareketleri),
    path('degerlendirme/', views.degerlendirme_yap),
    path('yonetici/referanslar/', views.yonetici_referanslar),
    path('yonetici/yemek-ekle/', views.yonetici_yemek_ekle),
    path('yonetici/menu-olustur/', views.yonetici_menu_olustur),
]
