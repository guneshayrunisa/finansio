from decimal import Decimal, InvalidOperation
from datetime import date, timedelta, datetime
import csv

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Islem, Kategori
from django.http import JsonResponse
from django.db.models import Sum
from decimal import Decimal
from datetime import date
import requests
import xml.etree.ElementTree as ET
from django.views.decorators.http import require_GET
from django.core.cache import cache
from django.utils import timezone
from .models import UserProfile
import json
from django.views.decorators.http import require_POST
from finans_takip.models import UserProfile



def _haftalik_araliklar():
    """Son 4 haftanın (pazartesi-pazar) tarih aralıklarını döndürür."""
    bugun = date.today()
    bu_hafta_pazartesi = bugun - timedelta(days=bugun.weekday())
    araliklar = []
    # 1. Hafta en eski olacak şekilde 4 haftalık liste
    for geri_sayim in range(3, -1, -1):
        baslangic = bu_hafta_pazartesi - timedelta(weeks=geri_sayim)
        bitis = baslangic + timedelta(days=6)
        araliklar.append((baslangic, bitis))
    return araliklar


def signup_view(request):
    """Kullanıcı kayıt sayfası"""
    if request.user.is_authenticated:
        return redirect("dashboard")
    
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)  
            email = (request.POST.get("email") or "").strip()
            user.email = email

            user.save()  

            login(request, user)
            messages.success(request, f"Hoş geldiniz, {user.username}! Hesabınız başarıyla oluşturuldu.")
            return redirect("dashboard")
    else:
        form = UserCreationForm()
    
    return render(request, "registration/signup.html", {"form": form})



