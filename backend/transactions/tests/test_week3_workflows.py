from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import UserFactory
from transactions.models import (
    Invitation,
    InvitationStatus,
    ParticipantRole,
    Transaction,
    TransactionParticipant,
    TransactionStatus,
    TransactionType,
)


pytestmark = pytest.mark.django_db


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
    confirm_response = client.post(
        reverse("transaction-purchase-agreement-confirm", args=[transaction_id]),
        {
            "purchase_price": "2500000.00",
            "earnest_money_amount": "100000.00",
            "currency": "MXN",
        },
        format="json",
    )
    assert confirm_response.status_code == status.HTTP_200_OK


def test_happy_path_transaction_invitation_workflow(
    authenticated_broker_client,
    buyer_user,
    seller_user,
):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Week 3 escrow workflow",
            "transaction_type": TransactionType.STANDARD,
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    transaction_id = create_response.data["id"]
    _upload_purchase_agreement(authenticated_broker_client, transaction_id)

    buyer_invite_response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(buyer_user.id),
            "intended_role": ParticipantRole.BUYER,
        },
        format="json",
    )
    seller_invite_response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(seller_user.id),
            "intended_role": ParticipantRole.SELLER,
        },
        format="json",
    )

    assert buyer_invite_response.status_code == status.HTTP_201_CREATED
    assert seller_invite_response.status_code == status.HTTP_201_CREATED

    buyer_client = APIClient()
    buyer_client.force_authenticate(user=buyer_user)
    buyer_accept_response = buyer_client.post(
        reverse("invitation-accept", args=[buyer_invite_response.data["id"]]),
        {},
        format="json",
    )

    seller_client = APIClient()
    seller_client.force_authenticate(user=seller_user)
    seller_accept_response = seller_client.post(
        reverse("invitation-accept", args=[seller_invite_response.data["id"]]),
        {},
        format="json",
    )

    assert buyer_accept_response.status_code == status.HTTP_200_OK
    assert seller_accept_response.status_code == status.HTTP_200_OK

    transaction = Transaction.objects.get(pk=transaction_id)
    assert transaction.status == TransactionStatus.PARTIES_CONFIRMED

    assert TransactionParticipant.objects.filter(
        transaction=transaction,
        user=buyer_user,
        role=ParticipantRole.BUYER,
    ).exists()
    assert TransactionParticipant.objects.filter(
        transaction=transaction,
        user=seller_user,
        role=ParticipantRole.SELLER,
    ).exists()


def test_non_broker_cannot_create_transaction(api_client):
    user = UserFactory(email="non-broker@example.com")
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Unauthorized escrow workflow",
            "transaction_type": TransactionType.STANDARD,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_expired_invitation_cannot_be_accepted(
    authenticated_broker_client,
    buyer_user,
):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Expired invite workflow",
            "transaction_type": TransactionType.STANDARD,
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    _upload_purchase_agreement(authenticated_broker_client, create_response.data["id"])

    invite_response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[create_response.data["id"]]),
        {
            "target_user": str(buyer_user.id),
            "intended_role": ParticipantRole.BUYER,
        },
        format="json",
    )
    assert invite_response.status_code == status.HTTP_201_CREATED

    invitation = Invitation.objects.get(pk=invite_response.data["id"])
    invitation.expires_at = timezone.now() - timedelta(minutes=1)
    invitation.save(update_fields=["expires_at"])

    buyer_client = APIClient()
    buyer_client.force_authenticate(user=buyer_user)
    accept_response = buyer_client.post(
        reverse("invitation-accept", args=[invitation.id]),
        {},
        format="json",
    )

    assert accept_response.status_code == status.HTTP_400_BAD_REQUEST

    invitation.refresh_from_db()
    assert invitation.status == InvitationStatus.EXPIRED
    assert not TransactionParticipant.objects.filter(
        transaction_id=create_response.data["id"],
        user=buyer_user,
    ).exists()
