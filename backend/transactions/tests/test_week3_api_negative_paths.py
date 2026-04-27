import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from accounts.tests.factories import UserFactory
from transactions.models import ParticipantRole, TransactionParticipant, TransactionType


pytestmark = pytest.mark.django_db


def _create_transaction(client, *, title="Negative path transaction"):
    response = client.post(
        reverse("transaction-list-create"),
        {
            "title": title,
            "transaction_type": TransactionType.STANDARD,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data["id"]


def _upload_purchase_agreement(client, transaction_id):
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 test purchase agreement",
        content_type="application/pdf",
    )
    response = client.post(
        reverse("transaction-purchase-agreement", args=[transaction_id]),
        {"file": upload},
        format="multipart",
    )
    assert response.status_code == status.HTTP_201_CREATED


def _create_invitation(client, transaction_id, user, role):
    response = client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(user.id),
            "intended_role": role,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data["id"]


def test_wrong_user_cannot_accept_invitation(
    authenticated_broker_client,
    api_client,
    buyer_user,
):
    transaction_id = _create_transaction(authenticated_broker_client)
    _upload_purchase_agreement(authenticated_broker_client, transaction_id)
    invitation_id = _create_invitation(
        authenticated_broker_client,
        transaction_id,
        buyer_user,
        ParticipantRole.BUYER,
    )
    other_user = UserFactory(email="wrong-user@example.com")
    api_client.force_authenticate(user=other_user)

    response = api_client.post(
        reverse("invitation-accept", args=[invitation_id]),
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not TransactionParticipant.objects.filter(
        transaction_id=transaction_id,
        user=other_user,
    ).exists()


def test_duplicate_pending_invitation_for_same_user_is_rejected(
    authenticated_broker_client,
    buyer_user,
):
    transaction_id = _create_transaction(authenticated_broker_client)
    _upload_purchase_agreement(authenticated_broker_client, transaction_id)
    _create_invitation(
        authenticated_broker_client,
        transaction_id,
        buyer_user,
        ParticipantRole.BUYER,
    )

    response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(buyer_user.id),
            "intended_role": ParticipantRole.SELLER,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "target_user" in response.data


def test_duplicate_pending_invitation_for_same_role_is_rejected(
    authenticated_broker_client,
    buyer_user,
):
    transaction_id = _create_transaction(authenticated_broker_client)
    _upload_purchase_agreement(authenticated_broker_client, transaction_id)
    second_buyer = UserFactory(email="second-buyer@example.com")
    _create_invitation(
        authenticated_broker_client,
        transaction_id,
        buyer_user,
        ParticipantRole.BUYER,
    )

    response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(second_buyer.id),
            "intended_role": ParticipantRole.BUYER,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "intended_role" in response.data


def test_user_who_cannot_see_transaction_cannot_read_detail_or_participants(
    authenticated_broker_client,
    api_client,
):
    transaction_id = _create_transaction(authenticated_broker_client)
    outsider = UserFactory(email="outsider@example.com")
    api_client.force_authenticate(user=outsider)

    detail_response = api_client.get(reverse("transaction-detail", args=[transaction_id]))
    participants_response = api_client.get(
        reverse("transaction-participants", args=[transaction_id])
    )

    assert detail_response.status_code == status.HTTP_404_NOT_FOUND
    assert participants_response.status_code == status.HTTP_404_NOT_FOUND
