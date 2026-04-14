# accounts/services/broker.py
from django.utils import timezone

from accounts.models import BrokerProfile, BrokerType
from django.db import transaction


@transaction.atomic
def apply_for_broker_status(
    *,
    user,
    broker_type: str,
    rfc: str,
    state: str,
    city: str,
    identity_verified: bool,
    accepted_broker_declaration: bool,
    brokerage_name: str = "",
    certification_name: str = "",
    certification_number: str = "",
    company_legal_name: str = "",
    company_rfc: str = "",
    representative_job_title: str = "",
    has_authority_to_represent: bool = False,
) -> BrokerProfile:
    profile, _ = BrokerProfile.objects.get_or_create(user=user)

    profile.broker_type = broker_type
    profile.rfc = rfc.strip().upper()
    profile.state = state.strip()
    profile.city = city.strip()
    profile.identity_verified = identity_verified

    profile.brokerage_name = brokerage_name.strip()
    profile.certification_name = certification_name.strip()
    profile.certification_number = certification_number.strip()

    if broker_type == BrokerType.COMPANY_REPRESENTATIVE:
        profile.company_legal_name = company_legal_name.strip()
        profile.company_rfc = company_rfc.strip().upper()
        profile.representative_job_title = representative_job_title.strip()
        profile.has_authority_to_represent = has_authority_to_represent
    else:
        profile.company_legal_name = ""
        profile.company_rfc = ""
        profile.representative_job_title = ""
        profile.has_authority_to_represent = False

    if accepted_broker_declaration and not profile.accepted_broker_declaration_at:
        profile.accepted_broker_declaration_at = timezone.now()

    profile.submit_for_review()
    profile.save()

    return profile


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