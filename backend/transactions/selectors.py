from django.db.models import Prefetch, Q

from transactions.models import Invitation, ParticipantStatus, Transaction, TransactionParticipant


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
    return (
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


def get_transaction_visible_to_user(*, user, transaction_id):
    return (
        get_transactions_visible_to_user(user=user)
        .prefetch_related(Prefetch("invitations", queryset=_invitation_queryset()))
        .filter(pk=transaction_id)
        .first()
    )
