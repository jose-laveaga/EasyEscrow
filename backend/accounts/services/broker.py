from django.db import transaction
from django.utils import timezone

from accounts.models import (
    BrokerProfile,
    BrokerType,
    IdentityStatus,
    UserProfile,
)


@transaction.atomic
def apply_for_broker_status(
    *,
    user,
    broker_type: str,
    identity_verified: bool,
    accepted_broker_declaration: bool,
    date_of_birth=None,
    state: str = "",
    city: str = "",
    address_line_1: str = "",
    address_line_2: str = "",
    postal_code: str = "",
    rfc: str = "",
    curp: str = "",
    id_type: str = "",
    id_image=None,
    brokerage_name: str = "",
    years_of_experience=None,
    primary_market: str = "",
    operating_state: str = "",
    license_or_registration_type: str = "",
    license_or_registration_number: str = "",
    issuing_authority: str = "",
    license_expires_at=None,
    company_legal_name: str = "",
    company_rfc: str = "",
    representative_job_title: str = "",
    has_authority_to_represent: bool = False,
) -> BrokerProfile:
    user_profile, _ = UserProfile.objects.get_or_create(user=user)
    broker_profile, created = BrokerProfile.objects.get_or_create(
        user=user,
        defaults={"broker_type": broker_type},
    )

    if date_of_birth is not None:
        user_profile.date_of_birth = date_of_birth
    if state.strip():
        user_profile.state = state.strip()
    if city.strip():
        user_profile.city = city.strip()
    if address_line_1.strip():
        user_profile.address_line_1 = address_line_1.strip()
    if address_line_2.strip():
        user_profile.address_line_2 = address_line_2.strip()
    if postal_code.strip():
        user_profile.postal_code = postal_code.strip()
    if rfc.strip():
        user_profile.rfc = rfc.strip().upper()
    if curp.strip():
        user_profile.curp = curp.strip().upper()
    if id_type:
        user_profile.id_type = id_type
    if id_image is not None:
        user_profile.id_image = id_image
    user_profile.identity_status = (
        IdentityStatus.VERIFIED if identity_verified else IdentityStatus.PENDING
    )
    user_profile.full_clean()
    user_profile.save()

    broker_profile.broker_type = broker_type
    broker_profile.identity_verified = identity_verified
    broker_profile.brokerage_name = brokerage_name.strip() or broker_profile.brokerage_name
    if years_of_experience is not None:
        broker_profile.years_of_experience = years_of_experience
    broker_profile.primary_market = (
        primary_market.strip()
        or broker_profile.primary_market
        or city.strip()
        or user_profile.city
    )
    broker_profile.operating_state = (
        operating_state.strip()
        or broker_profile.operating_state
        or state.strip()
        or user_profile.state
    )
    broker_profile.license_or_registration_type = (
        license_or_registration_type.strip() or broker_profile.license_or_registration_type
    )
    broker_profile.license_or_registration_number = (
        license_or_registration_number.strip() or broker_profile.license_or_registration_number
    )
    broker_profile.issuing_authority = issuing_authority.strip() or broker_profile.issuing_authority
    if license_expires_at is not None:
        broker_profile.license_expires_at = license_expires_at

    if broker_type == BrokerType.COMPANY_REPRESENTATIVE:
        broker_profile.company_legal_name = company_legal_name.strip()
        broker_profile.company_rfc = company_rfc.strip().upper()
        broker_profile.representative_job_title = representative_job_title.strip()
        broker_profile.has_authority_to_represent = has_authority_to_represent
    else:
        broker_profile.company_legal_name = ""
        broker_profile.company_rfc = ""
        broker_profile.representative_job_title = ""
        broker_profile.has_authority_to_represent = False

    if created:
        broker_profile.manual_review_required = True

    if accepted_broker_declaration and not broker_profile.accepted_broker_declaration_at:
        broker_profile.accepted_broker_declaration_at = timezone.now()

    broker_profile.submit_for_review()
    broker_profile.save()

    return broker_profile


@transaction.atomic
def approve_broker_profile(*, profile: BrokerProfile) -> BrokerProfile:
    profile.approve()
    profile.save()
    return profile


@transaction.atomic
def reject_broker_profile(*, profile: BrokerProfile) -> BrokerProfile:
    profile.reject()
    profile.save()
    return profile
