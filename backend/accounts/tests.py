from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import BrokerApplicationStatus, BrokerType, IdentityStatus, User
from accounts.services.broker import (
    approve_broker_profile,
    reopen_broker_profile,
    reject_broker_profile,
    request_broker_application_changes,
    save_broker_application_draft,
    submit_broker_application,
    user_can_create_transactions,
)


class BrokerWorkflowServiceTests(APITestCase):
    def setUp(self):
        self.applicant = User.objects.create_user(
            email="broker@example.com",
            password="testpass123",
        )
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com",
            password="testpass123",
            is_staff=True,
        )

    def test_applicant_can_save_draft_then_submit(self):
        profile = save_broker_application_draft(
            user=self.applicant,
            broker_type=BrokerType.INDIVIDUAL,
            state="Ciudad de Mexico",
            city="Ciudad de Mexico",
            rfc="ABCD123456EF1",
        )

        self.applicant.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.DRAFT)
        self.assertFalse(profile.can_create_transactions)
        self.assertEqual(self.applicant.profile.identity_status, IdentityStatus.UNVERIFIED)

        profile = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
        )
        profile.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.SUBMITTED)
        self.assertIsNotNone(profile.submitted_at)
        self.assertFalse(profile.is_active_broker)

    def test_submitted_application_cannot_be_edited_by_applicant(self):
        submit_broker_application(
            user=self.applicant,
            broker_type=BrokerType.INDIVIDUAL,
            accepted_broker_declaration=True,
            state="Ciudad de Mexico",
            city="Ciudad de Mexico",
            rfc="ABCD123456EF1",
        )

        with self.assertRaises(ValidationError):
            save_broker_application_draft(
                user=self.applicant,
                city="Guadalajara",
            )

    def test_reviewer_can_request_info_and_applicant_can_resubmit(self):
        profile = submit_broker_application(
            user=self.applicant,
            broker_type=BrokerType.INDIVIDUAL,
            accepted_broker_declaration=True,
            state="Ciudad de Mexico",
            city="Ciudad de Mexico",
            rfc="ABCD123456EF1",
        )

        profile = request_broker_application_changes(
            profile=profile,
            reviewer=self.reviewer,
            applicant_message="Please upload a clearer ID image.",
            internal_review_notes="Current upload is unreadable.",
        )
        profile.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.NEEDS_INFO)
        self.assertEqual(profile.applicant_message, "Please upload a clearer ID image.")
        self.assertEqual(profile.reviewed_by, self.reviewer)

        profile = save_broker_application_draft(
            user=self.applicant,
            id_type="ine",
        )
        self.assertEqual(profile.application_status, BrokerApplicationStatus.DRAFT)

        profile = submit_broker_application(
            user=self.applicant,
            accepted_broker_declaration=True,
        )
        profile.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.SUBMITTED)
        self.assertEqual(profile.applicant_message, "")

    def test_approval_requires_verified_identity_and_enables_transaction_creation(self):
        profile = submit_broker_application(
            user=self.applicant,
            broker_type=BrokerType.INDIVIDUAL,
            accepted_broker_declaration=True,
            state="Ciudad de Mexico",
            city="Ciudad de Mexico",
            rfc="ABCD123456EF1",
        )

        with self.assertRaises(ValidationError):
            approve_broker_profile(profile=profile, reviewer=self.reviewer)

        self.applicant.profile.identity_status = IdentityStatus.VERIFIED
        self.applicant.profile.save()

        profile = approve_broker_profile(
            profile=profile,
            reviewer=self.reviewer,
            internal_review_notes="All broker onboarding checks passed.",
        )
        profile.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.APPROVED)
        self.assertTrue(profile.can_create_transactions)
        self.assertTrue(profile.is_active_broker)
        self.assertTrue(user_can_create_transactions(self.applicant))
        self.assertEqual(profile.reviewed_by, self.reviewer)

    def test_reviewer_can_reopen_rejected_application(self):
        profile = submit_broker_application(
            user=self.applicant,
            broker_type=BrokerType.INDIVIDUAL,
            accepted_broker_declaration=True,
            state="Ciudad de Mexico",
            city="Ciudad de Mexico",
            rfc="ABCD123456EF1",
        )

        profile = reject_broker_profile(
            profile=profile,
            reviewer=self.reviewer,
            applicant_message="Not enough information for approval.",
            internal_review_notes="Please reopen after applicant updates profile details.",
        )
        profile.refresh_from_db()
        self.assertEqual(profile.application_status, BrokerApplicationStatus.REJECTED)

        profile = reopen_broker_profile(
            profile=profile,
            reviewer=self.reviewer,
            applicant_message="Application reopened. Please update your information and resubmit.",
            internal_review_notes="Reopened after manual override.",
        )
        profile.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.DRAFT)
        self.assertEqual(
            profile.applicant_message,
            "Application reopened. Please update your information and resubmit.",
        )
        self.assertEqual(profile.reviewed_by, self.reviewer)
        self.assertFalse(profile.can_create_transactions)

        profile = save_broker_application_draft(
            user=self.applicant,
            operating_state="Jalisco",
        )
        self.assertEqual(profile.application_status, BrokerApplicationStatus.DRAFT)


class BrokerWorkflowApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="api-broker@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_broker_application_endpoints_support_draft_and_submit(self):
        draft_response = self.client.patch(
            reverse("broker-application"),
            {
                "broker_type": BrokerType.INDIVIDUAL,
                "state": "Ciudad de Mexico",
                "city": "Ciudad de Mexico",
                "rfc": "ABCD123456EF1",
            },
            format="json",
        )
        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            draft_response.data["application_status"],
            BrokerApplicationStatus.DRAFT,
        )

        submit_response = self.client.post(
            reverse("broker-application-submit"),
            {"accepted_broker_declaration": True},
            format="json",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            submit_response.data["application_status"],
            BrokerApplicationStatus.SUBMITTED,
        )
        self.assertFalse(submit_response.data["can_create_transactions"])