@login_required
@login_required
def dashboard_view(request):
    """Anasayfa / dashboard görünümü."""

    # Kullanıcının işlemleri (en güncel en üstte)
    islem_listesi = (
        Islem.objects
        .filter(kullanici=request.user)
        .select_related("kategori")
        .order_by("-tarih")
    )

    # Kullanıcı profilini garanti altına al
    profile, created = UserProfile.objects.get_or_create(user=request.user,defaults={"monthly_income": Decimal("0.00")})

    # ----------------- POST: hızlı ekleme -----------------
    if request.method == "POST":
        action = request.POST.get("action")

        # Kategori ekle
        if action == "kategori_ekle":
            ad = (request.POST.get("kategori_adi") or "").strip()
            if ad:
                kategori, olusturuldu = Kategori.objects.get_or_create(ad=ad)
                if olusturuldu:
                    messages.success(request, f"'{ad}' kategorisi eklendi.")
                else:
                    messages.info(request, f"'{ad}' kategorisi zaten mevcut.")
            else:
                messages.error(request, "Kategori adı boş olamaz.")
            return redirect("dashboard")

        # İşlem ekle (haftaya göre)
        if action == "islem_ekle":
            miktar_raw = (request.POST.get("miktar") or "").strip()
            kategori_id = request.POST.get("kategori")
            hafta_no_raw = request.POST.get("hafta") or "4"
            aciklama = (request.POST.get("aciklama") or "").strip()

            # hafta_no güvenliği
            try:
                hafta_no = int(hafta_no_raw)
            except (TypeError, ValueError):
                hafta_no = 4

            # miktar güvenliği
            try:
                miktar = Decimal(miktar_raw)
            except (TypeError, ValueError, InvalidOperation):
                messages.error(request, "Geçerli bir miktar girin.")
                return redirect("dashboard")

            # Kategori kontrolü
            kategori = Kategori.objects.filter(pk=kategori_id).first()
            if not kategori:
                messages.error(request, "Lütfen geçerli bir kategori seçin.")
                return redirect("dashboard")

            # İşlem tarihi: seçilen haftanın ortasına koy
            hafta_araliklari = _haftalik_araliklar()
            hafta_index = max(1, min(hafta_no, 4)) - 1
            hafta_baslangic, hafta_bitis = hafta_araliklari[hafta_index]
            islem_tarihi = hafta_baslangic + timedelta(days=2)

            Islem.objects.create(
                kullanici=request.user,
                tip="GIDER",
                miktar=miktar,
                tarih=islem_tarihi,
                aciklama=aciklama or "Hızlı eklenen gider",
                kategori=kategori,
            )
            messages.success(request, "Harcama eklendi.")
            return redirect("dashboard")

    # ----------------- GET: özet veriler -----------------
    bugun = date.today()
    ay_basi = bugun.replace(day=1)

    aylik_gider = (
        islem_listesi
        .filter(tip="GIDER", tarih__gte=ay_basi, tarih__lte=bugun)
        .aggregate(toplam=Sum("miktar"))["toplam"]
        or Decimal("0")
    )

    dort_hafta_once = bugun - timedelta(weeks=4)
    son_4_hafta_toplam = (
        islem_listesi
        .filter(tip="GIDER", tarih__gte=dort_hafta_once, tarih__lte=bugun)
        .aggregate(toplam=Sum("miktar"))["toplam"]
        or Decimal("0")
    )

    # Haftalık ortalama (4 haftaya böl)
    haftalik_ort = (son_4_hafta_toplam / Decimal("4")) if son_4_hafta_toplam else Decimal("0")
    haftalik_ort = round(haftalik_ort, 2)

    toplam_gelir = (
        islem_listesi
        .filter(tip="GELIR")
        .aggregate(toplam=Sum("miktar"))["toplam"]
        or Decimal("0")
    )
    toplam_gider = (
        islem_listesi
        .filter(tip="GIDER")
        .aggregate(toplam=Sum("miktar"))["toplam"]
        or Decimal("0")
    )

    bakiye = toplam_gelir - toplam_gider

    # Aylık gelir (profil)
    # monthly_income bazen None olabiliyor; güvenli şekilde 0 yapıyoruz
    aylik_gelir = profile.monthly_income
    if aylik_gelir is None:
        aylik_gelir = Decimal("0")
    # Eğer DB’de bozuk değer olasılığı varsa, ekstra güvenlik:
    try:
        aylik_gelir = Decimal(aylik_gelir)
    except (TypeError, ValueError, InvalidOperation):
        aylik_gelir = Decimal("0")

    # Haftalık veriler (4 hafta)
    hafta_araliklari = _haftalik_araliklar()
    haftalik_veri = []
    en_yuksek = Decimal("0")

    for idx, (baslangic, bitis) in enumerate(hafta_araliklari, start=1):
        qs = islem_listesi.filter(
            tip="GIDER",
            tarih__gte=baslangic,
            tarih__lte=bitis,
        )
        toplam = qs.aggregate(toplam=Sum("miktar"))["toplam"] or Decimal("0")
        en_yuksek = max(en_yuksek, toplam)

        haftalik_veri.append({
            "etiket": f"{idx}. Hafta",
            "toplam": toplam,
            "baslangic": baslangic,
            "bitis": bitis,
            "islemler": qs.order_by("-tarih"),
            "yuzde": 0,
        })

    max_deger = en_yuksek if en_yuksek > 0 else Decimal("1")
    for hafta in haftalik_veri:
        hafta["yuzde"] = int((hafta["toplam"] / max_deger) * 100)

    bu_hafta_toplam = haftalik_veri[-1]["toplam"] if haftalik_veri else Decimal("0")
    kategori_sayisi = Kategori.objects.count()

    context = {
        "aylik_gider": aylik_gider,
        "haftalik_ort": haftalik_ort,
        "kategori_sayisi": kategori_sayisi,
        "islem_listesi": islem_listesi[:10],
        "kategoriler": Kategori.objects.all(),
        "haftalik_veri": haftalik_veri,
        "bakiye": bakiye,
        "bu_hafta_toplam": bu_hafta_toplam,
        "bugun": bugun,
        "aylik_gelir": aylik_gelir,
        "monthly_income": aylik_gelir,  # template’te bunu kullan
        "profile": profile,             # istersen template’te profile.monthly_income da kullanırsın
    }

    return render(request, "finans_takip/dashboard.html", context)

