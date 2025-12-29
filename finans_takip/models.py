# finans_takip/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

# Kategori Modeli
class Kategori(models.Model):
    ad = models.CharField(max_length=100, unique=True)
    renk = models.CharField(max_length=7, default='#4e8df5')  # Varsayılan renk
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Kullanıcıya özel kategori
    
    class Meta:
        verbose_name_plural = "Kategoriler"
    
    def __str__(self):
        return self.ad

# İşlem Modeli (Gelir veya Gider)
class Islem(models.Model):
    K_TIPI = [
        ('GIDER', 'Gider'),
        ('GELIR', 'Gelir'),
    ]
    
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE)
    tip = models.CharField(max_length=5, choices=K_TIPI)
    miktar = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    tarih = models.DateField()
    aciklama = models.TextField(blank=True, null=True)
    kategori = models.ForeignKey(Kategori, on_delete=models.SET_NULL, null=True)
    tekrarlayan_id = models.ForeignKey('TekrarlayanIslem', on_delete=models.SET_NULL, null=True, blank=True)
    olusturulma_tarihi = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-tarih', '-olusturulma_tarihi']
        verbose_name_plural = "İşlemler"
    
    def __str__(self):
        return f"{self.get_tip_display()} - {self.miktar} TL ({self.tarih})"

# Bütçe Limiti Modeli
class Butce(models.Model):
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE)
    kategori = models.ForeignKey(Kategori, on_delete=models.CASCADE)
    limit_aylik = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    uyari_yuzdesi = models.IntegerField(default=80, help_text="Limitin yüzde kaçına gelindiğinde uyarı verilsin")
    
    class Meta:
        unique_together = ['kullanici', 'kategori']
        verbose_name_plural = "Bütçeler"
    
    def __str__(self):
        return f"{self.kategori.ad} Bütçesi: {self.limit_aylik} TL"

# Tekrarlayan İşlemler Modeli
class TekrarlayanIslem(models.Model):
    FREKANS_SECENEKLERI = [
        ('GUNLUK', 'Günlük'),
        ('HAFTALIK', 'Haftalık'),
        ('AYLIK', 'Aylık'),
        ('YILLIK', 'Yıllık'),
    ]
    
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE)
    tip = models.CharField(max_length=5, choices=Islem.K_TIPI)
    miktar = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    kategori = models.ForeignKey(Kategori, on_delete=models.SET_NULL, null=True)
    aciklama = models.TextField(blank=True, null=True)
    frekans = models.CharField(max_length=10, choices=FREKANS_SECENEKLERI, default='AYLIK')
    baslangic_tarihi = models.DateField()
    bitis_tarihi = models.DateField(null=True, blank=True)
    aktif = models.BooleanField(default=True)
    son_islem_tarihi = models.DateField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Tekrarlayan İşlemler"
    
    def __str__(self):
        return f"{self.get_tip_display()} - {self.miktar} TL ({self.get_frekans_display()})"

# Yatırım Portföy Modeli
class Yatirim(models.Model):
    YATIRIM_TIPLERI = [
        ('HISSE', 'Hisse Senedi'),
        ('FON', 'Yatırım Fonu'),
        ('KRIPTO', 'Kripto Para'),
        ('ALTIN', 'Altın'),
        ('DIGER', 'Diğer'),
    ]
    
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE)
    ad = models.CharField(max_length=100)
    tip = models.CharField(max_length=10, choices=YATIRIM_TIPLERI)
    miktar = models.DecimalField(max_digits=15, decimal_places=4, validators=[MinValueValidator(0)])
    birim_fiyat = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    alis_tarihi = models.DateField()
    guncel_fiyat = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    guncelleme_tarihi = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Yatırımlar"
    
    @property
    def toplam_deger(self):
        if self.guncel_fiyat:
            return self.miktar * self.guncel_fiyat
        return self.miktar * self.birim_fiyat
    
    @property
    def kar_zarar(self):
        return self.toplam_deger - (self.miktar * self.birim_fiyat)
    
    @property
    def kar_zarar_yuzdesi(self):
        if self.birim_fiyat > 0:
            return ((self.guncel_fiyat or self.birim_fiyat) - self.birim_fiyat) / self.birim_fiyat * 100
        return 0
    
    def __str__(self):
        return f"{self.ad} - {self.miktar} adet"

# Döviz ve Emtia Takibi Modeli
class DovizTakip(models.Model):
    DOVIZ_TIPLERI = [
        ('USD', 'ABD Doları'),
        ('EUR', 'Euro'),
        ('GBP', 'İngiliz Sterlini'),
        ('JPY', 'Japon Yeni'),
        ('CHF', 'İsviçre Frangı'),
        ('ALTIN', 'Altın (Gram)'),
        ('GUMUS', 'Gümüş (Gram)'),
        ('BITCOIN', 'Bitcoin'),
    ]
    
    kullanici = models.ForeignKey(User, on_delete=models.CASCADE)
    tip = models.CharField(max_length=10, choices=DOVIZ_TIPLERI)
    miktar = models.DecimalField(max_digits=15, decimal_places=4, validators=[MinValueValidator(0)])
    ortalama_alis_fiyati = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    guncel_fiyat = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    guncelleme_tarihi = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['kullanici', 'tip']
        verbose_name_plural = "Döviz Takibi"
    
    @property
    def toplam_tl_degeri(self):
        if self.guncel_fiyat:
            return self.miktar * self.guncel_fiyat
        return self.miktar * self.ortalama_alis_fiyati
    
    @property
    def kar_zarar(self):
        if self.guncel_fiyat:
            return (self.guncel_fiyat - self.ortalama_alis_fiyati) * self.miktar
        return Decimal('0')
    
    def __str__(self):
        return f"{self.get_tip_display()} - {self.miktar}"
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Aylık gelir (TRY)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Tercihler
    notify_email = models.BooleanField(default=False)
    currency = models.CharField(max_length=10, default="TRY")

    # 🌙 Karanlık Mod
    dark_mode = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # kullanıcı kaydı güncellenince profil yoksa oluştur
        UserProfile.objects.get_or_create(user=instance)
