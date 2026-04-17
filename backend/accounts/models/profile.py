from django.conf import settings
from django.db import models
from accounts.validators import curp_validator, postal_code_validator, rfc_validator


class IdentityStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Unverified"
    PENDING = "pending", "Pending"
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

    identity_status = models.CharField(
        max_length=20,
        choices=IdentityStatus.choices,
        default=IdentityStatus.UNVERIFIED,
    )

    profile_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User profile"
        verbose_name_plural = "User profiles"

    def __str__(self) -> str:
        return f"UserProfile<{self.user.email}>"

    @property
    def is_identity_verified(self) -> bool:
        return self.identity_status == IdentityStatus.VERIFIED

    def save(self, *args, **kwargs):
        if self.rfc:
            self.rfc = self.rfc.strip().upper()
        if self.curp:
            self.curp = self.curp.strip().upper()
        if self.postal_code:
            self.postal_code = self.postal_code.strip()
        super().save(*args, **kwargs)
