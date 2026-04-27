from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.services.broker import user_can_create_transactions
from transactions.models import (
    InvitationStatus,
    ParticipantRole,
    ParticipantStatus,
    Property,
    Transaction,
    TransactionStatus,
)


SYNCABLE_SETUP_STATUSES = {
    TransactionStatus.DRAFT,
    TransactionStatus.PENDING_INVITATIONS,
    TransactionStatus.PARTIES_CONFIRMED,
}
REQUIRED_SETUP_PARTY_ROLES = {
    ParticipantRole.BUYER,
    ParticipantRole.SELLER,
}


def _build_reference_code() -> str:
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


def _generate_reference_code() -> str:
    for _ in range(5):
        reference_code = _build_reference_code()
        if not Transaction.objects.filter(reference_code=reference_code).exists():
            return reference_code
    raise ValidationError({"reference_code": "Could not generate a unique transaction reference code."})


def _normalize_property_data(property_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if property_data is None:
        return None

    normalized_data: dict[str, Any] = {}
    for field_name, value in property_data.items():
        normalized_data[field_name] = value.strip() if isinstance(value, str) else value

    missing_fields = [
        field_name
        for field_name in ("address_line1", "city", "state", "postal_code")
        if not normalized_data.get(field_name)
    ]
    if missing_fields:
        raise ValidationError(
            {
                field_name: "This field is required when property_data is provided."
                for field_name in missing_fields
            }
        )

    if not normalized_data.get("country"):
        normalized_data["country"] = "Mexico"

    return normalized_data


@db_transaction.atomic
def create_transaction(
    *,
    created_by,
    title,
    description="",
    transaction_type,
    property_data=None,
    purchase_price=None,
    earnest_money_amount=None,
    currency="MXN",
    closing_date_target=None,
) -> Transaction:
    if not user_can_create_transactions(created_by):
        raise ValidationError({"created_by": "Only approved active brokers can create transactions."})

    normalized_property_data = _normalize_property_data(property_data)
    property_instance = None
    if normalized_property_data is not None:
        property_instance = Property(**normalized_property_data)
        property_instance.full_clean()
        property_instance.save()

    transaction = Transaction(
        reference_code=_generate_reference_code(),
        transaction_type=transaction_type,
        status=TransactionStatus.DRAFT,
        title=title.strip(),
        description=description.strip(),
        property=property_instance,
        created_by=created_by,
        purchase_price=purchase_price,
        earnest_money_amount=earnest_money_amount,
        currency=(currency or "MXN").strip().upper(),
        closing_date_target=closing_date_target,
    )
    transaction.full_clean()
    transaction.save()

    from .participant import add_participant

    add_participant(
        transaction=transaction,
        user=created_by,
        role=ParticipantRole.PRIMARY_BROKER,
        status=ParticipantStatus.ACTIVE,
    )

    transaction.refresh_from_db()
    return transaction


def sync_transaction_setup_status(*, transaction: Transaction) -> Transaction:
    if transaction.status not in SYNCABLE_SETUP_STATUSES:
        return transaction

    from .invitation import expire_stale_pending_invitations

    expire_stale_pending_invitations(transaction_ids=[transaction.pk], sync_transactions=False)

    active_roles = set(
        transaction.participants.filter(status=ParticipantStatus.ACTIVE).values_list("role", flat=True)
    )
    missing_roles = REQUIRED_SETUP_PARTY_ROLES - active_roles

    if not missing_roles:
        new_status = TransactionStatus.PARTIES_CONFIRMED
    else:
        now = timezone.now()
        has_pending_required_invitations = transaction.invitations.filter(
            status=InvitationStatus.PENDING,
            intended_role__in=missing_roles,
            expires_at__gt=now,
        ).exists()
        new_status = (
            TransactionStatus.PENDING_INVITATIONS
            if has_pending_required_invitations
            else TransactionStatus.DRAFT
        )

    if transaction.status != new_status:
        transaction.status = new_status
        transaction.save(update_fields=["status", "updated_at"])

    return transaction
