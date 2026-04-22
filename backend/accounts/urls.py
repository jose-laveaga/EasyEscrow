from django.urls import path
from accounts.views import (
    BrokerApplicationSubmitView,
    BrokerApplicationView,
    BrokerProfileView,
    IdentityVerificationSubmitView,
    IdentityVerificationView,
    index,
)

urlpatterns = [
    path(
        "identity-verification/",
        IdentityVerificationView.as_view(),
        name="identity-verification",
    ),
    path(
        "identity-verification/submit/",
        IdentityVerificationSubmitView.as_view(),
        name="identity-verification-submit",
    ),
    path("broker-profile/", BrokerProfileView.as_view(), name="broker-profile"),
    path("broker-application/", BrokerApplicationView.as_view(), name="broker-application"),
    path(
        "broker-application/submit/",
        BrokerApplicationSubmitView.as_view(),
        name="broker-application-submit",
    ),
    path("", index, name="index"),
]
