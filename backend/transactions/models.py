import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class TransactionType(models.TextChoices):
    STANDARD = "STANDARD", "Standard"
    DOUBLE_BROKER = "DOUBLE_BROKER", "Double broker"


class TransactionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_INVITATIONS = "PENDING_INVITATIONS", "Pending invitations"
    PARTIES_CONFIRMED = "PARTIES_CONFIRMED", "Parties confirmed"
    KYC_IN_PROGRESS = "KYC_IN_PROGRESS", "KYC in progress"
    AWAITING_SIGNATURES = "AWAITING_SIGNATURES", "Awaiting signatures"
    AWAITING_DEPOSIT = "AWAITING_DEPOSIT", "Awaiting deposit"
    FUNDED = "FUNDED", "Funded"
    CLOSING_PENDING = "CLOSING_PENDING", "Closing pending"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    FAILED = "FAILED", "Failed"


class ParticipantRole(models.TextChoices):
    PRIMARY_BROKER = "PRIMARY_BROKER", "Primary broker"
    COOPERATING_BROKER = "COOPERATING_BROKER", "Cooperating broker"
    BUYER = "BUYER", "Buyer"
    SELLER = "SELLER", "Seller"
    ESCROW_OFFICER = "ESCROW_OFFICER", "Escrow officer"


class ParticipantStatus(models.TextChoices):
    INVITED = "INVITED", "Invited"
    ACTIVE = "ACTIVE", "Active"
    LEFT = "LEFT", "Left"
    REMOVED = "REMOVED", "Removed"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"
    REVOKED = "REVOKED", "Revoked"


class InvitationDeliveryMethod(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    LINK = "LINK", "Link"
    QR = "QR", "QR"


class Property(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=120, default="Mexico")
    parcel_number = models.CharField(max_length=120, blank=True)
    legal_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.address_line1}, {self.city}, {self.state}"


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_code = models.CharField(max_length=32, unique=True)
    transaction_type = models.CharField(
        max_length=40,
        choices=TransactionType.choices,
        default=TransactionType.STANDARD,
    )
    status = models.CharField(
        max_length=40,
        choices=TransactionStatus.choices,
        default=TransactionStatus.DRAFT,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transactions_created",
    )
    purchase_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    earnest_money_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=10, default="MXN")
    closing_date_target = models.DateField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    funded_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.reference_code} - {self.title}"


class TransactionParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transaction_participations",
    )
    role = models.CharField(max_length=40, choices=ParticipantRole.choices)
    status = models.CharField(
        max_length=20,
        choices=ParticipantStatus.choices,
        default=ParticipantStatus.ACTIVE,
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "user"],
                name="uniq_transaction_user",
            ),
            models.UniqueConstraint(
                fields=["transaction", "role"],
                condition=Q(status=ParticipantStatus.ACTIVE)
                & Q(
                    role__in=[
                        ParticipantRole.BUYER,
                        ParticipantRole.SELLER,
                        ParticipantRole.PRIMARY_BROKER,
                        ParticipantRole.COOPERATING_BROKER,
                        ParticipantRole.ESCROW_OFFICER,
                    ]
                ),
                name="uniq_active_single_role_per_transaction",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.transaction.reference_code} - {self.user} - {self.role}"


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    sent_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_transaction_invitations",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_transaction_invitations",
        null=True,
        blank=True,
    )
    target_email = models.EmailField(blank=True)
    intended_role = models.CharField(max_length=40, choices=ParticipantRole.choices)
    delivery_method = models.CharField(
        max_length=20,
        choices=InvitationDeliveryMethod.choices,
        default=InvitationDeliveryMethod.EMAIL,
    )
    token = models.CharField(max_length=128, unique=True)
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    accepted_participant = models.ForeignKey(
        "TransactionParticipant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_invitations",
    )
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(target_user__isnull=False) | ~Q(target_email=""),
                name="invitation_requires_target_user_or_email",
            ),
            models.UniqueConstraint(
                fields=["transaction", "target_user"],
                condition=Q(status=InvitationStatus.PENDING) & Q(target_user__isnull=False),
                name="uniq_pending_invitation_per_target_user",
            ),
            models.UniqueConstraint(
                "transaction",
                Lower("target_email"),
                condition=Q(status=InvitationStatus.PENDING) & ~Q(target_email=""),
                name="uniq_pending_invitation_per_target_email",
            ),
            models.UniqueConstraint(
                fields=["transaction", "intended_role"],
                condition=Q(status=InvitationStatus.PENDING)
                & Q(
                    intended_role__in=[
                        ParticipantRole.BUYER,
                        ParticipantRole.SELLER,
                        ParticipantRole.PRIMARY_BROKER,
                        ParticipantRole.COOPERATING_BROKER,
                        ParticipantRole.ESCROW_OFFICER,
                    ]
                ),
                name="uniq_pending_invitation_per_single_role",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.transaction.reference_code} - {self.intended_role} - {self.status}"
