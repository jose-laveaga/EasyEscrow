from django.contrib import admin

from file_security.models import FileSecurityReport


@admin.register(FileSecurityReport)
class FileSecurityReportAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "policy_name",
        "status",
        "reason_code",
        "original_filename",
        "detected_content_type",
        "size_bytes",
        "uploaded_by",
    )
    list_filter = ("status", "policy_name", "malware_scan_status", "detected_content_type")
    search_fields = ("original_filename", "sha256", "reason", "stored_file_name")
    readonly_fields = [field.name for field in FileSecurityReport._meta.fields]
