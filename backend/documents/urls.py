from django.urls import path

from documents.views import PurchaseAgreementConfirmView, TransactionPurchaseAgreementView


urlpatterns = [
    path(
        "api/transactions/<uuid:pk>/purchase-agreement/",
        TransactionPurchaseAgreementView.as_view(),
        name="transaction-purchase-agreement",
    ),
    path(
        "api/transactions/<uuid:pk>/purchase-agreement/confirm/",
        PurchaseAgreementConfirmView.as_view(),
        name="transaction-purchase-agreement-confirm",
    ),
]