@login_required
def harcama_ekle_view(request):
    """
    Harcama ekleme için ayrı sayfa.
    - Tarih seçiciden gerçek tarih alır
    - Tarih yoksa eski hafta mantığı (ortasına koyma) ile çalışır
    - Canlı özet için bu hafta toplam ve kategorilerin aylık toplamını hazırlar
    """
    bugun = timezone.localdate()
    hafta_araliklari = _haftalik_araliklar()
    bu_hafta_baslangic, bu_hafta_bitis = hafta_araliklari[-1]

    # ----------------- POST -----------------
    if request.method == "POST":
        islem_turu = request.POST.get("action")

        # Kategori ekleme
        if islem_turu == "kategori_ekle":
            ad = (request.POST.get("kategori_adi") or "").strip()
            if ad:
                kategori, olusturuldu = Kategori.objects.get_or_create(ad=ad)
                if olusturuldu:
                    messages.success(request, f"'{ad}' kategorisi eklendi.")
                else:
                    messages.info(request, f"'{ad}' kategorisi zaten mevcut.")
            else:
                messages.error(request, "Kategori adı boş olamaz.")
            return redirect("harcama_ekle")

        # İşlem ekleme
        if islem_turu == "islem_ekle":
            miktar_raw = request.POST.get("miktar")
            kategori_id = request.POST.get("kategori")
            hafta_no_raw = request.POST.get("hafta")  # fallback için
            aciklama = (request.POST.get("aciklama") or "").strip()
            tarih_str = request.POST.get("tarih")  # date picker'dan

            # Miktar parse
            try:
                miktar = Decimal(miktar_raw)
            except (TypeError, ValueError, InvalidOperation):
                messages.error(request, "Geçerli bir miktar girin.")
                return redirect("harcama_ekle")

            # Tarihi öncelikle date picker'dan al
            if tarih_str:
                try:
                    islem_tarihi = datetime.strptime(tarih_str, "%Y-%m-%d").date()
                except ValueError:
                    islem_tarihi = bugun
            else:
                # Eski davranış: seçilen haftanın ortası
                hafta_no = int(hafta_no_raw or 4)
                hafta_index = max(1, min(hafta_no, 4)) - 1
                hafta_baslangic, hafta_bitis = hafta_araliklari[hafta_index]
                islem_tarihi = hafta_baslangic + timedelta(days=2)

            kategori = Kategori.objects.filter(pk=kategori_id).first()
            if not kategori:
                messages.error(request, "Lütfen geçerli bir kategori seçin.")
                return redirect("harcama_ekle")

            Islem.objects.create(
                kullanici=request.user,
                tip="GIDER",
                miktar=miktar,
                tarih=islem_tarihi,
                aciklama=aciklama or "Hızlı eklenen gider",
                kategori=kategori,
            )
            messages.success(request, "Harcama eklendi.")
            return redirect("harcama_ekle")

    # ----------------- GET: form + canlı özet verileri -----------------
    ay_baslangic = bugun.replace(day=1)

    # Kategoriler + bu ayki toplamları (canlı özet + JS data-attribute için)
    kategoriler = (
        Kategori.objects
        .annotate(
            aylik_toplam=Sum(
                "islem__miktar",
                filter=Q(
                    islem__kullanici=request.user,
                    islem__tarih__gte=ay_baslangic,
                    islem__tip="GIDER",
                ),
            )
        )
    )

    # Bu hafta toplam gider (canlı özet)
    bu_hafta_toplam = (
        Islem.objects.filter(
            kullanici=request.user,
            tip="GIDER",
            tarih__gte=bu_hafta_baslangic,
            tarih__lte=bu_hafta_bitis,
        ).aggregate(t=Sum("miktar"))["t"]
        or Decimal("0")
    )

    # İlk kategori için aylık toplam (varsayılan)
    if kategoriler:
        ilk_kategori_aylik = kategoriler[0].aylik_toplam or Decimal("0")
    else:
        ilk_kategori_aylik = Decimal("0")

    # Haftalar için (template sadece forloop.counter kullanıyor)
    haftalik_veri = range(4)

    context = {
        "kategoriler": kategoriler,
        "haftalik_veri": haftalik_veri,
        "bugun": bugun,
        "bu_hafta_toplam": bu_hafta_toplam,
        "ilk_kategori_aylik": ilk_kategori_aylik,
    }
    return render(request, "finans_takip/harcama_ekle.html", context)


