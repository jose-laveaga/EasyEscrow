from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import (
    BrokerApplication,
    BrokerApplicationStatus,
    BrokerProfile,
    IdentityVerificationStatus,
    User,
    UserProfile,
)
from accounts.services.broker import (
    approve_broker_application,
    reopen_broker_application,
    reject_broker_application,
    request_broker_application_changes,
)
from accounts.services.identity import (
    approve_identity_verification,
    reopen_identity_verification,
    reject_identity_verification,
    request_identity_verification_changes,
)


class WorkflowReviewBaseForm(forms.Form):
    internal_review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Internal review notes",
    )


class WorkflowApproveForm(WorkflowReviewBaseForm):
    pass


class WorkflowNeedsInfoForm(WorkflowReviewBaseForm):
    applicant_message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to applicant",
    )


class WorkflowRejectForm(WorkflowReviewBaseForm):
    applicant_message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to applicant",
    )


class WorkflowReopenForm(WorkflowReviewBaseForm):
    applicant_message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to applicant",
    )


class WorkflowAdminMixin:
    workflow_action_map = {}
    review_permission_codename = ""

    def get_workflow_url_name(self, action: str) -> str:
        opts = self.model._meta
        return f"{opts.app_label}_{opts.model_name}_{action}"

    def has_review_permission(self, request):
        return request.user.is_superuser or request.user.has_perm(self.review_permission_codename)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "show_save": False,
            "show_save_and_continue": False,
            "show_save_and_add_another": False,
            "show_delete": False,
        }
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/request-info/",
                self.admin_site.admin_view(self.request_info_view),
                name=self.get_workflow_url_name("request_info"),
            ),
            path(
                "<path:object_id>/approve/",
                self.admin_site.admin_view(self.approve_view),
                name=self.get_workflow_url_name("approve"),
            ),
            path(
                "<path:object_id>/reject/",
                self.admin_site.admin_view(self.reject_view),
                name=self.get_workflow_url_name("reject"),
            ),
            path(
                "<path:object_id>/reopen/",
                self.admin_site.admin_view(self.reopen_view),
                name=self.get_workflow_url_name("reopen"),
            ),
        ]
        return custom_urls + urls

    def _get_review_target(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404(f"{self.model._meta.verbose_name} not found.")
        if not self.has_review_permission(request):
            raise PermissionDenied
        return obj

    def _handle_validation_error(self, form, exc: ValidationError):
        if hasattr(exc, "message_dict"):
            for field_name, errors in exc.message_dict.items():
                target_field = field_name if field_name in form.fields else None
                for error in errors:
                    form.add_error(target_field, error)
            return

        for error in exc.messages:
            form.add_error(None, error)

    def _render_workflow_form(self, request, obj, form, *, title):
        opts = self.model._meta
        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "original": obj,
            "object": obj,
            "title": title,
            "form": form,
            "media": self.media + form.media,
            "changelist_url_name": f"admin:{opts.app_label}_{opts.model_name}_changelist",
            "change_url_name": f"admin:{opts.app_label}_{opts.model_name}_change",
            "review_subject": self.get_review_subject(obj),
        }
        return TemplateResponse(
            request,
            "admin/accounts/workflow_action.html",
            context,
        )

    def _process_workflow_form(
        self,
        request,
        object_id,
        *,
        form_class,
        title,
        success_message,
        service_call,
    ):
        obj = self._get_review_target(request, object_id)

        if request.method == "POST":
            form = form_class(request.POST)
            if form.is_valid():
                try:
                    service_call(obj, form.cleaned_data)
                except ValidationError as exc:
                    self._handle_validation_error(form, exc)
                else:
                    self.message_user(request, success_message, level=messages.SUCCESS)
                    change_url = reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change", args=[obj.pk])
                    return HttpResponseRedirect(change_url)
        else:
            form = form_class()

        return self._render_workflow_form(request, obj, form, title=title)

    def workflow_actions(self, obj):
        actions = self.workflow_action_map.get(self.get_workflow_status(obj), ())
        if not actions:
            return "No reviewer actions are available for this status."

        links = []
        for label, action in actions:
            url = reverse(f"admin:{self.get_workflow_url_name(action)}", args=[obj.pk])
            links.append(
                format_html(
                    '<a class="button" href="{}" style="margin-right: 8px;">{}</a>',
                    url,
                    label,
                )
            )

        return mark_safe("".join(str(link) for link in links))

    workflow_actions.short_description = "Workflow actions"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User

    list_display = (
        "email",
        "first_name",
        "middle_name",
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
        "middle_name",
        "last_name",
        "phone",
    )
    ordering = ("-date_joined",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "middle_name", "last_name", "phone")}),
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
            {"fields": ("last_login", "date_joined", "created_at", "updated_at")},
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
                    "middle_name",
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
class UserProfileAdmin(WorkflowAdminMixin, admin.ModelAdmin):
    review_permission_codename = "accounts.review_identityverification"
    workflow_action_map = {
        IdentityVerificationStatus.SUBMITTED: (
            ("Needs info", "request_info"),
            ("Approve", "approve"),
            ("Reject", "reject"),
        ),
        IdentityVerificationStatus.REJECTED: (
            ("Reopen", "reopen"),
        ),
    }

    list_display = (
        "user",
        "status",
        "legal_name_display",
        "state",
        "city",
        "id_type",
        "is_identity_verified_display",
        "submitted_at",
        "reviewed_by",
        "verified_at",
        "created_at",
    )
    list_filter = ("status", "state", "id_type", "manual_review_required")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__middle_name",
        "user__last_name",
        "legal_first_name",
        "legal_middle_name",
        "legal_last_name",
        "rfc",
        "curp",
        "city",
        "state",
    )
    readonly_fields = (
        "user",
        "status",
        "workflow_actions",
        "is_identity_verified_display",
        "account_name_display",
        "legal_name_display",
        "date_of_birth",
        "state",
        "city",
        "address_line_1",
        "address_line_2",
        "postal_code",
        "profile_completed_at",
        "rfc",
        "curp",
        "id_type",
        "id_image_link",
        "submitted_at",
        "review_started_at",
        "reviewed_at",
        "verified_at",
        "rejected_at",
        "reviewed_by",
        "applicant_message",
        "internal_review_notes",
        "manual_review_required",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Workflow",
            {
                "fields": (
                    "status",
                    "workflow_actions",
                    "is_identity_verified_display",
                    "account_name_display",
                    "legal_name_display",
                    "submitted_at",
                    "review_started_at",
                    "reviewed_at",
                    "verified_at",
                    "rejected_at",
                    "reviewed_by",
                    "applicant_message",
                    "internal_review_notes",
                    "manual_review_required",
                )
            },
        ),
        (
            "Applicant profile",
            {
                "fields": (
                    "user",
                    "date_of_birth",
                    "state",
                    "city",
                    "address_line_1",
                    "address_line_2",
                    "postal_code",
                    "profile_completed_at",
                )
            },
        ),
        (
            "Identity data",
            {
                "fields": (
                    "rfc",
                    "curp",
                    "id_type",
                    "id_image_link",
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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "reviewed_by")

    def get_workflow_status(self, obj):
        return obj.status

    def get_review_subject(self, obj):
        return f"identity verification for {obj.user.email}"

    @admin.display(description="Account name")
    def account_name_display(self, obj):
        parts = [obj.user.first_name, obj.user.middle_name, obj.user.last_name]
        return " ".join(part for part in parts if part) or "-"

    @admin.display(description="Legal name")
    def legal_name_display(self, obj):
        parts = [obj.legal_first_name, obj.legal_middle_name, obj.legal_last_name]
        return " ".join(part for part in parts if part) or "-"

    @admin.display(description="Identity verified", boolean=True)
    def is_identity_verified_display(self, obj):
        return obj.is_identity_verified

    @admin.display(description="Uploaded ID")
    def id_image_link(self, obj):
        if not obj.id_image:
            return "-"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">Open uploaded ID</a>',
            obj.id_image.url,
        )

    def request_info_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowNeedsInfoForm,
            title="Request More Identity Information",
            success_message="Applicant has been asked for more identity information.",
            service_call=lambda obj, data: request_identity_verification_changes(
                user_profile=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def approve_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowApproveForm,
            title="Approve Identity Verification",
            success_message="Identity verification approved.",
            service_call=lambda obj, data: approve_identity_verification(
                user_profile=obj,
                reviewer=request.user,
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def reject_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowRejectForm,
            title="Reject Identity Verification",
            success_message="Identity verification rejected.",
            service_call=lambda obj, data: reject_identity_verification(
                user_profile=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def reopen_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowReopenForm,
            title="Reopen Identity Verification",
            success_message="Identity verification reopened for applicant edits.",
            service_call=lambda obj, data: reopen_identity_verification(
                user_profile=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )


@admin.register(BrokerApplication)
class BrokerApplicationAdmin(WorkflowAdminMixin, admin.ModelAdmin):
    review_permission_codename = "accounts.review_brokerapplication"
    workflow_action_map = {
        BrokerApplicationStatus.SUBMITTED: (
            ("Needs info", "request_info"),
            ("Approve", "approve"),
            ("Reject", "reject"),
        ),
        BrokerApplicationStatus.REJECTED: (
            ("Reopen", "reopen"),
        ),
    }

    list_display = (
        "user",
        "broker_type",
        "status",
        "identity_verification_status_display",
        "has_active_profile_display",
        "operating_state",
        "primary_market",
        "brokerage_name",
        "reviewed_by",
        "approved_at",
        "created_at",
    )
    list_filter = (
        "broker_type",
        "status",
        "operating_state",
        "has_authority_to_represent",
        "manual_review_required",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "brokerage_name",
        "license_or_registration_number",
        "company_legal_name",
        "company_rfc",
    )
    readonly_fields = (
        "id",
        "user",
        "status",
        "workflow_actions",
        "identity_verification_status_display",
        "identity_verification_overview",
        "active_broker_profile_overview",
        "reviewed_by",
        "accepted_broker_declaration_at",
        "submitted_at",
        "review_started_at",
        "reviewed_at",
        "approved_at",
        "rejected_at",
        "applicant_message",
        "internal_review_notes",
        "manual_review_required",
        "broker_type",
        "brokerage_name",
        "years_of_experience",
        "primary_market",
        "operating_state",
        "license_or_registration_type",
        "license_or_registration_number",
        "issuing_authority",
        "license_expires_at",
        "company_legal_name",
        "company_rfc",
        "representative_job_title",
        "has_authority_to_represent",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Workflow",
            {
                "fields": (
                    "status",
                    "workflow_actions",
                    "reviewed_by",
                    "accepted_broker_declaration_at",
                    "submitted_at",
                    "review_started_at",
                    "reviewed_at",
                    "approved_at",
                    "rejected_at",
                    "applicant_message",
                    "internal_review_notes",
                    "manual_review_required",
                )
            },
        ),
        (
            "Identity readiness",
            {
                "fields": (
                    "identity_verification_status_display",
                    "identity_verification_overview",
                    "active_broker_profile_overview",
                )
            },
        ),
        (
            "Professional information",
            {
                "fields": (
                    "id",
                    "user",
                    "broker_type",
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
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "reviewed_by", "user__profile", "user__broker_profile")
        )

    def get_workflow_status(self, obj):
        return obj.status

    def get_review_subject(self, obj):
        return f"broker application for {obj.user.email}"

    @admin.display(description="Identity status")
    def identity_verification_status_display(self, obj):
        try:
            verification = obj.user.profile
        except ObjectDoesNotExist:
            return "No identity verification"
        return verification.get_status_display()

    @admin.display(description="Active broker profile", boolean=True)
    def has_active_profile_display(self, obj):
        return hasattr(obj.user, "broker_profile")

    @admin.display(description="Identity verification")
    def identity_verification_overview(self, obj):
        try:
            verification = obj.user.profile
        except ObjectDoesNotExist:
            return "No identity verification is attached."

        verification_link = reverse("admin:accounts_userprofile_change", args=[verification.pk])
        return format_html(
            "<strong>Identity verification</strong>: <a href='{}'>Open identity verification</a><br>"
            "<strong>Status</strong>: {}<br>"
            "<strong>Submitted at</strong>: {}<br>"
            "<strong>Verified at</strong>: {}<br>"
            "<strong>Applicant message</strong>: {}",
            verification_link,
            verification.get_status_display(),
            verification.submitted_at or "-",
            verification.verified_at or "-",
            verification.applicant_message or "-",
        )

    @admin.display(description="Active broker profile")
    def active_broker_profile_overview(self, obj):
        profile = getattr(obj.user, "broker_profile", None)
        if profile is None:
            return "No active broker profile exists yet."

        profile_link = reverse("admin:accounts_brokerprofile_change", args=[profile.pk])
        return format_html(
            "<strong>Broker profile</strong>: <a href='{}'>Open active broker profile</a><br>"
            "<strong>Approved at</strong>: {}<br>"
            "<strong>Can create transactions</strong>: {}",
            profile_link,
            profile.approved_at or "-",
            "Yes" if profile.can_create_transactions else "No",
        )

    def request_info_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowNeedsInfoForm,
            title="Request More Broker Information",
            success_message="Applicant has been asked for more broker information.",
            service_call=lambda obj, data: request_broker_application_changes(
                application=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def approve_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowApproveForm,
            title="Approve Broker Application",
            success_message="Broker application approved.",
            service_call=lambda obj, data: approve_broker_application(
                application=obj,
                reviewer=request.user,
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def reject_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowRejectForm,
            title="Reject Broker Application",
            success_message="Broker application rejected.",
            service_call=lambda obj, data: reject_broker_application(
                application=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def reopen_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=WorkflowReopenForm,
            title="Reopen Broker Application",
            success_message="Broker application reopened for applicant edits.",
            service_call=lambda obj, data: reopen_broker_application(
                application=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )


@admin.register(BrokerProfile)
class BrokerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "broker_type",
        "is_active_broker",
        "can_create_transactions_display",
        "identity_verification_status_display",
        "approved_at",
        "approved_by",
        "created_at",
    )
    list_filter = (
        "broker_type",
        "is_active_broker",
        "operating_state",
        "has_authority_to_represent",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "brokerage_name",
        "license_or_registration_number",
        "company_legal_name",
        "company_rfc",
    )
    readonly_fields = (
        "id",
        "user",
        "approved_application_link",
        "identity_verification_link",
        "approved_by",
        "broker_type",
        "is_active_broker",
        "approved_at",
        "can_create_transactions_display",
        "brokerage_name",
        "years_of_experience",
        "primary_market",
        "operating_state",
        "license_or_registration_type",
        "license_or_registration_number",
        "issuing_authority",
        "license_expires_at",
        "company_legal_name",
        "company_rfc",
        "representative_job_title",
        "has_authority_to_represent",
        "created_at",
        "updated_at",
    )
    ordering = ("-approved_at", "-created_at")

    fieldsets = (
        (
            "Operational status",
            {
                "fields": (
                    "id",
                    "user",
                    "broker_type",
                    "is_active_broker",
                    "can_create_transactions_display",
                    "approved_at",
                    "approved_by",
                    "approved_application_link",
                    "identity_verification_link",
                )
            },
        ),
        (
            "Broker details",
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
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "user__profile", "approved_by", "approved_application")
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Can create transactions", boolean=True)
    def can_create_transactions_display(self, obj):
        return obj.can_create_transactions

    @admin.display(description="Identity status")
    def identity_verification_status_display(self, obj):
        try:
            identity_profile = obj.user.profile
        except ObjectDoesNotExist:
            return "No identity verification"
        return identity_profile.get_status_display()

    @admin.display(description="Approved application")
    def approved_application_link(self, obj):
        if not obj.approved_application_id:
            return "-"
        url = reverse("admin:accounts_brokerapplication_change", args=[obj.approved_application_id])
        return format_html("<a href='{}'>Open approved broker application</a>", url)

    @admin.display(description="Identity verification")
    def identity_verification_link(self, obj):
        try:
            identity_profile = obj.user.profile
        except ObjectDoesNotExist:
            return "-"
        url = reverse("admin:accounts_userprofile_change", args=[identity_profile.pk])
        return format_html("<a href='{}'>Open linked identity verification</a>", url)
