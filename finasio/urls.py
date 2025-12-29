from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path(
        "accounts/password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="finans_takip/password_change_form.html",
            success_url="/accounts/password_change/done/"
        ),
        name="password_change",
    ),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="finans_takip/password_change_done.html"
        ),
        name="password_change_done",
    ),

    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('finans_takip.urls')),
]
