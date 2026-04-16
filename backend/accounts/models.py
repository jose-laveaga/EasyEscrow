from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid

rfc_validator = RegexValidator(
    regex=r"^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$",
    message="Enter a valid Mexican RFC.",
)

phone_validator = RegexValidator(
    regex=r"^\+52\d{10}$",
    message="Enter a valid Mexican phone number in format +52-XX-XXXX-XXXX.",
)

name_place_validator = RegexValidator(
    regex=r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ'.\- ]{2,100}$",
    message="This field contains invalid characters.",
)

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is False:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is False:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    first_name = models.CharField(max_length=100, validators=[name_place_validator])
    last_name = models.CharField(max_length=100, validators=[name_place_validator])
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


# Broker profile



class BrokerProfile(models.Model):
    class BrokerApplicationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NEEDS_INFO = "needs_info", "Needs info"

    class BrokerType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        COMPANY_REPRESENTATIVE = "company_representative", "Company representative"

    class MexicoState(models.TextChoices):
        CIUDAD_DE_MEXICO = "CIUDAD_DE_MEXICO", "Ciudad de México"
        JALISCO = "JALISCO", "Jalisco"
        NUEVO_LEON = "NUEVO_LEON", "Nuevo León"
        ESTADO_DE_MEXICO = "ESTADO_DE_MEXICO", "Estado de México"
        # add the rest

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broker_profile",
    )

    broker_type = models.CharField(
        max_length=30,
        choices=BrokerType,
    )

    # Core broker identity / business info

    phone = models.CharField(max_length=13, validators=[phone_validator])
    rfc = models.CharField(max_length=13, validators=[rfc_validator])
    city = models.CharField(max_length=100, validators=[name_place_validator])
    state = models.CharField(max_length=50, choices=MexicoState)

    # Optional professional signal
    brokerage_name = models.CharField(max_length=255, blank=True)
    certification_name = models.CharField(max_length=255, blank=True)
    certification_number = models.CharField(max_length=100, blank=True)

    # Company representative fields
    company_legal_name = models.CharField(max_length=255, blank=True)
    company_rfc = models.CharField(max_length=13, blank=True)
    representative_job_title = models.CharField(max_length=255, blank=True)
    has_authority_to_represent = models.BooleanField(default=False)

    # Verification / application workflow
    identity_verified = models.BooleanField(default=False)

    application_status = models.CharField(
        max_length=20,
        choices=BrokerApplicationStatus,
        default=BrokerApplicationStatus.DRAFT,
    )

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    needs_info_at = models.DateTimeField(null=True, blank=True)

    # Platform-level broker declaration / attestation
    accepted_broker_declaration_at = models.DateTimeField(null=True, blank=True)

    # Optional internal review/admin notes
    review_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "broker_profiles"

    def __str__(self) -> str:
        return f"BrokerProfile<{self.user.email}>"

    @property
    def is_approved(self) -> bool:
        return self.application_status == self.BrokerApplicationStatus.APPROVED

    @property
    def can_create_transactions(self) -> bool:
        return self.application_status == self.BrokerApplicationStatus.APPROVED

    def clean(self) -> None:
        errors = {}

        if self.broker_type == self.BrokerType.COMPANY_REPRESENTATIVE:
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

        if self.broker_type == self.BrokerType.INDIVIDUAL:
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

        self.application_status = self.BrokerApplicationStatus.UNDER_REVIEW
        self.submitted_at = timezone.now()
        self.approved_at = None
        self.rejected_at = None
        self.needs_info_at = None

    def mark_needs_info(self, notes: str = "") -> None:
        self.application_status = self.BrokerApplicationStatus.NEEDS_INFO
        self.needs_info_at = timezone.now()
        self.review_notes = notes
        self.approved_at = None
        self.rejected_at = None

    def approve(self, notes: str = "") -> None:
        self.application_status = self.BrokerApplicationStatus.APPROVED
        self.approved_at = timezone.now()
        self.rejected_at = None
        self.needs_info_at = None
        self.review_notes = notes

    def reject(self, notes: str = "") -> None:
        self.application_status = self.BrokerApplicationStatus.REJECTED
        self.rejected_at = timezone.now()
        self.approved_at = None
        self.needs_info_at = None
        self.review_notes = notes

    def save(self, *args, **kwargs):
        if self.rfc:
            self.rfc = self.rfc.strip().upper()
        if self.company_rfc:
            self.company_rfc = self.company_rfc.strip().upper()
        super().save(*args, **kwargs)

