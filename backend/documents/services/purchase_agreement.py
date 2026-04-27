from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from documents.models import (
    DocumentType,
    PurchaseAgreement,
    PurchaseAgreementExtractionStatus,
    TransactionDocument,
)
from transactions.models import ParticipantRole, ParticipantStatus, Transaction


BROKER_MANAGEMENT_ROLES = {
    ParticipantRole.PRIMARY_BROKER,
    ParticipantRole.COOPERATING_BROKER,
}


def user_can_manage_purchase_agreement(*, transaction: Transaction, user) -> bool:
    return transaction.participants.filter(
        user=user,
        status=ParticipantStatus.ACTIVE,
        role__in=BROKER_MANAGEMENT_ROLES,
    ).exists()


def _ensure_user_can_manage_purchase_agreement(*, transaction: Transaction, user) -> None:
    if not user_can_manage_purchase_agreement(transaction=transaction, user=user):
        raise ValidationError(
            {"uploaded_by_user": "Only active broker participants can manage the purchase agreement."}
        )


def _validate_pdf_file(file) -> None:
    filename = getattr(file, "name", "")
    content_type = getattr(file, "content_type", "")
    if not filename.lower().endswith(".pdf") and content_type != "application/pdf":
        raise ValidationError({"file": "Purchase agreements must be uploaded as PDF files."})


def get_latest_purchase_agreement(*, transaction: Transaction) -> PurchaseAgreement | None:
    return (
        PurchaseAgreement.objects.select_related(
            "document",
            "document__transaction",
            "document__uploaded_by_user",
            "confirmed_by_user",
        )
        .filter(document__transaction=transaction)
        .order_by("-document__version", "-document__created_at")
        .first()
    )


def transaction_has_purchase_agreement(*, transaction: Transaction) -> bool:
    return PurchaseAgreement.objects.filter(document__transaction=transaction).exists()


def _next_purchase_agreement_version(*, transaction: Transaction) -> int:
    latest_document = (
        TransactionDocument.objects.filter(
            transaction=transaction,
            document_type=DocumentType.PURCHASE_AGREEMENT,
        )
        .order_by("-version")
        .first()
    )
    if latest_document is None:
        return 1
    return latest_document.version + 1


def _empty_extraction_payload() -> dict:
    return {
        "purchase_price": None,
        "earnest_money_amount": None,
        "currency": "MXN",
        "seller_names": [],
        "seller_address": "",
        "buyer_names": [],
        "buyer_address": "",
        "property_address": "",
        "property_legal_description": "",
        "closing_date": None,
        "executed_date": None,
        "inspection_days": None,
        "payment_scheme_summary": "",
        "payment_milestones": [],
        "contingencies": "",
        "special_conditions": "",
        "disbursement_conditions": "",
        "disbursement_payees": [],
        "disbursement_amounts": [],
        "disbursement_purposes": [],
    }


@db_transaction.atomic
def upload_purchase_agreement(
    *,
    transaction: Transaction,
    uploaded_by_user,
    file,
    title: str = "Purchase agreement",
) -> PurchaseAgreement:
    transaction = Transaction.objects.select_for_update().get(pk=transaction.pk)
    _ensure_user_can_manage_purchase_agreement(transaction=transaction, user=uploaded_by_user)
    _validate_pdf_file(file)

    document = TransactionDocument(
        transaction=transaction,
        uploaded_by_user=uploaded_by_user,
        document_type=DocumentType.PURCHASE_AGREEMENT,
        title=(title or "Purchase agreement").strip(),
        file=file,
        version=_next_purchase_agreement_version(transaction=transaction),
        is_required=True,
    )
    document.full_clean()
    document.save()

    agreement = PurchaseAgreement(
        document=document,
        currency=transaction.currency or "MXN",
        raw_extraction=_empty_extraction_payload(),
        extraction_status=PurchaseAgreementExtractionStatus.REVIEW_REQUIRED,
    )
    agreement.full_clean()
    agreement.save()
    return agreement


@db_transaction.atomic
def confirm_purchase_agreement_terms(
    *,
    purchase_agreement: PurchaseAgreement,
    confirmed_by_user,
    **terms,
) -> PurchaseAgreement:
    purchase_agreement = (
        PurchaseAgreement.objects.select_for_update()
        .select_related("document", "document__transaction")
        .get(pk=purchase_agreement.pk)
    )
    transaction = purchase_agreement.document.transaction
    _ensure_user_can_manage_purchase_agreement(transaction=transaction, user=confirmed_by_user)

    term_fields = (
        "purchase_price",
        "earnest_money_amount",
        "currency",
        "seller_names",
        "seller_address",
        "buyer_names",
        "buyer_address",
        "property_address",
        "property_legal_description",
        "executed_date",
        "closing_date",
        "inspection_days",
        "payment_scheme_summary",
        "payment_milestones",
        "contingencies",
        "special_conditions",
        "disbursement_conditions",
        "disbursement_payees",
        "disbursement_amounts",
        "disbursement_purposes",
        "gf_number",
        "escrow_agent",
        "escrow_fee",
        "escrow_bank_account",
        "wire_reference",
        "payee_wire_information",
        "broker_commission_allocations",
    )
    for field_name in term_fields:
        if field_name not in terms:
            continue
        value = terms[field_name]
        if isinstance(value, str):
            value = value.strip()
            if field_name == "currency":
                value = (value or "MXN").upper()
        setattr(purchase_agreement, field_name, value)

    purchase_agreement.extraction_status = PurchaseAgreementExtractionStatus.CONFIRMED
    purchase_agreement.confirmed_by_user = confirmed_by_user
    purchase_agreement.confirmed_at = timezone.now()
    purchase_agreement.full_clean()
    purchase_agreement.save()

    if purchase_agreement.purchase_price is not None:
        transaction.purchase_price = purchase_agreement.purchase_price
    if purchase_agreement.earnest_money_amount is not None:
        transaction.earnest_money_amount = purchase_agreement.earnest_money_amount
    if purchase_agreement.currency:
        transaction.currency = purchase_agreement.currency
    if purchase_agreement.closing_date is not None:
        transaction.closing_date_target = purchase_agreement.closing_date
    transaction.save(
        update_fields=[
            "purchase_price",
            "earnest_money_amount",
            "currency",
            "closing_date_target",
            "updated_at",
        ]
    )

    return purchase_agreement
