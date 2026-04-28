from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils.dateparse import parse_date
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


def transaction_has_confirmed_purchase_agreement_terms(*, transaction: Transaction) -> bool:
    return PurchaseAgreement.objects.filter(
        document__transaction=transaction,
        extraction_status=PurchaseAgreementExtractionStatus.CONFIRMED,
    ).exists()


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


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _join_text_list(value) -> str:
    return "\n".join(str(item).strip() for item in _as_list(value) if str(item).strip())


def _clean_text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _decimal_or_none(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _date_or_none(value):
    if value in (None, ""):
        return None
    return parse_date(str(value))


def _map_extraction_to_terms(raw_extraction: dict) -> dict:
    parties = raw_extraction.get("parties") or {}
    property_data = raw_extraction.get("property") or {}
    financial_terms = raw_extraction.get("financial_terms") or {}
    dates = raw_extraction.get("dates") or {}
    conditions = raw_extraction.get("conditions") or {}
    disbursement = raw_extraction.get("disbursement_instructions") or {}

    earnest_money_amount = financial_terms.get("earnest_money_amount")
    if earnest_money_amount is None:
        earnest_money_amount = financial_terms.get("escrow_deposit_amount")

    return {
        "purchase_price": _decimal_or_none(financial_terms.get("purchase_price")),
        "earnest_money_amount": _decimal_or_none(earnest_money_amount),
        "currency": (_clean_text(financial_terms.get("currency")) or "MXN").upper(),
        "seller_names": _as_list(parties.get("seller_names")),
        "seller_address": _clean_text(parties.get("seller_address")),
        "buyer_names": _as_list(parties.get("buyer_names")),
        "buyer_address": _clean_text(parties.get("buyer_address")),
        "property_address": _clean_text(property_data.get("property_address")),
        "property_legal_description": _clean_text(property_data.get("property_legal_description")),
        "executed_date": _date_or_none(dates.get("executed_date") or dates.get("agreement_date")),
        "closing_date": _date_or_none(dates.get("closing_date")),
        "payment_scheme_summary": _clean_text(financial_terms.get("payment_scheme_summary")),
        "payment_milestones": _as_list(financial_terms.get("payment_milestones")),
        "contingencies": _join_text_list(conditions.get("contingencies")),
        "special_conditions": _join_text_list(conditions.get("special_conditions")),
        "disbursement_conditions": _join_text_list(conditions.get("disbursement_conditions")),
        "disbursement_payees": _as_list(disbursement.get("payees")),
        "disbursement_amounts": _as_list(disbursement.get("amounts")),
        "disbursement_purposes": _as_list(disbursement.get("purposes")),
        "payee_wire_information": _as_list(disbursement.get("wire_information")),
    }


def _apply_extracted_terms(*, purchase_agreement: PurchaseAgreement, raw_extraction: dict) -> None:
    for field_name, value in _map_extraction_to_terms(raw_extraction).items():
        if value is None:
            continue
        setattr(purchase_agreement, field_name, value)


def _extraction_enabled() -> bool:
    return getattr(settings, "OPENAI_PURCHASE_AGREEMENT_EXTRACTION_ENABLED", True)


@db_transaction.atomic
def _create_purchase_agreement_record(
    *,
    transaction: Transaction,
    uploaded_by_user,
    file,
    title: str,
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
        extraction_status=(
            PurchaseAgreementExtractionStatus.PENDING
            if _extraction_enabled()
            else PurchaseAgreementExtractionStatus.REVIEW_REQUIRED
        ),
    )
    agreement.full_clean()
    agreement.save()
    return agreement


def upload_purchase_agreement(
    *,
    transaction: Transaction,
    uploaded_by_user,
    file,
    title: str = "Purchase agreement",
) -> PurchaseAgreement:
    agreement = _create_purchase_agreement_record(
        transaction=transaction,
        uploaded_by_user=uploaded_by_user,
        file=file,
        title=title,
    )
    if _extraction_enabled():
        agreement = run_purchase_agreement_extraction(purchase_agreement=agreement)
    return agreement


def run_purchase_agreement_extraction(*, purchase_agreement: PurchaseAgreement) -> PurchaseAgreement:
    from documents.services.open_ai_purchase_agreement_review import (
        extract_purchase_agreement_fields,
        upload_file_to_openai,
    )

    purchase_agreement = PurchaseAgreement.objects.select_related("document").get(
        pk=purchase_agreement.pk,
    )
    purchase_agreement.extraction_status = PurchaseAgreementExtractionStatus.PENDING
    purchase_agreement.extraction_error = ""
    purchase_agreement.save(update_fields=["extraction_status", "extraction_error", "updated_at"])

    try:
        openai_file_id = upload_file_to_openai(purchase_agreement.document.file.path)
        raw_extraction = extract_purchase_agreement_fields(openai_file_id)
    except Exception as exc:
        purchase_agreement.extraction_status = PurchaseAgreementExtractionStatus.FAILED
        purchase_agreement.extraction_error = str(exc)
        purchase_agreement.save(update_fields=["extraction_status", "extraction_error", "updated_at"])
        return purchase_agreement

    purchase_agreement.raw_extraction = raw_extraction
    if not raw_extraction.get("is_valid_purchase_agreement"):
        missing_fields = raw_extraction.get("missing_required_fields") or []
        purchase_agreement.extraction_status = PurchaseAgreementExtractionStatus.FAILED
        purchase_agreement.extraction_error = (
            "Missing required fields: " + ", ".join(missing_fields)
            if missing_fields
            else "OpenAI did not classify this document as a valid purchase agreement."
        )
    else:
        _apply_extracted_terms(
            purchase_agreement=purchase_agreement,
            raw_extraction=raw_extraction,
        )
        purchase_agreement.extraction_status = PurchaseAgreementExtractionStatus.REVIEW_REQUIRED
        purchase_agreement.extraction_error = ""

    purchase_agreement.full_clean()
    purchase_agreement.save()
    return purchase_agreement


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
