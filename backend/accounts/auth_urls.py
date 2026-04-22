from django.conf import settings
from django.urls import path

from allauth import app_settings as allauth_app_settings
from allauth.account import app_settings

from accounts.auth_views import (
    AccountInactiveAPIView,
    CompletePasswordResetAPIView,
    ConfirmEmailAPIView,
    ConfirmLoginCodeAPIView,
    ConfirmPasswordResetCodeAPIView,
    EmailAPIView,
    LoginAPIView,
    LogoutAPIView,
    PasswordChangeAPIView,
    PasswordResetAPIView,
    PasswordResetDoneAPIView,
    PasswordSetAPIView,
    ReauthenticateAPIView,
    SignupAPIView,
)


urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="account_login"),
    path("logout/", LogoutAPIView.as_view(), name="account_logout"),
    path("inactive/", AccountInactiveAPIView.as_view(), name="account_inactive"),
]

if not allauth_app_settings.SOCIALACCOUNT_ONLY:
    urlpatterns.extend(
        [
            path("signup/", SignupAPIView.as_view(), name="account_signup"),
            path(
                "reauthenticate/",
                ReauthenticateAPIView.as_view(),
                name="account_reauthenticate",
            ),
            path("email/", EmailAPIView.as_view(), name="account_email"),
            path(
                "confirm-email/",
                ConfirmEmailAPIView.as_view(),
                name="account_email_verification_sent",
            ),
            path(
                "password/change/",
                PasswordChangeAPIView.as_view(),
                name="account_change_password",
            ),
            path(
                "password/set/",
                PasswordSetAPIView.as_view(),
                name="account_set_password",
            ),
            path(
                "password/reset/",
                PasswordResetAPIView.as_view(),
                name="account_reset_password",
            ),
            path(
                "login/code/confirm/",
                ConfirmLoginCodeAPIView.as_view(),
                name="account_confirm_login_code",
            ),
        ]
    )
    if app_settings.PASSWORD_RESET_BY_CODE_ENABLED:
        urlpatterns.extend(
            [
                path(
                    "password/reset/confirm/",
                    ConfirmPasswordResetCodeAPIView.as_view(),
                    name="account_confirm_password_reset_code",
                ),
                path(
                    "password/reset/complete/",
                    CompletePasswordResetAPIView.as_view(),
                    name="account_complete_password_reset",
                ),
                path(
                    "password/reset/done/",
                    PasswordResetDoneAPIView.as_view(),
                    name="account_password_reset_completed",
                ),
            ]
        )
    if getattr(settings, "MFA_PASSKEY_SIGNUP_ENABLED", False):
        # Passkey signup stays on the stock MFA/allauth surface for now.
        pass
