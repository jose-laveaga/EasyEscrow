from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import BrokerApplicationStatus, BrokerProfile, User, UserProfile
from accounts.services.broker import (
    approve_broker_profile,
    reopen_broker_profile,
    reject_broker_profile,
    request_broker_application_changes,
)


class BrokerReviewBaseForm(forms.Form):
    internal_review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Internal review notes",
    )


class BrokerApproveForm(BrokerReviewBaseForm):
    pass


class BrokerNeedsInfoForm(BrokerReviewBaseForm):
    applicant_message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to applicant",
    )


class BrokerRejectForm(BrokerReviewBaseForm):
    applicant_message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to applicant",
    )


class BrokerReopenForm(BrokerReviewBaseForm):
    applicant_message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 5}),
        label="Message to applicant",
    )


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
        "identity_status_display",
        "can_create_transactions_display",
        "is_active_broker",
        "operating_state",
        "primary_market",
        "brokerage_name",
        "reviewed_by",
        "approved_at",
        "created_at",
    )
    list_filter = (
        "broker_type",
        "application_status",
        "is_active_broker",
        "professional_info_verified",
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
        "user",
        "application_status",
        "can_create_transactions_display",
        "identity_status_display",
        "user_profile_overview",
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
        "is_active_broker",
        "professional_info_verified",
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
                    "application_status",
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
                )
            },
        ),
        (
            "Applicant Profile",
            {
                "fields": (
                    "user",
                    "identity_status_display",
                    "user_profile_overview",
                )
            },
        ),
        (
            "Broker Capability",
            {
                "fields": (
                    "can_create_transactions_display",
                    "is_active_broker",
                    "professional_info_verified",
                    "manual_review_required",
                )
            },
        ),
        (
            "Professional information",
            {
                "fields": (
                    "id",
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
        return super().get_queryset(request).select_related("user", "user__profile", "reviewed_by")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "show_save": False,
            "show_save_and_continue": False,
            "show_save_and_add_another": False,
            "show_delete": False,
        }
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_review_permission(self, request):
        return request.user.has_perm("accounts.review_brokerprofile")

    @admin.display(description="Identity status")
    def identity_status_display(self, obj):
        try:
            return obj.user.profile.get_identity_status_display()
        except ObjectDoesNotExist:
            return "No profile"

    @admin.display(description="Can create transactions", boolean=True)
    def can_create_transactions_display(self, obj):
        return obj.can_create_transactions

    @admin.display(description="User profile")
    def user_profile_overview(self, obj):
        try:
            profile = obj.user.profile
        except ObjectDoesNotExist:
            return "No reusable user profile is attached."

        profile_link = reverse("admin:accounts_userprofile_change", args=[profile.pk])
        id_image_link = "-"
        if profile.id_image:
            id_image_link = format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">Open uploaded ID</a>',
                profile.id_image.url,
            )

        return format_html(
            "<strong>Profile</strong>: <a href='{}'>Open user profile</a><br>"
            "<strong>Date of birth</strong>: {}<br>"
            "<strong>RFC</strong>: {}<br>"
            "<strong>CURP</strong>: {}<br>"
            "<strong>Address</strong>: {}, {}, {}<br>"
            "<strong>ID type</strong>: {}<br>"
            "<strong>ID image</strong>: {}",
            profile_link,
            profile.date_of_birth or "-",
            profile.rfc or "-",
            profile.curp or "-",
            profile.address_line_1 or "-",
            profile.city or "-",
            profile.state or "-",
            profile.get_id_type_display() or "-",
            id_image_link,
        )

    @admin.display(description="Workflow actions")
    def workflow_actions(self, obj):
        action_map = {
            BrokerApplicationStatus.SUBMITTED: (
                ("Needs info", "request_info"),
                ("Approve", "approve"),
                ("Reject", "reject"),
            ),
            BrokerApplicationStatus.REJECTED: (
                ("Reopen", "reopen"),
            ),
        }

        actions = action_map.get(obj.application_status, ())
        if not actions:
            return "No reviewer actions are available for this status."

        links = []
        for label, action in actions:
            url = reverse(f"admin:accounts_brokerprofile_{action}", args=[obj.pk])
            links.append(
                format_html(
                    '<a class="button" href="{}" style="margin-right: 8px;">{}</a>',
                    url,
                    label,
                )
            )

        return mark_safe("".join(str(link) for link in links))


    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/request-info/",
                self.admin_site.admin_view(self.request_info_view),
                name="accounts_brokerprofile_request_info",
            ),
            path(
                "<path:object_id>/approve/",
                self.admin_site.admin_view(self.approve_view),
                name="accounts_brokerprofile_approve",
            ),
            path(
                "<path:object_id>/reject/",
                self.admin_site.admin_view(self.reject_view),
                name="accounts_brokerprofile_reject",
            ),
            path(
                "<path:object_id>/reopen/",
                self.admin_site.admin_view(self.reopen_view),
                name="accounts_brokerprofile_reopen",
            ),
        ]
        return custom_urls + urls

    def _get_review_target(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404("Broker profile not found.")
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
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": obj,
            "object": obj,
            "title": title,
            "form": form,
            "media": self.media + form.media,
        }
        return TemplateResponse(
            request,
            "admin/accounts/brokerprofile/workflow_action.html",
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
                    change_url = reverse("admin:accounts_brokerprofile_change", args=[obj.pk])
                    return HttpResponseRedirect(change_url)
        else:
            form = form_class()

        return self._render_workflow_form(request, obj, form, title=title)

    def request_info_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=BrokerNeedsInfoForm,
            title="Request More Broker Information",
            success_message="Applicant has been asked for more information.",
            service_call=lambda obj, data: request_broker_application_changes(
                profile=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def reopen_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=BrokerReopenForm,
            title="Reopen Broker Application",
            success_message="Broker application reopened for applicant edits.",
            service_call=lambda obj, data: reopen_broker_profile(
                profile=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def approve_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=BrokerApproveForm,
            title="Approve Broker Application",
            success_message="Broker application approved.",
            service_call=lambda obj, data: approve_broker_profile(
                profile=obj,
                reviewer=request.user,
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )

    def reject_view(self, request, object_id):
        return self._process_workflow_form(
            request,
            object_id,
            form_class=BrokerRejectForm,
            title="Reject Broker Application",
            success_message="Broker application rejected.",
            service_call=lambda obj, data: reject_broker_profile(
                profile=obj,
                reviewer=request.user,
                applicant_message=data["applicant_message"],
                internal_review_notes=data.get("internal_review_notes", ""),
            ),
        )
