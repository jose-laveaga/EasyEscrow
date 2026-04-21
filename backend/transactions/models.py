import uuid

from django.conf import settings
from django.db import models


class TransactionStatus(models.TextChoices):
    PENDING_INVITATIONS = "PENDING_INVITATIONS"
    PENDING_USER_INFORMATION = "PENDING_USER_INFORMATION"
    ACTIVE_WITHOUT_FUNDS = "ACTIVE_WITHOUT_FUNDS"
    ACTIVE_WITH_FUNDS = "ACTIVE_WITH_FUNDS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    IN_DISPUTE = "IN_DISPUTE"


class ParticipantRole(models.TextChoices):
    BROKER_PRIMARY = "BROKER_PRIMARY"
    BROKER_SECONDARY = "BROKER_SECONDARY"
    BUYER = "BUYER"
    SELLER = "SELLER"
    ESCROW_OFFICER = "ESCROW_OFFICER"


class TransactionType(models.TextChoices):
    SINGLE_BROKER_TRANSACTION = "SINGLE_BROKER_TRANSACTION"
    DOUBLE_BROKER_TRANSACTION = "MULTI_BROKER_TRANSACTION"
    DUE_DILIGENCE_TRANSACTION = "DUE_DILIGENCE_TRANSACTION"
    HIDDEN_DEFECTS_TRANSACTION = "HIDDEN_DEFECTS_TRANSACTION"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class InvitationRole(models.TextChoices):
    SECONDARY_BROKER = "SECONDARY_BROKER"
    SELLER = "SELLER"
    BUYER = "BUYER"

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, choices=TransactionType.choices)
    status = models.CharField(max_length=50, choices=TransactionStatus.choices, default=TransactionStatus.PENDING_INVITATIONS)

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    purchase_agreement_document = models.FileField(upload_to="transactions/purchase_agreements/", blank=True, null=True)
    inspection_days = models.PositiveSmallIntegerField(default=0)

    # property = ''
    earnest_deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions_created")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions_updated")

    def __str__(self):
        return f"{self.get_type_display()} {self.name}"

class TransactionParticipant(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    role = models.CharField(max_length=50, choices=ParticipantRole.choices)
    status = models.CharField(max_length=50, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invitations_sent")
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["transaction", "role"], name="unique_transaction_role")
        ]

    def __str__(self):
        return f"{self.transaction} - {self.user} - {self.role}"
