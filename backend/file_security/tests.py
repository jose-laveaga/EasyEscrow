from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from file_security.models import FileSecurityReport, FileSecurityStatus


pytestmark = pytest.mark.django_db


def valid_png_bytes():
    output = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(output, format="PNG")
    return output.getvalue()


def test_purchase_agreement_upload_rejects_pdf_extension_with_bad_magic(
    authenticated_broker_client,
    settings,
):
    settings.OPENAI_PURCHASE_AGREEMENT_EXTRACTION_ENABLED = False
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Bad upload workflow",
            "transaction_type": "STANDARD",
        },
        format="json",
    )
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"not a pdf",
        content_type="application/pdf",
    )

    response = authenticated_broker_client.post(
        reverse("transaction-purchase-agreement", args=[create_response.data["id"]]),
        {"file": upload},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "file" in response.data
    report = FileSecurityReport.objects.get(policy_name="purchase_agreement_pdf")
    assert report.status == FileSecurityStatus.REJECTED
    assert report.reason_code == "magic_bytes_not_allowed"
    assert report.original_filename == "purchase-agreement.pdf"


def test_purchase_agreement_upload_records_accepted_security_report(
    authenticated_broker_client,
    settings,
):
    settings.OPENAI_PURCHASE_AGREEMENT_EXTRACTION_ENABLED = False
    create_response = authenticated_broker_client.post(
        reverse("transaction-list-create"),
        {
            "title": "Clean upload workflow",
            "transaction_type": "STANDARD",
        },
        format="json",
    )
    upload = SimpleUploadedFile(
        "purchase-agreement.pdf",
        b"%PDF-1.4 clean purchase agreement",
        content_type="application/pdf",
    )

    response = authenticated_broker_client.post(
        reverse("transaction-purchase-agreement", args=[create_response.data["id"]]),
        {"file": upload},
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    report = FileSecurityReport.objects.get(policy_name="purchase_agreement_pdf")
    assert report.status == FileSecurityStatus.ACCEPTED
    assert report.detected_content_type == "application/pdf"
    assert report.stored_file_name.startswith("private/uploads/purchase-agreements/")
    assert response.data["document"]["file"].endswith(report.stored_file_name)


def test_identity_image_rejects_spoofed_image(api_client, buyer_user):
    api_client.force_authenticate(user=buyer_user)
    upload = SimpleUploadedFile(
        "ine-front.png",
        b"not an image",
        content_type="image/png",
    )

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
            "legal_first_name": "Jose",
            "legal_last_name": "Martinez",
            "id_image": upload,
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id_image" in response.data
    report = FileSecurityReport.objects.get(policy_name="identity_image")
    assert report.status == FileSecurityStatus.REJECTED
    assert report.reason_code == "magic_bytes_not_allowed"


def test_identity_image_accepts_and_reencodes_clean_image(api_client, buyer_user):
    api_client.force_authenticate(user=buyer_user)
    upload = SimpleUploadedFile("ine-front.png", valid_png_bytes(), content_type="image/png")

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
            "legal_first_name": "Jose",
            "legal_last_name": "Martinez",
            "id_image": upload,
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_200_OK
    report = FileSecurityReport.objects.get(policy_name="identity_image")
    assert report.status == FileSecurityStatus.ACCEPTED
    assert report.detected_content_type == "image/png"
    assert report.stored_file_name.startswith("private/uploads/identity-images/")
