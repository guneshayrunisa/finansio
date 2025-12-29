from django.contrib import admin

from .models import Butce, DovizTakip, Islem, Kategori, TekrarlayanIslem, Yatirim


@admin.register(Kategori)
class KategoriAdmin(admin.ModelAdmin):
    list_display = ("ad", "renk", "kullanici")
    search_fields = ("ad",)
    list_filter = ("kullanici",)


@admin.register(Islem)
class IslemAdmin(admin.ModelAdmin):
    list_display = ("kullanici", "tip", "miktar", "tarih", "kategori", "tekrarlayan_id")
    list_filter = ("tip", "tarih", "kategori")
    search_fields = ("aciklama",)
    autocomplete_fields = ("kullanici", "kategori", "tekrarlayan_id")
    date_hierarchy = "tarih"


@admin.register(Butce)
class ButceAdmin(admin.ModelAdmin):
    list_display = ("kullanici", "kategori", "limit_aylik", "uyari_yuzdesi")
    list_filter = ("kategori",)
    autocomplete_fields = ("kullanici", "kategori")


@admin.register(TekrarlayanIslem)
class TekrarlayanIslemAdmin(admin.ModelAdmin):
    list_display = ("kullanici", "tip", "miktar", "kategori", "frekans", "aktif", "baslangic_tarihi")
    list_filter = ("tip", "frekans", "aktif")
    search_fields = ("aciklama",)
    autocomplete_fields = ("kullanici", "kategori")


@admin.register(Yatirim)
class YatirimAdmin(admin.ModelAdmin):
    list_display = ("kullanici", "ad", "tip", "miktar", "birim_fiyat", "guncel_fiyat", "alis_tarihi")
    list_filter = ("tip", "alis_tarihi")
    search_fields = ("ad",)
    autocomplete_fields = ("kullanici",)


@admin.register(DovizTakip)
class DovizTakipAdmin(admin.ModelAdmin):
    list_display = ("kullanici", "tip", "miktar", "ortalama_alis_fiyati", "guncel_fiyat")
    list_filter = ("tip",)
    autocomplete_fields = ("kullanici",)
