import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentType(models.TextChoices):
    PURCHASE_AGREEMENT = "PURCHASE_AGREEMENT", "Purchase agreement"
    ESCROW_CONTRACT = "ESCROW_CONTRACT", "Escrow contract"
    GENERIC = "GENERIC", "Generic"


class DocumentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    AWAITING_SIGNATURES = "AWAITING_SIGNATURES", "Awaiting signatures"
    EXECUTED = "EXECUTED", "Executed"
    VOID = "VOID", "Void"


class PurchaseAgreementExtractionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    REVIEW_REQUIRED = "REVIEW_REQUIRED", "Review required"
    CONFIRMED = "CONFIRMED", "Confirmed"
    FAILED = "FAILED", "Failed"


class TransactionDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    uploaded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_transaction_documents",
    )

    document_type = models.CharField(max_length=40, choices=DocumentType.choices)
    status = models.CharField(
        max_length=30,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
    )

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="transactions/documents/")
    version = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PurchaseAgreement(models.Model):
    document = models.OneToOneField(
        TransactionDocument,
        on_delete=models.CASCADE,
        related_name="purchase_agreement",
    )
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    earnest_money_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="MXN")
    seller_names = models.JSONField(default=list, blank=True)
    seller_address = models.TextField(blank=True)
    buyer_names = models.JSONField(default=list, blank=True)
    buyer_address = models.TextField(blank=True)
    property_address = models.TextField(blank=True)
    property_legal_description = models.TextField(blank=True)
    executed_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    inspection_days = models.PositiveSmallIntegerField(null=True, blank=True)
    payment_scheme_summary = models.TextField(blank=True)
    payment_milestones = models.JSONField(default=list, blank=True)
    contingencies = models.TextField(blank=True)
    special_conditions = models.TextField(blank=True)
    disbursement_conditions = models.TextField(blank=True)
    disbursement_payees = models.JSONField(default=list, blank=True)
    disbursement_amounts = models.JSONField(default=list, blank=True)
    disbursement_purposes = models.JSONField(default=list, blank=True)
    gf_number = models.CharField(max_length=120, blank=True)
    escrow_agent = models.CharField(max_length=255, blank=True)
    escrow_fee = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    escrow_bank_account = models.TextField(blank=True)
    wire_reference = models.CharField(max_length=255, blank=True)
    payee_wire_information = models.JSONField(default=list, blank=True)
    broker_commission_allocations = models.JSONField(default=list, blank=True)
    raw_extraction = models.JSONField(default=dict, blank=True)
    extraction_status = models.CharField(
        max_length=30,
        choices=PurchaseAgreementExtractionStatus.choices,
        default=PurchaseAgreementExtractionStatus.PENDING,
    )
    extraction_error = models.TextField(blank=True)
    confirmed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_purchase_agreements",
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
