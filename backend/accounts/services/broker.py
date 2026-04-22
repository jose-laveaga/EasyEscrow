from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    BrokerApplication,
    BrokerApplicationStatus,
    BrokerProfile,
    BrokerType,
    IdentityVerificationStatus,
    UserProfile,
)


BROKER_FIELD_NAMES = (
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
)


def _get_locked_broker_application(user, *, broker_type=None):
    application = (
        BrokerApplication.objects.select_for_update()
        .select_related("user")
        .filter(user=user)
        .order_by("-created_at")
        .first()
    )
    if application:
        return application

    if not broker_type:
        raise ValidationError(
            {"broker_type": "Broker type is required to start a broker application."}
        )

    return BrokerApplication(
        user=user,
        broker_type=broker_type,
        status=BrokerApplicationStatus.DRAFT,
    )


def _get_locked_broker_application_instance(application: BrokerApplication) -> BrokerApplication:
    return (
        BrokerApplication.objects.select_for_update()
        .select_related("user")
        .get(pk=application.pk)
    )


def _get_locked_identity_profile(user) -> UserProfile | None:
    return (
        UserProfile.objects.select_for_update()
        .select_related("user")
        .filter(user=user)
        .first()
    )


def _get_locked_broker_profile(user) -> BrokerProfile | None:
    return (
        BrokerProfile.objects.select_for_update()
        .select_related("user")
        .filter(user=user)
        .first()
    )


def _apply_broker_updates(application: BrokerApplication, data: dict) -> None:
    if "broker_type" in data and data["broker_type"]:
        application.broker_type = data["broker_type"]

    if not application.broker_type:
        raise ValidationError(
            {"broker_type": "Broker type is required to save a broker application."}
        )

    for field_name in BROKER_FIELD_NAMES:
        if field_name not in data or field_name == "broker_type":
            continue

        value = data[field_name]
        if isinstance(value, str):
            value = value.strip()
            if field_name == "company_rfc":
                value = value.upper()
        setattr(application, field_name, value)

    if application.broker_type == BrokerType.INDIVIDUAL:
        application.company_legal_name = ""
        application.company_rfc = ""
        application.representative_job_title = ""
        application.has_authority_to_represent = False


def _apply_declaration_state(application: BrokerApplication, data: dict) -> None:
    if "accepted_broker_declaration" not in data:
        return

    accepted = data["accepted_broker_declaration"]
    if accepted:
        if not application.accepted_broker_declaration_at:
            application.accepted_broker_declaration_at = timezone.now()
        return

    if application.is_editable_by_applicant:
        application.accepted_broker_declaration_at = None


def _validate_submission_requirements(
    application: BrokerApplication,
    identity_profile: UserProfile | None,
) -> None:
    errors = {}

    if not identity_profile:
        errors["identity_verification"] = (
            "Submit identity verification before submitting a broker application."
        )
    elif not identity_profile.has_submitted_form:
        errors["identity_verification"] = (
            "Identity verification must be submitted before submitting a broker application."
        )

    if not application.broker_type:
        errors["broker_type"] = "Broker type is required before submitting a broker application."

    if errors:
        raise ValidationError(errors)


def _upsert_broker_profile_from_application(
    *,
    application: BrokerApplication,
    reviewer,
) -> BrokerProfile:
    profile = _get_locked_broker_profile(application.user)
    if profile is None:
        profile = BrokerProfile(
            user=application.user,
            broker_type=application.broker_type,
        )

    profile.sync_from_application(
        application=application,
        reviewer=reviewer,
    )
    profile.full_clean()
    profile.save()
    return profile


@transaction.atomic
def save_broker_application_draft(*, user, **data) -> BrokerApplication:
    broker_type = data.get("broker_type")
    application = _get_locked_broker_application(user, broker_type=broker_type)

    application.save_draft()
    _apply_broker_updates(application, data)
    _apply_declaration_state(application, data)
    application.full_clean()
    application.save()

    return application


@transaction.atomic
def submit_broker_application(*, user, **data) -> BrokerApplication:
    broker_type = data.get("broker_type")
    application = _get_locked_broker_application(user, broker_type=broker_type)
    identity_profile = _get_locked_identity_profile(user)

    _apply_broker_updates(application, data)
    _apply_declaration_state(application, data)
    _validate_submission_requirements(application, identity_profile)
    application.submit()
    application.save()

    return application


@transaction.atomic
def request_broker_application_changes(
    *,
    application: BrokerApplication,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> BrokerApplication:
    application = _get_locked_broker_application_instance(application)
    application.request_changes(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    application.full_clean()
    application.save()
    return application


@transaction.atomic
def reopen_broker_application(
    *,
    application: BrokerApplication,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> BrokerApplication:
    application = _get_locked_broker_application_instance(application)
    application.reopen(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    application.full_clean()
    application.save()
    return application


@transaction.atomic
def approve_broker_application(
    *,
    application: BrokerApplication,
    reviewer,
    internal_review_notes: str = "",
) -> BrokerApplication:
    application = _get_locked_broker_application_instance(application)
    identity_profile = _get_locked_identity_profile(application.user)

    if not identity_profile or identity_profile.status != IdentityVerificationStatus.VERIFIED:
        raise ValidationError(
            {"identity_verification": "The applicant's identity must be verified before broker approval."}
        )

    application.approve(
        reviewer=reviewer,
        internal_review_notes=internal_review_notes,
    )
    application.full_clean()
    application.save()
    _upsert_broker_profile_from_application(
        application=application,
        reviewer=reviewer,
    )

    return application


@transaction.atomic
def reject_broker_application(
    *,
    application: BrokerApplication,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> BrokerApplication:
    application = _get_locked_broker_application_instance(application)
    application.reject(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    application.full_clean()
    application.save()
    return application


def get_broker_application_for_user(user) -> BrokerApplication | None:
    return (
        BrokerApplication.objects.select_related("user")
        .filter(user=user)
        .order_by("-created_at")
        .first()
    )


def get_broker_profile_for_user(user) -> BrokerProfile | None:
    return (
        BrokerProfile.objects.select_related("user", "user__profile", "approved_application")
        .filter(user=user)
        .first()
    )


def user_can_create_transactions(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False

    return BrokerProfile.objects.filter(
        user_id=user.pk,
        is_active_broker=True,
        user__profile__status=IdentityVerificationStatus.VERIFIED,
    ).exists()


def apply_for_broker_status(*, user, **data) -> BrokerApplication:
    return submit_broker_application(user=user, **data)
