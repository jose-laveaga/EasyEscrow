import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from documents.models import (
    DocumentStatus,
    DocumentType,
    PurchaseAgreement,
    PurchaseAgreementExtractionStatus,
    TransactionDocument,
)
from transactions.models import ParticipantRole, Transaction
from transactions.tests.factories import TransactionFactory


pytestmark = pytest.mark.django_db


def test_purchase_agreement_document_can_attach_to_transaction():
    transaction = TransactionFactory()

    document = TransactionDocument.objects.create(
        transaction=transaction,
        uploaded_by_user=transaction.created_by,
        document_type=DocumentType.PURCHASE_AGREEMENT,
        title="Purchase agreement",
        file="transactions/documents/purchase-agreement.pdf",
        is_required=True,
    )
    agreement = PurchaseAgreement.objects.create(
        document=document,
        purchase_price="2500000.00",
        earnest_money_amount="100000.00",
        inspection_days=10,
    )

    assert document.status == DocumentStatus.DRAFT
    assert document.transaction == transaction
    assert document.uploaded_by_user == transaction.created_by
    assert agreement.document == document


def test_broker_can_upload_purchase_agreement(authenticated_broker_client):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Week 4 purchase agreement workflow",
            "transaction_type": "STANDARD",
        },
        format="json",
    )
    transaction_id = create_response.data["id"]
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 test purchase agreement",
        content_type="application/pdf",
    )

    response = authenticated_broker_client.post(
        reverse("transaction-purchase-agreement", args=[transaction_id]),
        {"title": "Signed purchase agreement", "file": upload},
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["document"]["document_type"] == DocumentType.PURCHASE_AGREEMENT
    assert response.data["document"]["version"] == 1
    assert response.data["document"]["is_required"] is True
    assert response.data["extraction_status"] == PurchaseAgreementExtractionStatus.REVIEW_REQUIRED


def test_purchase_agreement_upload_is_required_before_invitations(
    authenticated_broker_client,
    buyer_user,
):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Invitation gate workflow",
            "transaction_type": "STANDARD",
        },
        format="json",
    )
    transaction_id = create_response.data["id"]

    blocked_response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(buyer_user.id),
            "intended_role": ParticipantRole.BUYER,
        },
        format="json",
    )

    assert blocked_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "purchase_agreement" in blocked_response.data

    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 test purchase agreement",
        content_type="application/pdf",
    )
    upload_response = authenticated_broker_client.post(
        reverse("transaction-purchase-agreement", args=[transaction_id]),
        {"file": upload},
        format="multipart",
    )
    assert upload_response.status_code == status.HTTP_201_CREATED

    invite_response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(buyer_user.id),
            "intended_role": ParticipantRole.BUYER,
        },
        format="json",
    )

    assert invite_response.status_code == status.HTTP_201_CREATED


def test_broker_can_confirm_purchase_agreement_terms(authenticated_broker_client):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Agreement confirmation workflow",
            "transaction_type": "STANDARD",
        },
        format="json",
    )
    transaction_id = create_response.data["id"]
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 test purchase agreement",
        content_type="application/pdf",
    )
    authenticated_broker_client.post(
        reverse("transaction-purchase-agreement", args=[transaction_id]),
        {"file": upload},
        format="multipart",
    )

    response = authenticated_broker_client.post(
        reverse("transaction-purchase-agreement-confirm", args=[transaction_id]),
        {
            "purchase_price": "2500000.00",
            "earnest_money_amount": "100000.00",
            "currency": "MXN",
            "seller_names": ["Ana Seller", "Luis Seller"],
            "seller_address": "Av. Reforma 100, Ciudad de Mexico",
            "buyer_names": ["Maria Buyer"],
            "buyer_address": "Calle Durango 25, Ciudad de Mexico",
            "property_address": "Calle Roma 123, Ciudad de Mexico",
            "property_legal_description": "Lot 7, Block 4, Roma Norte subdivision.",
            "closing_date": "2026-06-30",
            "executed_date": "2026-04-27",
            "inspection_days": 10,
            "payment_scheme_summary": "Buyer deposits earnest money, then funds at closing.",
            "payment_milestones": [
                {
                    "label": "Earnest money",
                    "amount": "100000.00",
                    "due": "After acceptance",
                }
            ],
            "contingencies": "Inspection contingency.",
            "special_conditions": "Seller repairs listed fixtures before closing.",
            "disbursement_conditions": "Disburse after signed closing instruction.",
            "disbursement_payees": ["Ana Seller", "Luis Seller"],
            "disbursement_amounts": ["1200000.00", "1200000.00"],
            "disbursement_purposes": ["Seller proceeds", "Seller proceeds"],
            "gf_number": "GF-2026-001",
            "escrow_agent": "EasyEscrow Trust Services",
            "escrow_fee": "15000.00",
            "escrow_bank_account": "EasyEscrow settlement account ending 1234",
            "wire_reference": "TXN-WIRE-001",
            "payee_wire_information": [
                {
                    "payee": "Ana Seller",
                    "bank": "Banco Test",
                    "clabe": "123456789012345678",
                }
            ],
            "broker_commission_allocations": [
                {
                    "broker": "Primary broker",
                    "amount": "50000.00",
                }
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["extraction_status"] == PurchaseAgreementExtractionStatus.CONFIRMED
    assert response.data["purchase_price"] == "2500000.00"
    assert response.data["seller_names"] == ["Ana Seller", "Luis Seller"]
    assert response.data["buyer_names"] == ["Maria Buyer"]
    assert response.data["property_legal_description"] == "Lot 7, Block 4, Roma Norte subdivision."
    assert response.data["payment_milestones"][0]["label"] == "Earnest money"
    assert response.data["disbursement_payees"] == ["Ana Seller", "Luis Seller"]
    assert response.data["gf_number"] == "GF-2026-001"
    assert response.data["payee_wire_information"][0]["payee"] == "Ana Seller"

    transaction = Transaction.objects.get(pk=transaction_id)
    assert transaction.purchase_price == 2500000
    assert transaction.earnest_money_amount == 100000


def test_accepted_participant_can_view_purchase_agreement(
    authenticated_broker_client,
    api_client,
    buyer_user,
):
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Agreement visibility workflow",
            "transaction_type": "STANDARD",
        },
        format="json",
    )
    transaction_id = create_response.data["id"]
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 test purchase agreement",
        content_type="application/pdf",
    )
    authenticated_broker_client.post(
        reverse("transaction-purchase-agreement", args=[transaction_id]),
        {"file": upload},
        format="multipart",
    )
    invite_response = authenticated_broker_client.post(
        reverse("transaction-invitations", args=[transaction_id]),
        {
            "target_user": str(buyer_user.id),
            "intended_role": ParticipantRole.BUYER,
        },
        format="json",
    )

    api_client.force_authenticate(user=buyer_user)
    accept_response = api_client.post(
        reverse("invitation-accept", args=[invite_response.data["id"]]),
        {},
        format="json",
    )
    response = api_client.get(reverse("transaction-purchase-agreement", args=[transaction_id]))

    assert accept_response.status_code == status.HTTP_200_OK
    assert response.status_code == status.HTTP_200_OK
    assert response.data["document"]["document_type"] == DocumentType.PURCHASE_AGREEMENT
