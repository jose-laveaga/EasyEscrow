from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from transactions.models import (
    BrokerCommissionAgreement,
    CommissionAgreementStatus,
    CommissionBasis,
    ParticipantRole,
    ParticipantStatus,
    Transaction,
    TransactionType,
)


def _user_has_role(*, transaction: Transaction, user, role: str) -> bool:
    return transaction.participants.filter(
        user=user,
        role=role,
        status=ParticipantStatus.ACTIVE,
    ).exists()


def _ensure_double_broker_transaction(*, transaction: Transaction) -> None:
    if transaction.transaction_type != TransactionType.DOUBLE_BROKER:
        raise ValidationError(
            {"transaction_type": "Commission agreements are only required for double-broker transactions."}
        )


def _ensure_primary_broker(*, transaction: Transaction, user) -> None:
    if not _user_has_role(transaction=transaction, user=user, role=ParticipantRole.PRIMARY_BROKER):
        raise ValidationError({"proposed_by_user": "Only the primary broker can propose commission terms."})


def _ensure_cooperating_broker(*, transaction: Transaction, user) -> None:
    if not _user_has_role(transaction=transaction, user=user, role=ParticipantRole.COOPERATING_BROKER):
        raise ValidationError(
            {"accepted_by_user": "Only the active cooperating broker can accept commission terms."}
        )


def _ensure_cooperating_broker_exists(*, transaction: Transaction) -> None:
    if not transaction.participants.filter(
        role=ParticipantRole.COOPERATING_BROKER,
        status=ParticipantStatus.ACTIVE,
    ).exists():
        raise ValidationError(
            {"cooperating_broker": "The cooperating broker must accept the transaction before commission terms are proposed."}
        )


def _validate_commission_terms(*, commission_basis, total_commission_amount, total_commission_percentage):
    if commission_basis == CommissionBasis.FIXED_AMOUNT and total_commission_amount is None:
        raise ValidationError({"total_commission_amount": "Provide a total commission amount for fixed commission terms."})
    if commission_basis == CommissionBasis.PERCENT_OF_PURCHASE_PRICE and total_commission_percentage is None:
        raise ValidationError(
            {
                "total_commission_percentage": (
                    "Provide a total commission percentage for percentage-based commission terms."
                )
            }
        )


def get_commission_agreement(*, transaction: Transaction) -> BrokerCommissionAgreement | None:
    return (
        BrokerCommissionAgreement.objects.select_related(
            "transaction",
            "proposed_by_user",
            "accepted_by_user",
        )
        .filter(transaction=transaction)
        .first()
    )


def _serialize_decimal(value):
    return str(value) if value is not None else None


def _build_broker_commission_allocations(
    *,
    transaction: Transaction,
    agreement: BrokerCommissionAgreement,
) -> list[dict]:
    primary_participant = (
        transaction.participants.select_related("user")
        .filter(role=ParticipantRole.PRIMARY_BROKER, status=ParticipantStatus.ACTIVE)
        .first()
    )
    cooperating_participant = (
        transaction.participants.select_related("user")
        .filter(role=ParticipantRole.COOPERATING_BROKER, status=ParticipantStatus.ACTIVE)
        .first()
    )
    return [
        {
            "role": ParticipantRole.PRIMARY_BROKER,
            "broker_email": primary_participant.user.email if primary_participant else "",
            "share_amount": _serialize_decimal(agreement.primary_broker_share_amount),
            "share_percentage": _serialize_decimal(agreement.primary_broker_share_percentage),
            "payment_source": agreement.payment_source,
            "payable_event": agreement.payable_event,
        },
        {
            "role": ParticipantRole.COOPERATING_BROKER,
            "broker_email": cooperating_participant.user.email if cooperating_participant else "",
            "share_amount": _serialize_decimal(agreement.cooperating_broker_share_amount),
            "share_percentage": _serialize_decimal(agreement.cooperating_broker_share_percentage),
            "payment_source": agreement.payment_source,
            "payable_event": agreement.payable_event,
        },
    ]


def _sync_accepted_commission_to_purchase_agreement(
    *,
    transaction: Transaction,
    agreement: BrokerCommissionAgreement,
) -> None:
    from documents.services.purchase_agreement import get_latest_purchase_agreement

    purchase_agreement = get_latest_purchase_agreement(transaction=transaction)
    if purchase_agreement is None:
        return

    purchase_agreement.broker_commission_allocations = _build_broker_commission_allocations(
        transaction=transaction,
        agreement=agreement,
    )
    purchase_agreement.save(update_fields=["broker_commission_allocations", "updated_at"])


@db_transaction.atomic
def propose_commission_agreement(
    *,
    transaction: Transaction,
    proposed_by_user,
    commission_basis,
    total_commission_amount=None,
    total_commission_percentage=None,
    currency="MXN",
    primary_broker_share_amount=None,
    primary_broker_share_percentage=None,
    cooperating_broker_share_amount=None,
    cooperating_broker_share_percentage=None,
    payment_source=None,
    payable_event=None,
    notes="",
) -> BrokerCommissionAgreement:
    transaction = Transaction.objects.select_for_update().get(pk=transaction.pk)
    _ensure_double_broker_transaction(transaction=transaction)
    _ensure_primary_broker(transaction=transaction, user=proposed_by_user)
    _ensure_cooperating_broker_exists(transaction=transaction)
    _validate_commission_terms(
        commission_basis=commission_basis,
        total_commission_amount=total_commission_amount,
        total_commission_percentage=total_commission_percentage,
    )

    agreement, _created = BrokerCommissionAgreement.objects.select_for_update().get_or_create(
        transaction=transaction,
        defaults={
            "commission_basis": commission_basis,
            "proposed_by_user": proposed_by_user,
        },
    )
    if agreement.status == CommissionAgreementStatus.ACCEPTED:
        raise ValidationError({"commission_agreement": "Accepted commission terms cannot be changed."})

    agreement.status = CommissionAgreementStatus.PROPOSED
    agreement.commission_basis = commission_basis
    agreement.total_commission_amount = total_commission_amount
    agreement.total_commission_percentage = total_commission_percentage
    agreement.currency = (currency or "MXN").strip().upper()
    agreement.primary_broker_share_amount = primary_broker_share_amount
    agreement.primary_broker_share_percentage = primary_broker_share_percentage
    agreement.cooperating_broker_share_amount = cooperating_broker_share_amount
    agreement.cooperating_broker_share_percentage = cooperating_broker_share_percentage
    if payment_source is not None:
        agreement.payment_source = payment_source
    if payable_event is not None:
        agreement.payable_event = payable_event
    agreement.notes = notes.strip() if isinstance(notes, str) else notes
    agreement.proposed_by_user = proposed_by_user
    agreement.accepted_by_user = None
    agreement.accepted_at = None
    agreement.full_clean()
    agreement.save()
    return agreement


@db_transaction.atomic
def accept_commission_agreement(
    *,
    transaction: Transaction,
    accepted_by_user,
) -> BrokerCommissionAgreement:
    transaction = Transaction.objects.select_for_update().get(pk=transaction.pk)
    _ensure_double_broker_transaction(transaction=transaction)
    _ensure_cooperating_broker(transaction=transaction, user=accepted_by_user)

    try:
        agreement = BrokerCommissionAgreement.objects.select_for_update().get(transaction=transaction)
    except BrokerCommissionAgreement.DoesNotExist as exc:
        raise ValidationError({"commission_agreement": "Commission terms have not been proposed yet."}) from exc

    if agreement.status != CommissionAgreementStatus.PROPOSED:
        raise ValidationError({"commission_agreement": "Only proposed commission terms can be accepted."})

    agreement.status = CommissionAgreementStatus.ACCEPTED
    agreement.accepted_by_user = accepted_by_user
    agreement.accepted_at = timezone.now()
    agreement.full_clean()
    agreement.save()
    _sync_accepted_commission_to_purchase_agreement(
        transaction=transaction,
        agreement=agreement,
    )
    return agreement
