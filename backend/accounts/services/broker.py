from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import BrokerApplicationStatus, BrokerProfile, BrokerType, UserProfile


PROFILE_FIELD_NAMES = (
    "date_of_birth",
    "state",
    "city",
    "address_line_1",
    "address_line_2",
    "postal_code",
    "rfc",
    "curp",
    "id_type",
    "id_image",
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


def _get_locked_user_profile(user):
    try:
        return UserProfile.objects.select_for_update().get(user=user)
    except UserProfile.DoesNotExist:
        return UserProfile(user=user)


def _get_locked_broker_profile(user, *, broker_type=None):
    try:
        return BrokerProfile.objects.select_for_update().select_related("user").get(user=user)
    except BrokerProfile.DoesNotExist:
        if not broker_type:
            raise ValidationError(
                {"broker_type": "Broker type is required to start a broker application."}
            )
        return BrokerProfile(
            user=user,
            broker_type=broker_type,
            application_status=BrokerApplicationStatus.DRAFT,
        )


def _get_locked_profile_instance(profile: BrokerProfile) -> BrokerProfile:
    return (
        BrokerProfile.objects.select_for_update()
        .select_related("user")
        .get(pk=profile.pk)
    )


def _apply_profile_updates(user_profile: UserProfile, data: dict) -> None:
    for field_name in PROFILE_FIELD_NAMES:
        if field_name not in data:
            continue

        value = data[field_name]
        if isinstance(value, str):
            value = value.strip()
            if field_name in {"rfc", "curp"}:
                value = value.upper()
        setattr(user_profile, field_name, value)


def _apply_broker_updates(broker_profile: BrokerProfile, data: dict) -> None:
    if "broker_type" in data and data["broker_type"]:
        broker_profile.broker_type = data["broker_type"]

    if not broker_profile.broker_type:
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
        setattr(broker_profile, field_name, value)

    if broker_profile.broker_type == BrokerType.INDIVIDUAL:
        broker_profile.company_legal_name = ""
        broker_profile.company_rfc = ""
        broker_profile.representative_job_title = ""
        broker_profile.has_authority_to_represent = False


def _apply_declaration_state(broker_profile: BrokerProfile, data: dict) -> None:
    if "accepted_broker_declaration" not in data:
        return

    accepted = data["accepted_broker_declaration"]
    if accepted:
        if not broker_profile.accepted_broker_declaration_at:
            broker_profile.accepted_broker_declaration_at = timezone.now()
        return

    if broker_profile.is_editable_by_applicant:
        broker_profile.accepted_broker_declaration_at = None


def _save_application_models(user_profile: UserProfile, broker_profile: BrokerProfile) -> None:
    user_profile.full_clean()
    user_profile.save()
    broker_profile.full_clean()
    broker_profile.save()


def _validate_submission_requirements(
    user_profile: UserProfile,
    broker_profile: BrokerProfile,
) -> None:
    errors = {}

    if not user_profile.state:
        errors["state"] = "State is required before submitting a broker application."
    if not user_profile.city:
        errors["city"] = "City is required before submitting a broker application."
    if not any([user_profile.rfc, user_profile.curp, user_profile.id_image]):
        errors["non_field_errors"] = [
            "Provide at least one reusable identity document or identifier before submission."
        ]
    if not broker_profile.broker_type:
        errors["broker_type"] = "Broker type is required before submitting a broker application."

    if errors:
        raise ValidationError(errors)


@transaction.atomic
def save_broker_application_draft(*, user, **data) -> BrokerProfile:
    broker_type = data.get("broker_type")
    user_profile = _get_locked_user_profile(user)
    broker_profile = _get_locked_broker_profile(user, broker_type=broker_type)

    broker_profile.save_draft()
    _apply_profile_updates(user_profile, data)
    _apply_broker_updates(broker_profile, data)
    _apply_declaration_state(broker_profile, data)
    _save_application_models(user_profile, broker_profile)

    return broker_profile


@transaction.atomic
def submit_broker_application(*, user, **data) -> BrokerProfile:
    broker_type = data.get("broker_type")
    user_profile = _get_locked_user_profile(user)
    broker_profile = _get_locked_broker_profile(user, broker_type=broker_type)

    _apply_profile_updates(user_profile, data)
    _apply_broker_updates(broker_profile, data)
    _apply_declaration_state(broker_profile, data)
    user_profile.full_clean()
    user_profile.save()
    _validate_submission_requirements(user_profile, broker_profile)
    broker_profile.submit()
    broker_profile.save()

    return broker_profile


@transaction.atomic
def request_broker_application_changes(
    *,
    profile: BrokerProfile,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> BrokerProfile:
    profile = _get_locked_profile_instance(profile)
    profile.request_changes(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    profile.full_clean()
    profile.save()
    return profile


@transaction.atomic
def reopen_broker_profile(
    *,
    profile: BrokerProfile,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> BrokerProfile:
    profile = _get_locked_profile_instance(profile)
    profile.reopen(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    profile.full_clean()
    profile.save()
    return profile


@transaction.atomic
def approve_broker_profile(
    *,
    profile: BrokerProfile,
    reviewer,
    internal_review_notes: str = "",
) -> BrokerProfile:
    profile = _get_locked_profile_instance(profile)
    profile.approve(
        reviewer=reviewer,
        internal_review_notes=internal_review_notes,
    )
    profile.full_clean()
    profile.save()
    return profile


@transaction.atomic
def reject_broker_profile(
    *,
    profile: BrokerProfile,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> BrokerProfile:
    profile = _get_locked_profile_instance(profile)
    profile.reject(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    profile.full_clean()
    profile.save()
    return profile


def get_broker_application_for_user(user) -> BrokerProfile | None:
    try:
        return user.broker_profile
    except ObjectDoesNotExist:
        return None


def user_can_create_transactions(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False

    profile = get_broker_application_for_user(user)
    return bool(profile and profile.can_create_transactions)


def apply_for_broker_status(*, user, **data) -> BrokerProfile:
    return submit_broker_application(user=user, **data)
