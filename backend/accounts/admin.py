from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import BrokerProfile, User, UserProfile


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User

    list_display = (
        "email",
        "first_name",
        "last_name",
        "phone",
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
        "phone",
    )
    ordering = ("-date_joined",)
    readonly_fields = ("created_at", "updated_at")

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
                "fields": ("first_name", "last_name", "phone"),
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
                "fields": ("last_login", "date_joined", "created_at", "updated_at"),
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
                    "first_name",
                    "last_name",
                    "phone",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "identity_status",
        "state",
        "city",
        "date_of_birth",
        "profile_completed_at",
        "updated_at",
    )
    list_filter = (
        "identity_status",
        "id_type",
        "state",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "rfc",
        "curp",
        "city",
        "state",
    )
    readonly_fields = ("profile_completed_at", "created_at", "updated_at")
    ordering = ("-updated_at",)
    list_select_related = ("user",)


@admin.register(BrokerProfile)
class BrokerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "broker_type",
        "application_status",
        "can_create_transactions",
        "is_active_broker",
        "identity_verified",
        "operating_state",
        "primary_market",
        "brokerage_name",
        "approved_at",
        "created_at",
    )
    list_filter = (
        "broker_type",
        "application_status",
        "can_create_transactions",
        "is_active_broker",
        "identity_verified",
        "manual_review_required",
        "operating_state",
        "has_authority_to_represent",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "user__profile__rfc",
        "brokerage_name",
        "license_or_registration_number",
        "company_legal_name",
        "company_rfc",
    )
    readonly_fields = (
        "id",
        "submitted_at",
        "reviewed_at",
        "approved_at",
        "rejected_at",
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
                    "can_create_transactions",
                    "is_active_broker",
                    "manual_review_required",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "identity_verified",
                    "professional_info_verified",
                    "accepted_broker_declaration_at",
                )
            },
        ),
        (
            "Professional information",
            {
                "fields": (
                    "brokerage_name",
                    "years_of_experience",
                    "primary_market",
                    "operating_state",
                    "license_or_registration_type",
                    "license_or_registration_number",
                    "issuing_authority",
                    "license_expires_at",
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
                    "reviewed_at",
                    "approved_at",
                    "rejected_at",
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
