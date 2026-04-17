from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from ..validators import rfc_validator
import uuid


class BrokerApplicationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    UNDER_REVIEW = "under_review", "Under review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    NEEDS_INFO = "needs_info", "Needs info"


class BrokerType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual"
    COMPANY_REPRESENTATIVE = "company_representative", "Company representative"


class BrokerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broker_profile",
    )

    broker_type = models.CharField(
        max_length=30,
        choices=BrokerType.choices,
    )

    application_status = models.CharField(
        max_length=20,
        choices=BrokerApplicationStatus.choices,
        default=BrokerApplicationStatus.DRAFT,
    )
    review_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    accepted_broker_declaration_at = models.DateTimeField(null=True, blank=True)

    can_create_transactions = models.BooleanField(default=False)
    is_active_broker = models.BooleanField(default=False)

    brokerage_name = models.CharField(max_length=255, blank=True)
    years_of_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    primary_market = models.CharField(max_length=255, blank=True)
    operating_state = models.CharField(max_length=100, blank=True)
    license_or_registration_type = models.CharField(max_length=255, blank=True)
    license_or_registration_number = models.CharField(max_length=100, blank=True)
    issuing_authority = models.CharField(max_length=255, blank=True)
    license_expires_at = models.DateField(null=True, blank=True)

    company_legal_name = models.CharField(max_length=255, blank=True)
    company_rfc = models.CharField(
        max_length=13,
        blank=True,
        validators=[rfc_validator],
    )
    representative_job_title = models.CharField(max_length=255, blank=True)
    has_authority_to_represent = models.BooleanField(default=False)

    identity_verified = models.BooleanField(default=False)
    professional_info_verified = models.BooleanField(default=False)
    manual_review_required = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "broker_profiles"
        verbose_name = "Broker profile"
        verbose_name_plural = "Broker profiles"

    def __str__(self) -> str:
        return f"BrokerProfile<{self.user.email}>"

    @property
    def is_approved(self) -> bool:
        return self.application_status == BrokerApplicationStatus.APPROVED

    def clean(self) -> None:
        errors = {}

        if self.broker_type == BrokerType.COMPANY_REPRESENTATIVE:
            if not self.company_legal_name:
                errors["company_legal_name"] = "This field is required for company representatives."
            if not self.company_rfc:
                errors["company_rfc"] = "This field is required for company representatives."
            if not self.representative_job_title:
                errors["representative_job_title"] = "This field is required for company representatives."
            if not self.has_authority_to_represent:
                errors["has_authority_to_represent"] = (
                    "Company representatives must declare authority to represent the company."
                )

        if self.broker_type == BrokerType.INDIVIDUAL:
            if self.company_legal_name:
                errors["company_legal_name"] = "Individuals should not provide company legal name."
            if self.company_rfc:
                errors["company_rfc"] = "Individuals should not provide company RFC."
            if self.representative_job_title:
                errors["representative_job_title"] = "Individuals should not provide representative job title."
            if self.has_authority_to_represent:
                errors["has_authority_to_represent"] = (
                    "Individuals should not declare company representation authority."
                )

        if errors:
            raise ValidationError(errors)

    def submit_for_review(self) -> None:
        self.full_clean()

        if not self.accepted_broker_declaration_at:
            raise ValidationError(
                {"accepted_broker_declaration_at": "Broker declaration must be accepted before submission."}
            )

        if not self.identity_verified:
            raise ValidationError(
                {"identity_verified": "Identity must be verified before submission."}
            )

        self.application_status = BrokerApplicationStatus.UNDER_REVIEW
        self.submitted_at = timezone.now()
        self.reviewed_at = None
        self.approved_at = None
        self.rejected_at = None
        self.can_create_transactions = False
        self.is_active_broker = False
        self.manual_review_required = True

    def mark_needs_info(self, notes: str = "") -> None:
        reviewed_at = timezone.now()
        self.application_status = BrokerApplicationStatus.NEEDS_INFO
        self.reviewed_at = reviewed_at
        self.review_notes = notes
        self.approved_at = None
        self.rejected_at = None
        self.can_create_transactions = False
        self.is_active_broker = False
        self.manual_review_required = True

    def approve(self, notes: str = "") -> None:
        approved_at = timezone.now()
        self.application_status = BrokerApplicationStatus.APPROVED
        self.reviewed_at = approved_at
        self.approved_at = approved_at
        self.rejected_at = None
        self.review_notes = notes
        self.can_create_transactions = True
        self.is_active_broker = True
        self.professional_info_verified = True
        self.manual_review_required = False

    def reject(self, notes: str = "") -> None:
        rejected_at = timezone.now()
        self.application_status = BrokerApplicationStatus.REJECTED
        self.reviewed_at = rejected_at
        self.rejected_at = rejected_at
        self.approved_at = None
        self.review_notes = notes
        self.can_create_transactions = False
        self.is_active_broker = False
        self.manual_review_required = False

    def save(self, *args, **kwargs):
        if self.company_rfc:
            self.company_rfc = self.company_rfc.strip().upper()
        super().save(*args, **kwargs)