@login_required
def export_view(request):
    """Verileri CSV olarak export et"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="finansio_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Tarih', 'Tip', 'Kategori', 'Miktar', 'Açıklama'])
    
    islemler = Islem.objects.filter(kullanici=request.user).order_by('-tarih')
    for islem in islemler:
        writer.writerow([
            islem.tarih.strftime('%d.%m.%Y'),
            islem.get_tip_display(),
            islem.kategori.ad if islem.kategori else '-',
            str(islem.miktar),
            islem.aciklama or '-',
        ])
    
    return response


@login_required
def islem_sil_view(request, islem_id):
    """İşlem silme"""
    islem = get_object_or_404(Islem, pk=islem_id, kullanici=request.user)
    islem.delete()
    messages.success(request, "Harcama silindi.")
    return redirect("dashboard")

@login_required
def raporlar_view(request):
    """Raporlar Sayfası - Gerçek verilerle"""
    
    # Zaman dilimi seçimi
    zaman_dilimi = request.GET.get('zaman_dilimi', 'aylik')
    
    # Verileri al
    islem_listesi = (
        Islem.objects
        .filter(kullanici=request.user)
        .select_related("kategori")
        .order_by("-tarih")
    )

    bugun = date.today()
    
    # Zaman dilimi aralıklarını belirle
    if zaman_dilimi == 'haftalik':
        baslangic_tarih = bugun - timedelta(days=bugun.weekday())  # Bu haftanın pazartesi
        bitis_tarih = bugun
    elif zaman_dilimi == 'yillik':
        baslangic_tarih = bugun.replace(month=1, day=1)  # Yılın başı
        bitis_tarih = bugun
    else:  # aylik (default)
        baslangic_tarih = bugun.replace(day=1)  # Ayın başı
        bitis_tarih = bugun

    # Seçili dönem için toplam gelir
    toplam_gelir = (
        islem_listesi
        .filter(tip="GELIR", tarih__gte=baslangic_tarih, tarih__lte=bitis_tarih)
        .aggregate(Sum("miktar"))["miktar__sum"]
        or Decimal("0")
    )
    
    # Seçili dönem için toplam gider
    toplam_gider = (
        islem_listesi
        .filter(tip="GIDER", tarih__gte=baslangic_tarih, tarih__lte=bitis_tarih)
        .aggregate(Sum("miktar"))["miktar__sum"]
        or Decimal("0")
    )
    
    fark = toplam_gelir - toplam_gider

    # Kategorilere göre harcama verisi (seçili dönem için)
    harcama_kategorileri = (
        islem_listesi
        .filter(tip="GIDER", tarih__gte=baslangic_tarih, tarih__lte=bitis_tarih)
        .values('kategori__ad')
        .annotate(toplam_harcama=Sum('miktar'))
        .order_by('-toplam_harcama')
    )

    # QuerySet'i liste olarak dönüştür
    harcama_kategorileri_list = []
    for item in harcama_kategorileri:
        harcama_kategorileri_list.append({
            'kategori__ad': item['kategori__ad'] or 'Diğer',
            'toplam_harcama': float(item['toplam_harcama'])
        })

    # Haftalık veriler (son 4 hafta)
    haftalik_veriler = []
    haftalik_gelir = []
    haftalik_gider = []
    haftalik_etiketler = []
    
    for i in range(3, -1, -1):  # Son 4 hafta (4, 3, 2, 1. hafta)
        hafta_sonu = bugun - timedelta(weeks=i)
        hafta_basi = hafta_sonu - timedelta(days=6)
        
        # Her hafta için gelir
        gelir = (
            islem_listesi
            .filter(tip="GELIR", tarih__gte=hafta_basi, tarih__lte=hafta_sonu)
            .aggregate(Sum("miktar"))["miktar__sum"]
            or Decimal("0")
        )
        
        # Her hafta için gider
        gider = (
            islem_listesi
            .filter(tip="GIDER", tarih__gte=hafta_basi, tarih__lte=hafta_sonu)
            .aggregate(Sum("miktar"))["miktar__sum"]
            or Decimal("0")
        )
        
        haftalik_gelir.append(float(gelir))
        haftalik_gider.append(float(gider))
        haftalik_etiketler.append(f"{4-i}. Hafta")

    # Aylık veriler (son 6 ay)
    aylik_veriler = []
    aylik_gelir = []
    aylik_gider = []
    aylik_etiketler = []
    
    ay_isimleri = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 
                   'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
    
    for i in range(5, -1, -1):  # Son 6 ay
        tarih = bugun - timedelta(days=30 * i)
        ay_basi = tarih.replace(day=1)
        
        # Ayın son günü
        if tarih.month == 12:
            ay_sonu = tarih.replace(day=31)
        else:
            ay_sonu = (tarih.replace(month=tarih.month + 1, day=1) - timedelta(days=1))
        
        # Her ay için gelir
        gelir = (
            islem_listesi
            .filter(tip="GELIR", tarih__gte=ay_basi, tarih__lte=ay_sonu)
            .aggregate(Sum("miktar"))["miktar__sum"]
            or Decimal("0")
        )
        
        # Her ay için gider
        gider = (
            islem_listesi
            .filter(tip="GIDER", tarih__gte=ay_basi, tarih__lte=ay_sonu)
            .aggregate(Sum("miktar"))["miktar__sum"]
            or Decimal("0")
        )
        
        aylik_gelir.append(float(gelir))
        aylik_gider.append(float(gider))
        aylik_etiketler.append(ay_isimleri[tarih.month - 1])

    context = {
        "zaman_dilimi": zaman_dilimi,
        "toplam_gelir": toplam_gelir,
        "toplam_harcama": toplam_gider,
        "fark": fark,
        "harcama_kategorileri": harcama_kategorileri_list,
        "haftalik_gelir": haftalik_gelir,
        "haftalik_gider": haftalik_gider,
        "haftalik_etiketler": haftalik_etiketler,
        "aylik_gelir": aylik_gelir,
        "aylik_gider": aylik_gider,
        "aylik_etiketler": aylik_etiketler,
    }

    return render(request, 'finans_takip/raporlar.html', context)


@login_required
def ayarlar_view(request):
    """
    Ayarlar sayfası:
    - Profil bilgileri (kullanıcı adı, email) güncelleme
    - Şifre değiştir sayfasına yönlendirme (Django'nun built-in view'i)
    - Basit uygulama ayarları (tema / bildirim gibi) (şimdilik UI)
    - Aylık gelir güncelleme (UserProfile.monthly_income)
    """
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # ✅ Kullanıcının profil kaydı (monthly_income burada duracak)
    # Signal yazdıysan normalde zaten oluşur; yine de garanti olsun:
    profile, _ = user.profile.__class__.objects.get_or_create(user=user) if hasattr(user, "profile") else (None, None)
    # Yukarıdaki satır bazen karışık gelebilir; en temiz garanti yöntem:
    # from .models import UserProfile
    # profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        action = request.POST.get("action")

        # 1) Profil güncelle
        if action == "update_profile":
            username = (request.POST.get("username") or "").strip()
            if not username:
                messages.error(request, "Kullanıcı adı boş olamaz.")
                return redirect("ayarlar")

            # username başka kullanıcıda var mı?
            from django.contrib.auth.models import User
            if User.objects.filter(username=username).exclude(id=user.id).exists():
                messages.error(request, "Bu kullanıcı adı zaten kullanılıyor.")
                return redirect("ayarlar")

            # ✅ Aylık gelir (profil altında)
            income_raw = (request.POST.get("monthly_income") or "").strip()

            user.username = username
            user.save()

            # income boş değilse kaydet, boşsa mevcut kalsın
            if income_raw != "":
                # TR format desteği: 25.000,50 -> 25000.50
                income_raw = income_raw.replace(" ", "")
                income_raw = income_raw.replace(".", "").replace(",", ".")
                try:
                    income_val = Decimal(income_raw)
                    if income_val < 0:
                        messages.error(request, "Aylık gelir negatif olamaz.")
                        return redirect("ayarlar")
                    profile.monthly_income = income_val
                    profile.save()
                except (InvalidOperation, ValueError):
                    messages.error(request, "Aylık gelir formatı hatalı. Örn: 25000 veya 25.000,50")
                    return redirect("ayarlar")

            messages.success(request, "Profil bilgilerin güncellendi.")
            return redirect("ayarlar")

        # 2) Basit tercih ayarı örneği (UI şimdilik)
        if action == "update_preferences":
            notify_email = request.POST.get("notify_email") == "on"
            currency = request.POST.get("currency") or "TRY"

            messages.success(
                request,
                f"Ayarlar kaydedildi. E-posta bildirim: {'Açık' if notify_email else 'Kapalı'}, Para birimi: {currency}"
            )
            return redirect("ayarlar")

    return render(request, "finans_takip/ayarlar.html", {
        "user_obj": user,
        "monthly_income": profile.monthly_income if profile else 0,
    })

@login_required
@require_POST
def tema_kaydet_view(request):
    data = json.loads(request.body.decode("utf-8"))
    dark_mode = bool(data.get("dark_mode", False))

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.dark_mode = dark_mode
    profile.save()

    return JsonResponse({"ok": True, "dark_mode": profile.dark_mode})

@require_GET
def fx_rates_api(request):
    """
    TCMB today.xml'den döviz kurlarını çekip JSON döndürür.
    Not: TCMB verisi 'gün içi anlık borsa' değil; TCMB'nin yayınladığı güncel kur tablosudur.
    """
    cache_key = "fx_rates_tcmb_today"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached, safe=False)

    url = "https://www.tcmb.gov.tr/kurlar/today.xml"

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()

        root = ET.fromstring(r.content)

        rates = []
        # TCMB XML'de her Currency node'u bir döviz
        for cur in root.findall("Currency"):
            code = cur.get("CurrencyCode")
            name = cur.findtext("CurrencyName")
            unit = cur.findtext("Unit")

            # ForexBuying / ForexSelling: bankalar arası alış/satış benzeri alanlar
            buy = cur.findtext("ForexBuying")
            sell = cur.findtext("ForexSelling")

            # Bazı satırlarda boş gelebilir (örn: bazı kurlar)
            def to_float(x):
                try:
                    if x is None:
                        return None
                    x = x.strip()
                    if not x:
                        return None
                    return float(x.replace(",", "."))
                except:
                    return None

            rates.append({
                "code": code,
                "name": name,
                "unit": int(unit) if unit and unit.isdigit() else unit,
                "buy": to_float(buy),
                "sell": to_float(sell),
            })

        payload = {
            "source": "TCMB",
            "last_updated": timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M:%S"),
            "rates": rates,
        }

        # 60 saniye cache (spam istek atmasın)
        cache.set(cache_key, payload, 60)

        return JsonResponse(payload, safe=False)

    except Exception as e:
        return JsonResponse({
            "source": "TCMB",
            "last_updated": timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M:%S"),
            "rates": [],
            "error": str(e),
        }, status=500)
    

