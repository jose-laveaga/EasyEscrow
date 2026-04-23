from django.urls import path

from transactions.views import (
    InvitationAcceptView,
    InvitationRejectView,
    TransactionDetailView,
    TransactionInvitationCreateView,
    TransactionListCreateView,
    TransactionParticipantsView,
)


urlpatterns = [
    path("api/transactions/", TransactionListCreateView.as_view(), name="transaction-list-create"),
    path("api/transactions/<uuid:pk>/", TransactionDetailView.as_view(), name="transaction-detail"),
    path(
        "api/transactions/<uuid:pk>/participants/",
        TransactionParticipantsView.as_view(),
        name="transaction-participants",
    ),
    path(
        "api/transactions/<uuid:pk>/invitations/",
        TransactionInvitationCreateView.as_view(),
        name="transaction-invitations",
    ),
    path("api/invitations/<uuid:pk>/accept/", InvitationAcceptView.as_view(), name="invitation-accept"),
    path("api/invitations/<uuid:pk>/reject/", InvitationRejectView.as_view(), name="invitation-reject"),
]
