from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone

from ..validators import rfc_validator
import uuid


class BrokerApplicationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    NEEDS_INFO = "needs_info", "Needs info"


class BrokerType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual"
    COMPANY_REPRESENTATIVE = "company_representative", "Company representative"


class BrokerApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broker_applications",
    )

    broker_type = models.CharField(
        max_length=30,
        choices=BrokerType.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=BrokerApplicationStatus.choices,
        default=BrokerApplicationStatus.DRAFT,
    )
    applicant_message = models.TextField(blank=True)
    internal_review_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_started_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="broker_applications_reviewed",
    )
    accepted_broker_declaration_at = models.DateTimeField(null=True, blank=True)

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

    manual_review_required = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "broker_applications"
        verbose_name = "Broker application"
        verbose_name_plural = "Broker applications"
        permissions = (
            ("review_brokerapplication", "Can review broker applications"),
        )
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"BrokerApplication<{self.user.email}>"

    @property
    def is_approved(self) -> bool:
        return self.status == BrokerApplicationStatus.APPROVED

    @property
    def is_editable_by_applicant(self) -> bool:
        return self.status in {
            BrokerApplicationStatus.DRAFT,
            BrokerApplicationStatus.NEEDS_INFO,
        }

    def clean(self) -> None:
        errors = {}


        if self.status != BrokerApplicationStatus.DRAFT and not self.accepted_broker_declaration_at:
            errors["accepted_broker_declaration_at"] = "Broker declaration must be accepted before submission."


        if (
            self.status != BrokerApplicationStatus.DRAFT
            and self.broker_type == BrokerType.COMPANY_REPRESENTATIVE
        ):
            if not self.company_legal_name:
                errors["company_legal_name"] = "This field is required for company representatives."
            if not self.company_rfc:
                errors["company_rfc"] = "This field is required for company representatives."
            if not self.representative_job_title:
                errors["representative_job_title"] = "This field is required for company representatives."
            if not self.has_authority_to_represent:
                errors["has_authority_to_represent"] = "Company representatives must declare authority to represent the company."

            if self.years_of_experience is None:
                errors["years_of_experience"] = "Years of experience is required before submission."
            if not self.primary_market:
                errors["primary_market"] = "Primary market is required before submission."
            if not self.operating_state:
                errors["operating_state"] = "Operating state is required before submission."
            if not self.license_or_registration_type:
                errors["license_or_registration_type"] = "License or registration type is required before submission."
            if not self.license_or_registration_number:
                errors["license_or_registration_number"] = "License or registration number is required before submission."
            if not self.issuing_authority:
                errors["issuing_authority"] = "Issuing authority is required before submission."


        if (
            self.status != BrokerApplicationStatus.DRAFT
            and self.broker_type == BrokerType.INDIVIDUAL
        ):
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

    def save_draft(self) -> None:
        if not self.is_editable_by_applicant:
            raise ValidationError(
                {"status": "Only draft or needs-info applications can be edited by the applicant."}
            )

        self.status = BrokerApplicationStatus.DRAFT
        self.manual_review_required = True

    def submit(self) -> None:
        if self.status not in {
            BrokerApplicationStatus.DRAFT,
            BrokerApplicationStatus.NEEDS_INFO,
        }:
            raise ValidationError(
                {"status": "Only draft or needs-info applications can be submitted."}
            )

        self.status = BrokerApplicationStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.review_started_at = None
        self.reviewed_at = None
        self.approved_at = None
        self.rejected_at = None
        self.applicant_message = ""
        self.manual_review_required = True

        self.full_clean()

    def request_changes(
        self,
        *,
        reviewer,
        applicant_message: str,
        internal_review_notes: str = "",
    ) -> None:
        if self.status != BrokerApplicationStatus.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted applications can request more information."}
            )
        if not applicant_message.strip():
            raise ValidationError(
                {"applicant_message": "An applicant-facing message is required when requesting more information."}
            )

        reviewed_at = timezone.now()
        self.status = BrokerApplicationStatus.NEEDS_INFO
        self.review_started_at = self.review_started_at or reviewed_at
        self.reviewed_at = reviewed_at
        self.reviewed_by = reviewer
        self.applicant_message = applicant_message.strip()
        self.internal_review_notes = internal_review_notes.strip()
        self.approved_at = None
        self.rejected_at = None
        self.manual_review_required = True

    def approve(self, *, reviewer, internal_review_notes: str = "") -> None:
        if self.status != BrokerApplicationStatus.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted applications can be approved."}
            )

        approved_at = timezone.now()
        self.status = BrokerApplicationStatus.APPROVED
        self.review_started_at = self.review_started_at or approved_at
        self.reviewed_at = approved_at
        self.approved_at = approved_at
        self.rejected_at = None
        self.reviewed_by = reviewer
        self.applicant_message = ""
        self.internal_review_notes = internal_review_notes.strip()
        self.manual_review_required = False

    def reject(
        self,
        *,
        reviewer,
        applicant_message: str,
        internal_review_notes: str = "",
    ) -> None:
        if self.status != BrokerApplicationStatus.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted applications can be rejected."}
            )
        if not applicant_message.strip():
            raise ValidationError(
                {"applicant_message": "An applicant-facing message is required when rejecting an application."}
            )

        rejected_at = timezone.now()
        self.status = BrokerApplicationStatus.REJECTED
        self.review_started_at = self.review_started_at or rejected_at
        self.reviewed_at = rejected_at
        self.rejected_at = rejected_at
        self.approved_at = None
        self.reviewed_by = reviewer
        self.applicant_message = applicant_message.strip()
        self.internal_review_notes = internal_review_notes.strip()
        self.manual_review_required = False

    def reopen(
        self,
        *,
        reviewer,
        applicant_message: str,
        internal_review_notes: str = "",
    ) -> None:
        if self.status != BrokerApplicationStatus.REJECTED:
            raise ValidationError(
                {"status": "Only rejected applications can be reopened."}
            )
        if not applicant_message.strip():
            raise ValidationError(
                {"applicant_message": "An applicant-facing message is required when reopening an application."}
            )

        reopened_at = timezone.now()
        self.status = BrokerApplicationStatus.DRAFT
        self.reviewed_at = reopened_at
        self.reviewed_by = reviewer
        self.applicant_message = applicant_message.strip()
        self.internal_review_notes = internal_review_notes.strip()
        self.approved_at = None
        self.rejected_at = None
        self.manual_review_required = True

    def save(self, *args, **kwargs):
        if self.company_rfc:
            self.company_rfc = self.company_rfc.strip().upper()
        super().save(*args, **kwargs)


class BrokerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broker_profile",
    )
    approved_application = models.ForeignKey(
        "accounts.BrokerApplication",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_profiles",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="broker_profiles_approved",
    )

    broker_type = models.CharField(
        max_length=30,
        choices=BrokerType.choices,
    )
    is_active_broker = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "broker_profiles"
        verbose_name = "Broker profile"
        verbose_name_plural = "Broker profiles"

    def __str__(self) -> str:
        return f"BrokerProfile<{self.user.email}>"

    @property
    def can_create_transactions(self) -> bool:
        try:
            identity_profile = self.user.profile
        except ObjectDoesNotExist:
            return False
        return bool(
            self.is_active_broker
            and identity_profile
            and identity_profile.is_identity_verified
        )

    def sync_from_application(
        self,
        *,
        application: BrokerApplication,
        reviewer,
    ) -> None:
        self.user = application.user
        self.approved_application = application
        self.approved_by = reviewer
        self.broker_type = application.broker_type
        self.is_active_broker = True
        self.approved_at = application.approved_at
        self.brokerage_name = application.brokerage_name
        self.years_of_experience = application.years_of_experience
        self.primary_market = application.primary_market
        self.operating_state = application.operating_state
        self.license_or_registration_type = application.license_or_registration_type
        self.license_or_registration_number = application.license_or_registration_number
        self.issuing_authority = application.issuing_authority
        self.license_expires_at = application.license_expires_at
        self.company_legal_name = application.company_legal_name
        self.company_rfc = application.company_rfc
        self.representative_job_title = application.representative_job_title
        self.has_authority_to_represent = application.has_authority_to_represent

    def save(self, *args, **kwargs):
        if self.company_rfc:
            self.company_rfc = self.company_rfc.strip().upper()
        super().save(*args, **kwargs)
