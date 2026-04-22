from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.validators import (
    curp_validator,
    name_place_validator,
    postal_code_validator,
    rfc_validator,
)


class IdentityVerificationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    NEEDS_INFO = "needs_info", "Needs info"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class GovernmentIDType(models.TextChoices):
    INE = "ine", "INE"
    PASSPORT = "passport", "Passport"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    date_of_birth = models.DateField(null=True, blank=True)

    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(
        max_length=5,
        blank=True,
        validators=[postal_code_validator],
    )
    status = models.CharField(
        max_length=20,
        choices=IdentityVerificationStatus.choices,
        default=IdentityVerificationStatus.DRAFT,
    )
    legal_first_name = models.CharField(
        max_length=150,
        blank=True,
        validators=[name_place_validator],
    )
    legal_middle_name = models.CharField(
        max_length=150,
        blank=True,
        validators=[name_place_validator],
    )
    legal_last_name = models.CharField(
        max_length=150,
        blank=True,
        validators=[name_place_validator],
    )
    rfc = models.CharField(
        max_length=13,
        blank=True,
        validators=[rfc_validator],
    )
    curp = models.CharField(
        max_length=18,
        blank=True,
        validators=[curp_validator],
    )
    id_type = models.CharField(
        max_length=20,
        choices=GovernmentIDType.choices,
        blank=True,
    )
    id_image = models.FileField(
        upload_to="accounts/id-images/",
        blank=True,
        null=True,
    )
    applicant_message = models.TextField(blank=True)
    internal_review_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_started_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="identity_verifications_reviewed",
    )
    manual_review_required = models.BooleanField(default=True)

    profile_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"
        permissions = (
            ("review_identityverification", "Can review identity verifications"),
        )

    def __str__(self) -> str:
        return f"UserProfile<{self.user.email}>"

    @property
    def is_identity_verified(self) -> bool:
        return self.status == IdentityVerificationStatus.VERIFIED

    @property
    def has_submitted_form(self) -> bool:
        return self.status in {
            IdentityVerificationStatus.SUBMITTED,
            IdentityVerificationStatus.VERIFIED,
        }

    @property
    def is_editable_by_applicant(self) -> bool:
        return self.status in {
            IdentityVerificationStatus.DRAFT,
            IdentityVerificationStatus.NEEDS_INFO,
        }

    def clean(self) -> None:
        errors = {}

        if self.status != IdentityVerificationStatus.DRAFT:
            if not self.legal_first_name:
                errors["legal_first_name"] = "Legal first name is required before submission."
            if not self.legal_last_name:
                errors["legal_last_name"] = "Legal last name is required before submission."
            if not self.id_type:
                errors["id_type"] = "Government ID type is required before submission."
            if not self.id_image:
                errors["id_image"] = "Government ID image is required before submission."
            if not (self.rfc or self.curp):
                errors["non_field_errors"] = [
                    "Provide at least one government identifier before submission."
                ]

        if errors:
            raise ValidationError(errors)

    def save_draft(self) -> None:
        if not self.is_editable_by_applicant:
            raise ValidationError(
                {"status": "Only draft or needs-info identity verifications can be edited by the applicant."}
            )

        self.status = IdentityVerificationStatus.DRAFT
        self.manual_review_required = True

    def submit(self) -> None:
        if self.status not in {
            IdentityVerificationStatus.DRAFT,
            IdentityVerificationStatus.NEEDS_INFO,
        }:
            raise ValidationError(
                {"status": "Only draft or needs-info identity verifications can be submitted."}
            )

        submitted_at = timezone.now()
        self.status = IdentityVerificationStatus.SUBMITTED
        self.submitted_at = submitted_at
        self.review_started_at = None
        self.reviewed_at = None
        self.verified_at = None
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
        if self.status != IdentityVerificationStatus.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted identity verifications can request more information."}
            )
        if not applicant_message.strip():
            raise ValidationError(
                {"applicant_message": "An applicant-facing message is required when requesting more information."}
            )

        reviewed_at = timezone.now()
        self.status = IdentityVerificationStatus.NEEDS_INFO
        self.review_started_at = self.review_started_at or reviewed_at
        self.reviewed_at = reviewed_at
        self.reviewed_by = reviewer
        self.applicant_message = applicant_message.strip()
        self.internal_review_notes = internal_review_notes.strip()
        self.verified_at = None
        self.rejected_at = None
        self.manual_review_required = True

    def approve(self, *, reviewer, internal_review_notes: str = "") -> None:
        if self.status != IdentityVerificationStatus.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted identity verifications can be approved."}
            )

        verified_at = timezone.now()
        self.status = IdentityVerificationStatus.VERIFIED
        self.review_started_at = self.review_started_at or verified_at
        self.reviewed_at = verified_at
        self.verified_at = verified_at
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
        if self.status != IdentityVerificationStatus.SUBMITTED:
            raise ValidationError(
                {"status": "Only submitted identity verifications can be rejected."}
            )
        if not applicant_message.strip():
            raise ValidationError(
                {"applicant_message": "An applicant-facing message is required when rejecting identity verification."}
            )

        rejected_at = timezone.now()
        self.status = IdentityVerificationStatus.REJECTED
        self.review_started_at = self.review_started_at or rejected_at
        self.reviewed_at = rejected_at
        self.rejected_at = rejected_at
        self.verified_at = None
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
        if self.status != IdentityVerificationStatus.REJECTED:
            raise ValidationError(
                {"status": "Only rejected identity verifications can be reopened."}
            )
        if not applicant_message.strip():
            raise ValidationError(
                {"applicant_message": "An applicant-facing message is required when reopening identity verification."}
            )

        reopened_at = timezone.now()
        self.status = IdentityVerificationStatus.DRAFT
        self.reviewed_at = reopened_at
        self.reviewed_by = reviewer
        self.applicant_message = applicant_message.strip()
        self.internal_review_notes = internal_review_notes.strip()
        self.verified_at = None
        self.rejected_at = None
        self.manual_review_required = True

    def save(self, *args, **kwargs):
        if self.state:
            self.state = self.state.strip()
        if self.city:
            self.city = self.city.strip()
        if self.address_line_1:
            self.address_line_1 = self.address_line_1.strip()
        if self.address_line_2:
            self.address_line_2 = self.address_line_2.strip()
        if self.postal_code:
            self.postal_code = self.postal_code.strip()
        if self.legal_first_name:
            self.legal_first_name = self.legal_first_name.strip()
        if self.legal_middle_name:
            self.legal_middle_name = self.legal_middle_name.strip()
        if self.legal_last_name:
            self.legal_last_name = self.legal_last_name.strip()
        if self.rfc:
            self.rfc = self.rfc.strip().upper()
        if self.curp:
            self.curp = self.curp.strip().upper()
        if self.applicant_message:
            self.applicant_message = self.applicant_message.strip()
        if self.internal_review_notes:
            self.internal_review_notes = self.internal_review_notes.strip()
        super().save(*args, **kwargs)
