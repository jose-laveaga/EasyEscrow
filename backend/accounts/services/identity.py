from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    UserProfile,
    IdentityVerificationStatus,
)


PROFILE_FIELD_NAMES = (
    "date_of_birth",
    "state",
    "city",
    "address_line_1",
    "address_line_2",
    "postal_code",
)

IDENTITY_FIELD_NAMES = (
    "legal_first_name",
    "legal_middle_name",
    "legal_last_name",
    "rfc",
    "curp",
    "id_type",
    "id_image",
)


def _get_locked_user_profile(user):
    try:
        return UserProfile.objects.select_for_update().select_related("user").get(user=user)
    except UserProfile.DoesNotExist:
        return UserProfile(user=user, status=IdentityVerificationStatus.DRAFT)


def _get_locked_user_profile_instance(user_profile: UserProfile) -> UserProfile:
    return (
        UserProfile.objects.select_for_update()
        .get(pk=user_profile.pk)
    )


def _apply_profile_updates(user_profile: UserProfile, data: dict) -> None:
    for field_name in PROFILE_FIELD_NAMES:
        if field_name not in data:
            continue

        value = data[field_name]
        if isinstance(value, str):
            value = value.strip()
        setattr(user_profile, field_name, value)


def _apply_identity_updates(user_profile: UserProfile, data: dict) -> None:
    for field_name in IDENTITY_FIELD_NAMES:
        if field_name not in data:
            continue

        value = data[field_name]
        if isinstance(value, str):
            value = value.strip()
            if field_name in {"rfc", "curp"}:
                value = value.upper()
        setattr(user_profile, field_name, value)


def _prefill_identity_names(user_profile: UserProfile, user) -> None:
    if not user_profile.legal_first_name and user.first_name:
        user_profile.legal_first_name = user.first_name.strip()
    if not user_profile.legal_middle_name and user.middle_name:
        user_profile.legal_middle_name = user.middle_name.strip()
    if not user_profile.legal_last_name and user.last_name:
        user_profile.legal_last_name = user.last_name.strip()


def _save_identity_model(user_profile: UserProfile) -> None:
    user_profile.full_clean()
    user_profile.save()


def _validate_identity_submission_requirements(
    user_profile: UserProfile,
) -> None:
    errors = {}

    if not user_profile.date_of_birth:
        errors["date_of_birth"] = "Date of birth is required before submitting identity verification."
    if not user_profile.state:
        errors["state"] = "State is required before submitting identity verification."
    if not user_profile.city:
        errors["city"] = "City is required before submitting identity verification."
    if not user_profile.address_line_1:
        errors["address_line_1"] = "Address line 1 is required before submitting identity verification."
    if not user_profile.postal_code:
        errors["postal_code"] = "Postal code is required before submitting identity verification."
    if not user_profile.id_type:
        errors["id_type"] = "Government ID type is required before submitting identity verification."
    if not user_profile.id_image:
        errors["id_image"] = "Government ID image is required before submitting identity verification."
    if not (user_profile.rfc or user_profile.curp):
        errors["non_field_errors"] = [
            "Provide at least one government identifier before submitting identity verification."
        ]

    if errors:
        raise ValidationError(errors)


@transaction.atomic
def save_identity_verification_draft(*, user, **data) -> UserProfile:
    user_profile = _get_locked_user_profile(user)

    user_profile.save_draft()
    _prefill_identity_names(user_profile, user)
    _apply_profile_updates(user_profile, data)
    _apply_identity_updates(user_profile, data)
    _save_identity_model(user_profile)

    return user_profile


@transaction.atomic
def submit_identity_verification(*, user, **data) -> UserProfile:
    user_profile = _get_locked_user_profile(user)

    _prefill_identity_names(user_profile, user)
    _apply_profile_updates(user_profile, data)
    _apply_identity_updates(user_profile, data)
    _validate_identity_submission_requirements(user_profile)
    user_profile.submit()
    user_profile.profile_completed_at = user_profile.profile_completed_at or timezone.now()
    _save_identity_model(user_profile)

    return user_profile


@transaction.atomic
def request_identity_verification_changes(
    *,
    user_profile: UserProfile,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> UserProfile:
    user_profile = _get_locked_user_profile_instance(user_profile)
    user_profile.request_changes(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    _save_identity_model(user_profile)
    return user_profile


@transaction.atomic
def approve_identity_verification(
    *,
    user_profile: UserProfile,
    reviewer,
    internal_review_notes: str = "",
) -> UserProfile:
    user_profile = _get_locked_user_profile_instance(user_profile)
    user_profile.approve(
        reviewer=reviewer,
        internal_review_notes=internal_review_notes,
    )
    _save_identity_model(user_profile)
    return user_profile


@transaction.atomic
def reject_identity_verification(
    *,
    user_profile: UserProfile,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> UserProfile:
    user_profile = _get_locked_user_profile_instance(user_profile)
    user_profile.reject(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    _save_identity_model(user_profile)
    return user_profile


@transaction.atomic
def reopen_identity_verification(
    *,
    user_profile: UserProfile,
    reviewer,
    applicant_message: str,
    internal_review_notes: str = "",
) -> UserProfile:
    user_profile = _get_locked_user_profile_instance(user_profile)
    user_profile.reopen(
        reviewer=reviewer,
        applicant_message=applicant_message,
        internal_review_notes=internal_review_notes,
    )
    _save_identity_model(user_profile)
    return user_profile


def get_identity_verification_for_user(user) -> UserProfile | None:
    try:
        return (
            UserProfile.objects.select_related("user", "reviewed_by")
            .get(user=user)
        )
    except (UserProfile.DoesNotExist, ObjectDoesNotExist):
        return None
