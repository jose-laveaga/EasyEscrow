from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import BrokerProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
        "last_login",
        "date_joined",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
    )
    search_fields = (
        "email",
        "first_name",
        "last_name",
    )
    ordering = ("-date_joined",)

    fieldsets = (
        (
            None,
            {
                "fields": ("email", "password"),
            },
        ),
        (
            "Personal info",
            {
                "fields": ("first_name", "last_name"),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            "Important dates",
            {
                "fields": ("last_login", "date_joined"),
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(BrokerProfile)
class BrokerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "broker_type",
        "application_status",
        "identity_verified",
        "state",
        "city",
        "brokerage_name",
        "approved_at",
        "created_at",
    )
    list_filter = (
        "broker_type",
        "application_status",
        "identity_verified",
        "state",
        "has_authority_to_represent",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "rfc",
        "brokerage_name",
        "company_legal_name",
        "company_rfc",
    )
    readonly_fields = (
        "id",
        "submitted_at",
        "approved_at",
        "rejected_at",
        "needs_info_at",
        "accepted_broker_declaration_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    list_select_related = ("user",)

    fieldsets = (
        (
            "Core",
            {
                "fields": (
                    "id",
                    "user",
                    "broker_type",
                    "application_status",
                    "identity_verified",
                )
            },
        ),
        (
            "Location and identity",
            {
                "fields": (
                    "rfc",
                    "state",
                    "city",
                    "accepted_broker_declaration_at",
                )
            },
        ),
        (
            "Professional information",
            {
                "fields": (
                    "brokerage_name",
                    "certification_name",
                    "certification_number",
                )
            },
        ),
        (
            "Company representative information",
            {
                "fields": (
                    "company_legal_name",
                    "company_rfc",
                    "representative_job_title",
                    "has_authority_to_represent",
                )
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "review_notes",
                    "submitted_at",
                    "approved_at",
                    "rejected_at",
                    "needs_info_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )