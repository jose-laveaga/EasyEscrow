import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.tests.factories import EligibleBrokerUserFactory
from documents.models import PurchaseAgreement
from transactions.models import (
    CommissionAgreementStatus,
    CommissionBasis,
    CommissionPayableEvent,
    CommissionPaymentSource,
    ParticipantRole,
    TransactionType,
)


pytestmark = pytest.mark.django_db


def _create_double_broker_transaction(client):
    response = client.post(
        reverse("transaction-list-create"),
        {
            "title": "Double broker commission workflow",
            "transaction_type": TransactionType.DOUBLE_BROKER,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data["id"]


def _upload_and_confirm_purchase_agreement(client, transaction_id):
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 test purchase agreement",
        content_type="application/pdf",
    )
    upload_response = client.post(
        reverse("transaction-purchase-agreement", args=[transaction_id]),
        {"file": upload},
        format="multipart",
    )
    assert upload_response.status_code == status.HTTP_201_CREATED

    confirm_response = client.post(
        reverse("transaction-purchase-agreement-confirm", args=[transaction_id]),
        {
            "purchase_price": "5000000.00",
            "earnest_money_amount": "250000.00",
            "currency": "MXN",
        },
        format="json",
    )
    assert confirm_response.status_code == status.HTTP_200_OK


def _invite_and_accept_cooperating_broker(primary_client, transaction_id, cooperating_broker):
    invite_response = primary_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(cooperating_broker.id),
            "intended_role": ParticipantRole.COOPERATING_BROKER,
        },
        format="json",
    )
    assert invite_response.status_code == status.HTTP_201_CREATED

    cooperating_client = APIClient()
    cooperating_client.force_authenticate(user=cooperating_broker)
    accept_response = cooperating_client.post(
        reverse("invitation-accept", args=[invite_response.data["id"]]),
        {},
        format="json",
    )
    assert accept_response.status_code == status.HTTP_200_OK
    return cooperating_client


def test_double_broker_commission_terms_are_proposed_and_accepted(authenticated_broker_client):
    cooperating_broker = EligibleBrokerUserFactory(email="cooperating@example.com")
    transaction_id = _create_double_broker_transaction(authenticated_broker_client)
    _upload_and_confirm_purchase_agreement(authenticated_broker_client, transaction_id)

    premature_response = authenticated_broker_client.post(
        reverse("transaction-commission-agreement", args=[transaction_id]),
        {
            "commission_basis": CommissionBasis.FIXED_AMOUNT,
            "total_commission_amount": "150000.00",
        },
        format="json",
    )
    assert premature_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "cooperating_broker" in premature_response.data

    cooperating_client = _invite_and_accept_cooperating_broker(
        authenticated_broker_client,
        transaction_id,
        cooperating_broker,
    )

    propose_response = authenticated_broker_client.post(
        reverse("transaction-commission-agreement", args=[transaction_id]),
        {
            "commission_basis": CommissionBasis.FIXED_AMOUNT,
            "total_commission_amount": "150000.00",
            "currency": "MXN",
            "primary_broker_share_amount": "75000.00",
            "primary_broker_share_percentage": "50.0000",
            "cooperating_broker_share_amount": "75000.00",
            "cooperating_broker_share_percentage": "50.0000",
            "payment_source": CommissionPaymentSource.SELLER_PROCEEDS,
            "payable_event": CommissionPayableEvent.AT_CLOSING,
            "notes": "Commission paid directly from escrow at closing.",
        },
        format="json",
    )
    assert propose_response.status_code == status.HTTP_201_CREATED
    assert propose_response.data["status"] == CommissionAgreementStatus.PROPOSED
    assert propose_response.data["total_commission_amount"] == "150000.00"
    assert propose_response.data["cooperating_broker_share_amount"] == "75000.00"

    accept_response = cooperating_client.post(
        reverse("transaction-commission-agreement-accept", args=[transaction_id]),
        {},
        format="json",
    )
    assert accept_response.status_code == status.HTTP_200_OK
    assert accept_response.data["status"] == CommissionAgreementStatus.ACCEPTED
    assert accept_response.data["accepted_by_user"]["email"] == cooperating_broker.email

    purchase_agreement = PurchaseAgreement.objects.get(document__transaction_id=transaction_id)
    assert purchase_agreement.broker_commission_allocations[0]["share_amount"] == "75000.00"
    assert purchase_agreement.broker_commission_allocations[1]["broker_email"] == cooperating_broker.email


def test_standard_transaction_rejects_commission_agreement(authenticated_broker_client):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Standard commission workflow",
            "transaction_type": TransactionType.STANDARD,
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    response = authenticated_broker_client.post(
        reverse("transaction-commission-agreement", args=[create_response.data["id"]]),
        {
            "commission_basis": CommissionBasis.FIXED_AMOUNT,
            "total_commission_amount": "150000.00",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "transaction_type" in response.data
