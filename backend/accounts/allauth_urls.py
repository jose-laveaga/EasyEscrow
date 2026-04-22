from django.urls import include, path

from allauth import app_settings as allauth_app_settings


urlpatterns = [
    path("", include("accounts.auth_urls")),
]

if allauth_app_settings.MFA_ENABLED:
    urlpatterns.append(path("2fa/", include("allauth.mfa.urls")))
