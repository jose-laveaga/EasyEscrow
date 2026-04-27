import pytest
from django.urls import reverse
from rest_framework import status

from accounts.models import IdentityVerificationStatus
from accounts.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


def test_identity_submission_rejects_missing_id_upload(api_client):
    user = UserFactory(email="identity-missing-file@example.com")
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("identity-verification-submit"),
        {
            "date_of_birth": "1990-01-10",
            "state": "Ciudad de Mexico",
            "city": "Ciudad de Mexico",
            "address_line_1": "Av. Reforma 100",
            "postal_code": "06500",
            "rfc": "ABCD123456EF1",
            "id_type": "ine",
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id_image" in response.data
    user.profile.refresh_from_db()
    assert user.profile.status == IdentityVerificationStatus.DRAFT


def test_identity_draft_rejects_invalid_postal_code(api_client):
    user = UserFactory(email="identity-invalid-postal@example.com")
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        reverse("identity-verification"),
        {"postal_code": "invalid"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "postal_code" in response.data


def test_broker_application_submit_rejects_missing_broker_type(api_client):
    user = UserFactory(email="broker-missing-type@example.com")
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("broker-application-submit"),
        {
            "accepted_broker_declaration": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "broker_type" in response.data


def test_staff_without_review_permission_cannot_use_identity_review_admin_action(client):
    applicant = UserFactory(email="identity-review-target@example.com")
    reviewer = UserFactory(email="staff-without-review@example.com", is_staff=True)
    profile = applicant.profile
    profile.status = IdentityVerificationStatus.SUBMITTED
    profile.legal_first_name = "Jose"
    profile.legal_last_name = "Martinez"
    profile.id_type = "ine"
    profile.rfc = "ABCD123456EF1"
    profile.id_image = "accounts/id-images/test.png"
    profile.save()

    client.force_login(reviewer)
    response = client.get(reverse("admin:accounts_userprofile_approve", args=[profile.pk]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
