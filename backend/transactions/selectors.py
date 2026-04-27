from django.db.models import Prefetch, Q

from transactions.models import (
    Invitation,
    ParticipantStatus,
    Transaction,
    TransactionParticipant,
    TransactionStatus,
)
from transactions.services.invitation import expire_stale_pending_invitations


TERMINAL_TRANSACTION_STATUSES = {
    TransactionStatus.COMPLETED,
    TransactionStatus.CANCELLED,
    TransactionStatus.FAILED,
}


def _participant_queryset():
    return TransactionParticipant.objects.select_related("user").order_by("created_at")


def _invitation_queryset():
    return Invitation.objects.select_related(
        "sent_by_user",
        "target_user",
        "accepted_participant",
        "accepted_participant__user",
    ).order_by("created_at")


def get_transactions_visible_to_user(*, user):
    queryset = (
        Transaction.objects.select_related("property", "created_by")
        .prefetch_related(Prefetch("participants", queryset=_participant_queryset()))
        .filter(
            Q(created_by=user)
            | Q(
                participants__user=user,
                participants__status=ParticipantStatus.ACTIVE,
            )
        )
        .distinct()
    )
    transaction_ids = list(queryset.values_list("pk", flat=True))
    if transaction_ids:
        expire_stale_pending_invitations(transaction_ids=transaction_ids)
    return queryset


def get_transaction_visible_to_user(*, user, transaction_id):
    visible_transaction = get_transactions_visible_to_user(user=user).filter(pk=transaction_id).first()
    if visible_transaction is None:
        return None

    return (
        get_transactions_visible_to_user(user=user)
        .prefetch_related(Prefetch("invitations", queryset=_invitation_queryset()))
        .filter(pk=visible_transaction.pk)
        .first()
    )


def get_user_draft_and_active_transactions(*, user):
    visible_transactions = get_transactions_visible_to_user(user=user)
    return {
        "draft": visible_transactions.filter(status=TransactionStatus.DRAFT),
        "active": visible_transactions.exclude(
            status__in=TERMINAL_TRANSACTION_STATUSES | {TransactionStatus.DRAFT}
        ),
    }


def get_user_invitations(*, user):
    expire_stale_pending_invitations(user=user)
    base_queryset = _invitation_queryset()
    return {
        "sent": base_queryset.filter(sent_by_user=user),
        "received": base_queryset.filter(
            Q(target_user=user)
            | Q(target_user__isnull=True, target_email__iexact=user.email)
        ).distinct(),
    }
