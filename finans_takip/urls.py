# finans_takip/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('signup/', views.signup_view, name='signup'),
    path('export/', views.export_view, name='export'),
    path('islem/<int:islem_id>/sil/', views.islem_sil_view, name='islem_sil'),
    path('harcama-ekle/', views.harcama_ekle_view, name='harcama_ekle'),
    path('raporlar/', views.raporlar_view, name='raporlar'),
    path("api/fx-rates/", views.fx_rates_api, name="fx_rates_api"),
    path("ayarlar/", views.ayarlar_view, name="ayarlar"),
    path("ayarlar/tema-kaydet/", views.tema_kaydet_view, name="tema_kaydet"),

]