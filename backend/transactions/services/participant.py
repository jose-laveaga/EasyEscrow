from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.services.broker import user_can_create_transactions
from transactions.models import (
    ParticipantRole,
    ParticipantStatus,
    Transaction,
    TransactionParticipant,
    TransactionType,
)


SINGLE_OCCUPANT_ROLES = {
    ParticipantRole.PRIMARY_BROKER,
    ParticipantRole.BUYER,
    ParticipantRole.SELLER,
    ParticipantRole.ESCROW_OFFICER,
}
BROKER_ROLES = {
    ParticipantRole.PRIMARY_BROKER,
    ParticipantRole.COOPERATING_BROKER,
}


def validate_participant_role_assignment(*, transaction: Transaction, user, role) -> None:
    if TransactionParticipant.objects.filter(transaction=transaction, user=user).exists():
        raise ValidationError({"user": "This user is already a participant in this transaction."})

    if role == ParticipantRole.COOPERATING_BROKER:
        if transaction.transaction_type != TransactionType.DOUBLE_BROKER:
            raise ValidationError({"role": "STANDARD transactions cannot include a cooperating broker."})
        if TransactionParticipant.objects.filter(
            transaction=transaction,
            role=ParticipantRole.COOPERATING_BROKER,
            status=ParticipantStatus.ACTIVE,
        ).exists():
            raise ValidationError({"role": "This transaction already has a cooperating broker."})

    if role in BROKER_ROLES and not user_can_create_transactions(user):
        raise ValidationError(
            {"user": "Broker participants must have an active approved broker profile."}
        )

    if role in SINGLE_OCCUPANT_ROLES and TransactionParticipant.objects.filter(
        transaction=transaction,
        role=role,
        status=ParticipantStatus.ACTIVE,
    ).exists():
        raise ValidationError({"role": "This role is already assigned in this transaction."})


@db_transaction.atomic
def add_participant(
    *,
    transaction: Transaction,
    user,
    role,
    status=ParticipantStatus.ACTIVE,
) -> TransactionParticipant:
    validate_participant_role_assignment(
        transaction=transaction,
        user=user,
        role=role,
    )

    participant = TransactionParticipant(
        transaction=transaction,
        user=user,
        role=role,
        status=status,
        joined_at=timezone.now() if status == ParticipantStatus.ACTIVE else None,
        left_at=timezone.now() if status == ParticipantStatus.LEFT else None,
    )
    participant.full_clean()
    participant.save()

    from .transaction import sync_transaction_setup_status

    sync_transaction_setup_status(transaction=transaction)
    return participant
