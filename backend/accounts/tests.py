from django.test import TestCase

from accounts.models import BrokerApplicationStatus, BrokerType, IdentityStatus, User
from accounts.services.broker import apply_for_broker_status, approve_broker_profile


class BrokerApplicationServiceTests(TestCase):
    def test_broker_application_creates_reusable_user_profile(self):
        user = User.objects.create_user(
            email="broker@example.com",
            password="testpass123",
        )

        profile = apply_for_broker_status(
            user=user,
            broker_type=BrokerType.INDIVIDUAL,
            identity_verified=True,
            accepted_broker_declaration=True,
            state="Ciudad de Mexico",
            city="Ciudad de Mexico",
            address_line_1="Av. Reforma 123",
            postal_code="06000",
            rfc="ABCD123456EF1",
            curp="BADD110313HCMLNS09",
            brokerage_name="Escrow Brokers MX",
            operating_state="Ciudad de Mexico",
            primary_market="Polanco",
            license_or_registration_type="AMPI",
            license_or_registration_number="LIC-123",
        )

        user.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.UNDER_REVIEW)
        self.assertFalse(profile.can_create_transactions)
        self.assertFalse(profile.is_active_broker)
        self.assertTrue(profile.manual_review_required)
        self.assertEqual(user.profile.rfc, "ABCD123456EF1")
        self.assertEqual(user.profile.identity_status, IdentityStatus.VERIFIED)
        self.assertEqual(profile.operating_state, "Ciudad de Mexico")
        self.assertEqual(profile.primary_market, "Polanco")

    def test_broker_approval_enables_transaction_creation(self):
        user = User.objects.create_user(
            email="approved@example.com",
            password="testpass123",
        )

        profile = apply_for_broker_status(
            user=user,
            broker_type=BrokerType.INDIVIDUAL,
            identity_verified=True,
            accepted_broker_declaration=True,
            state="Jalisco",
            city="Guadalajara",
            rfc="ABCD123456EF1",
        )

        approve_broker_profile(profile=profile)
        profile.refresh_from_db()

        self.assertEqual(profile.application_status, BrokerApplicationStatus.APPROVED)
        self.assertTrue(profile.can_create_transactions)
        self.assertTrue(profile.is_active_broker)
        self.assertFalse(profile.manual_review_required)
        self.assertTrue(profile.professional_info_verified)
        self.assertIsNotNone(profile.reviewed_at)
        self.assertIsNotNone(profile.approved_at)
