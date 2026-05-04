import shutil
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import BrokerApplicationStatus, BrokerType, IdentityVerificationStatus, User
from accounts.services.broker import (
    approve_broker_application,
    get_broker_profile_for_user,
    reopen_broker_application,
    reject_broker_application,
    request_broker_application_changes,
    save_broker_application_draft,
    submit_broker_application,
    user_can_create_transactions,
)
from accounts.services.identity import (
    approve_identity_verification,
    request_identity_verification_changes,
    save_identity_verification_draft,
    submit_identity_verification,
)


class WorkflowFixturesMixin:
    def identity_payload(self):
        return {
            "date_of_birth": "1990-01-10",
            "state": "Ciudad de Mexico",
            "city": "Ciudad de Mexico",
            "address_line_1": "Av. Reforma 100",
            "address_line_2": "Piso 4",
            "postal_code": "06500",
            "rfc": "ABCD123456EF1",
            "id_type": "ine",
        }

    def identity_file(self, name="ine-front.png"):
        output = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(output, format="PNG")
        return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")

    def broker_payload(self):
        return {
            "broker_type": BrokerType.INDIVIDUAL,
            "brokerage_name": "Escrow Brokers MX",
            "years_of_experience": 8,
            "primary_market": "Residential resale",
            "operating_state": "Ciudad de Mexico",
            "license_or_registration_type": "State broker license",
            "license_or_registration_number": "CDMX-123456",
            "issuing_authority": "Colegio Inmobiliario",
        }


class TempMediaMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._temp_media_root = tempfile.mkdtemp(prefix="easyescrow-test-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._temp_media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._temp_media_root, ignore_errors=True)
        super().tearDownClass()


class BrokerWorkflowServiceTests(TempMediaMixin, WorkflowFixturesMixin, APITestCase):
    def setUp(self):
        self.applicant = User.objects.create_user(
            email="broker@example.com",
            password="testpass123",
            first_name="Jose",
            middle_name="Antonio",
            last_name="Martinez Lopez",
        )
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com",
            password="testpass123",
            is_staff=True,
        )

    def test_user_profile_is_created_for_new_users(self):
        profile = self.applicant.profile

        self.assertEqual(profile.user_id, self.applicant.id)
        self.assertEqual(profile.status, IdentityVerificationStatus.DRAFT)
        self.assertFalse(profile.is_identity_verified)

    def _submit_identity_verification(self):
        payload = self.identity_payload()
        payload["id_image"] = self.identity_file()
        return submit_identity_verification(user=self.applicant, **payload)

    def test_identity_verification_can_save_draft_then_submit(self):
        verification = save_identity_verification_draft(
            user=self.applicant,
            **self.identity_payload(),
        )

        self.assertEqual(verification.status, IdentityVerificationStatus.DRAFT)
        self.assertFalse(verification.is_identity_verified)
        self.assertEqual(verification.legal_first_name, "Jose")
        self.assertEqual(verification.legal_middle_name, "Antonio")
        self.assertEqual(verification.legal_last_name, "Martinez Lopez")

        verification = self._submit_identity_verification()
        verification.refresh_from_db()
        self.applicant.refresh_from_db()

        self.assertEqual(verification.status, IdentityVerificationStatus.SUBMITTED)
        self.assertIsNotNone(verification.submitted_at)
        self.assertIsNotNone(self.applicant.profile.profile_completed_at)

    def test_broker_application_requires_identity_submission(self):
        with self.assertRaises(ValidationError):
            submit_broker_application(
                user=self.applicant,
                accepted_broker_declaration=True,
                **self.broker_payload(),
            )

    def test_applicant_can_save_broker_draft_then_submit_after_identity_submission(self):
        self._submit_identity_verification()

        application = save_broker_application_draft(
            user=self.applicant,
            **self.broker_payload(),
        )

        self.assertEqual(application.status, BrokerApplicationStatus.DRAFT)

        application = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
        )
        application.refresh_from_db()

        self.assertEqual(application.status, BrokerApplicationStatus.SUBMITTED)
        self.assertIsNotNone(application.submitted_at)

    def test_reviewer_can_request_info_and_applicant_can_resubmit(self):
        self._submit_identity_verification()
        application = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
            **self.broker_payload(),
        )

        application = request_broker_application_changes(
            application=application,
            reviewer=self.reviewer,
            applicant_message="Please clarify your primary market.",
            internal_review_notes="Primary market description is too broad.",
        )
        application.refresh_from_db()

        self.assertEqual(application.status, BrokerApplicationStatus.NEEDS_INFO)
        self.assertEqual(application.applicant_message, "Please clarify your primary market.")
        self.assertEqual(application.reviewed_by, self.reviewer)

        application = save_broker_application_draft(
            user=self.applicant,
            primary_market="Residential and luxury resale",
        )
        self.assertEqual(application.status, BrokerApplicationStatus.DRAFT)

        application = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
        )
        application.refresh_from_db()

        self.assertEqual(application.status, BrokerApplicationStatus.SUBMITTED)
        self.assertEqual(application.applicant_message, "")

    def test_approval_requires_verified_identity_and_creates_separate_broker_profile(self):
        identity_verification = self._submit_identity_verification()
        application = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
            **self.broker_payload(),
        )

        with self.assertRaises(ValidationError):
            approve_broker_application(application=application, reviewer=self.reviewer)

        approve_identity_verification(
            user_profile=identity_verification,
            reviewer=self.reviewer,
            internal_review_notes="Documents match the applicant record.",
        )

        application = approve_broker_application(
            application=application,
            reviewer=self.reviewer,
            internal_review_notes="Broker application approved.",
        )
        application.refresh_from_db()

        broker_profile = get_broker_profile_for_user(self.applicant)

        self.assertEqual(application.status, BrokerApplicationStatus.APPROVED)
        self.assertIsNotNone(broker_profile)
        self.assertEqual(broker_profile.approved_application_id, application.id)
        self.assertEqual(broker_profile.user.profile.user_id, self.applicant.id)
        self.assertTrue(broker_profile.can_create_transactions)
        self.assertTrue(user_can_create_transactions(self.applicant))

    def test_reviewer_can_reopen_rejected_application(self):
        self._submit_identity_verification()
        application = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
            **self.broker_payload(),
        )

        application = reject_broker_application(
            application=application,
            reviewer=self.reviewer,
            applicant_message="Not enough licensing detail for approval.",
            internal_review_notes="Please reopen after the applicant updates licensing data.",
        )
        application.refresh_from_db()
        self.assertEqual(application.status, BrokerApplicationStatus.REJECTED)

        application = reopen_broker_application(
            application=application,
            reviewer=self.reviewer,
            applicant_message="Application reopened. Please update your licensing data and resubmit.",
            internal_review_notes="Reopened after manual override.",
        )
        application.refresh_from_db()

        self.assertEqual(application.status, BrokerApplicationStatus.DRAFT)
        self.assertEqual(
            application.applicant_message,
            "Application reopened. Please update your licensing data and resubmit.",
        )
        self.assertEqual(application.reviewed_by, self.reviewer)
        self.assertFalse(user_can_create_transactions(self.applicant))

    def test_identity_review_can_request_changes_before_broker_submission(self):
        verification = self._submit_identity_verification()

        verification = request_identity_verification_changes(
            user_profile=verification,
            reviewer=self.reviewer,
            applicant_message="Please upload a clearer ID image.",
            internal_review_notes="Current upload is unreadable.",
        )
        verification.refresh_from_db()

        self.assertEqual(verification.status, IdentityVerificationStatus.NEEDS_INFO)
        self.assertEqual(verification.applicant_message, "Please upload a clearer ID image.")

        with self.assertRaises(ValidationError):
            submit_broker_application(
                user=self.applicant,
                accepted_broker_declaration=True,
                **self.broker_payload(),
            )


