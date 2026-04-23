import uuid

from django.conf import settings
from django.db import models


class DocumentType(models.TextChoices):
    PURCHASE_AGREEMENT = "PURCHASE_AGREEMENT", "Purchase agreement"
    ESCROW_CONTRACT = "ESCROW_CONTRACT", "Escrow contract"
    GENERIC = "GENERIC", "Generic"


class DocumentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    AWAITING_SIGNATURES = "AWAITING_SIGNATURES", "Awaiting signatures"
    EXECUTED = "EXECUTED", "Executed"
    VOID = "VOID", "Void"


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
    executed_date = models.DateField(null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    inspection_days = models.PositiveSmallIntegerField(null=True, blank=True)
    payment_scheme_summary = models.TextField(blank=True)