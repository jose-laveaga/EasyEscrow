from django.conf import settings
from django.db import models


class FileSecurityStatus(models.TextChoices):
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    ERROR = "ERROR", "Error"


class MalwareScanStatus(models.TextChoices):
    CLEAN = "CLEAN", "Clean"
    INFECTED = "INFECTED", "Infected"
    SKIPPED = "SKIPPED", "Skipped"
    ERROR = "ERROR", "Error"


class FileSecurityReport(models.Model):
    policy_name = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=FileSecurityStatus.choices)
    reason_code = models.CharField(max_length=80, blank=True)
    reason = models.TextField(blank=True)

    original_filename = models.CharField(max_length=255, blank=True)
    client_content_type = models.CharField(max_length=255, blank=True)
    detected_content_type = models.CharField(max_length=255, blank=True)
    extension = models.CharField(max_length=20, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)

    malware_scan_status = models.CharField(
        max_length=20,
        choices=MalwareScanStatus.choices,
        default=MalwareScanStatus.SKIPPED,
    )
    malware_scan_detail = models.TextField(blank=True)
    sanitizer = models.CharField(max_length=120, blank=True)
    stored_file_name = models.CharField(max_length=500, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="file_security_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.policy_name}: {self.status} {self.original_filename}".strip()