class BrokerWorkflowApiTests(TempMediaMixin, WorkflowFixturesMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="api-broker@example.com",
            password="testpass123",
            first_name="Jose",
            middle_name="Antonio",
            last_name="Martinez Lopez",
        )
        self.client.force_authenticate(user=self.user)

    def _submit_identity_verification_via_service(self):
        payload = self.identity_payload()
        payload["id_image"] = self.identity_file()
        return submit_identity_verification(user=self.user, **payload)

    def test_profile_endpoint_returns_auto_created_profile(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], "Jose")
        self.assertEqual(response.data["middle_name"], "Antonio")
        self.assertEqual(response.data["last_name"], "Martinez Lopez")
        self.assertEqual(response.data["city"], "")

    def test_profile_endpoint_patch_updates_user_and_profile_fields(self):
        response = self.client.patch(
            reverse("profile"),
            {
                "first_name": "Jose Luis",
                "middle_name": "",
                "last_name": "Martinez",
                "phone": "+521234567890",
                "state": "Jalisco",
                "city": "Guadalajara",
                "address_line_1": "Av. Vallarta 123",
                "postal_code": "44100",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Jose Luis")
        self.assertEqual(response.data["middle_name"], "")
        self.assertEqual(response.data["last_name"], "Martinez")
        self.assertEqual(response.data["phone"], "+521234567890")
        self.assertEqual(response.data["state"], "Jalisco")
        self.assertEqual(response.data["city"], "Guadalajara")

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jose Luis")
        self.assertEqual(self.user.middle_name, "")
        self.assertEqual(self.user.last_name, "Martinez")
        self.assertEqual(self.user.phone, "+521234567890")
        self.assertEqual(self.user.profile.postal_code, "44100")

    def test_profile_endpoint_rejects_invalid_payload(self):
        response = self.client.patch(
            reverse("profile"),
            {
                "first_name": "J",
                "phone": "123",
                "postal_code": "ABCDE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data)
        self.assertIn("phone", response.data)
        self.assertIn("postal_code", response.data)

    def test_identity_verification_endpoints_support_draft_and_submit(self):
        draft_response = self.client.patch(
            reverse("identity-verification"),
            self.identity_payload(),
            format="json",
        )
        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            draft_response.data["status"],
            IdentityVerificationStatus.DRAFT,
        )
        self.assertEqual(draft_response.data["legal_first_name"], "Jose")
        self.assertEqual(draft_response.data["legal_middle_name"], "Antonio")
        self.assertEqual(draft_response.data["legal_last_name"], "Martinez Lopez")

        submit_payload = self.identity_payload()
        submit_payload["id_image"] = self.identity_file()
        submit_response = self.client.post(
            reverse("identity-verification-submit"),
            submit_payload,
            format="multipart",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            submit_response.data["status"],
            IdentityVerificationStatus.SUBMITTED,
        )

    def test_identity_verification_submit_returns_errors_when_incomplete(self):
        response = self.client.post(
            reverse("identity-verification-submit"),
            {
                "legal_first_name": "Jose",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_of_birth", response.data)
        self.assertIn("state", response.data)
        self.assertIn("city", response.data)
        self.assertIn("address_line_1", response.data)
        self.assertIn("postal_code", response.data)
        self.assertIn("id_image", response.data)
        self.assertIn("non_field_errors", response.data)

    def test_identity_verification_submit_requires_legal_last_name_when_other_fields_exist(self):
        payload = self.identity_payload()
        payload["id_image"] = self.identity_file()
        payload["legal_first_name"] = "Jose"
        payload["legal_last_name"] = ""

        response = self.client.post(
            reverse("identity-verification-submit"),
            payload,
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("legal_last_name", response.data)

    def test_identity_verification_draft_cannot_be_edited_after_submission(self):
        self._submit_identity_verification_via_service()

        response = self.client.patch(
            reverse("identity-verification"),
            {"city": "Guadalajara"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_broker_application_submit_requires_identity_verification(self):
        submit_response = self.client.post(
            reverse("broker-application-submit"),
            {
                **self.broker_payload(),
                "accepted_broker_declaration": True,
            },
            format="json",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("identity_verification", submit_response.data)

    def test_broker_application_draft_requires_broker_type_on_first_save(self):
        response = self.client.patch(
            reverse("broker-application"),
            {
                "brokerage_name": "Escrow Brokers MX",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("broker_type", response.data)

    def test_broker_application_endpoints_support_draft_and_submit(self):
        self._submit_identity_verification_via_service()

        draft_response = self.client.patch(
            reverse("broker-application"),
            self.broker_payload(),
            format="json",
        )
        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            draft_response.data["status"],
            BrokerApplicationStatus.DRAFT,
        )

        submit_response = self.client.post(
            reverse("broker-application-submit"),
            {"accepted_broker_declaration": True},
            format="json",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            submit_response.data["status"],
            BrokerApplicationStatus.SUBMITTED,
        )
        self.assertEqual(
            submit_response.data["identity_verification"]["status"],
            IdentityVerificationStatus.SUBMITTED,
        )
