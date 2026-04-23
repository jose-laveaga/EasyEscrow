from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from transactions.models import (
    InvitationStatus,
    ParticipantRole,
    ParticipantStatus,
    TransactionParticipant,
    TransactionStatus,
    TransactionType,
)
from transactions.services.invitation import accept_invitation, invite_participant, reject_invitation
from transactions.services.participant import add_participant
from transactions.services.transaction import create_transaction, sync_transaction_setup_status
from transactions.tests.test_fixtures import TransactionFixturesMixin


class TransactionServiceTests(TransactionFixturesMixin, TestCase):
    def test_eligible_broker_can_create_transaction(self):
        broker = self.create_broker("broker@example.com")

        transaction = create_transaction(
            created_by=broker,
            title="Roma Norte purchase",
            transaction_type=TransactionType.STANDARD,
        )

        self.assertEqual(transaction.created_by, broker)
        self.assertEqual(transaction.status, TransactionStatus.DRAFT)
        self.assertTrue(transaction.reference_code.startswith("TXN-"))

    def test_non_broker_cannot_create_transaction(self):
        user = self.create_user("non-broker@example.com")

        with self.assertRaises(ValidationError):
            create_transaction(
                created_by=user,
                title="Should fail",
                transaction_type=TransactionType.STANDARD,
            )

    def test_creator_becomes_primary_broker_participant(self):
        broker = self.create_broker("primary-broker@example.com")

        transaction = self.create_transaction_for_broker(broker)

        participant = transaction.participants.get(user=broker)
        self.assertEqual(participant.role, ParticipantRole.PRIMARY_BROKER)
        self.assertEqual(participant.status, ParticipantStatus.ACTIVE)
        self.assertIsNotNone(participant.joined_at)

    def test_invitation_can_be_sent_to_existing_user(self):
        broker = self.create_broker("broker@example.com")
        buyer = self.create_user("buyer@example.com")
        transaction = self.create_transaction_for_broker(broker)

        invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.BUYER,
            target_user=buyer,
        )

        self.assertEqual(invitation.target_user, buyer)
        self.assertEqual(invitation.target_email, buyer.email)
        self.assertEqual(invitation.status, InvitationStatus.PENDING)

    def test_invitation_can_be_sent_by_email_only(self):
        broker = self.create_broker("broker@example.com")
        transaction = self.create_transaction_for_broker(broker)

        invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.SELLER,
            target_email="seller@example.com",
        )

        self.assertIsNone(invitation.target_user)
        self.assertEqual(invitation.target_email, "seller@example.com")
        self.assertEqual(invitation.status, InvitationStatus.PENDING)

    def test_invitation_acceptance_creates_participant(self):
        broker = self.create_broker("broker@example.com")
        buyer = self.create_user("buyer@example.com")
        transaction = self.create_transaction_for_broker(broker)
        invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.BUYER,
            target_user=buyer,
        )

        participant = accept_invitation(invitation=invitation, acting_user=buyer)

        invitation.refresh_from_db()
        self.assertEqual(participant.user, buyer)
        self.assertEqual(participant.role, ParticipantRole.BUYER)
        self.assertEqual(invitation.status, InvitationStatus.ACCEPTED)
        self.assertEqual(invitation.accepted_participant, participant)

    def test_invitation_rejection_does_not_create_participant(self):
        broker = self.create_broker("broker@example.com")
        seller = self.create_user("seller@example.com")
        transaction = self.create_transaction_for_broker(broker)
        invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.SELLER,
            target_user=seller,
        )

        reject_invitation(invitation=invitation, acting_user=seller)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.DECLINED)
        self.assertFalse(
            TransactionParticipant.objects.filter(transaction=transaction, user=seller).exists()
        )

    def test_duplicate_participant_user_in_same_transaction_is_blocked(self):
        broker = self.create_broker("broker@example.com")
        transaction = self.create_transaction_for_broker(broker)

        with self.assertRaises(ValidationError):
            add_participant(
                transaction=transaction,
                user=broker,
                role=ParticipantRole.ESCROW_OFFICER,
            )

    def test_duplicate_restricted_role_in_same_transaction_is_blocked(self):
        broker = self.create_broker("broker@example.com")
        buyer_one = self.create_user("buyer-one@example.com")
        buyer_two = self.create_user("buyer-two@example.com")
        transaction = self.create_transaction_for_broker(broker)

        add_participant(
            transaction=transaction,
            user=buyer_one,
            role=ParticipantRole.BUYER,
        )

        with self.assertRaises(ValidationError):
            add_participant(
                transaction=transaction,
                user=buyer_two,
                role=ParticipantRole.BUYER,
            )

    def test_setup_status_sync_changes_to_pending_invitations_when_required_invites_are_pending(self):
        broker = self.create_broker("broker@example.com")
        transaction = self.create_transaction_for_broker(broker)

        invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.BUYER,
            target_email="buyer@example.com",
        )
        invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.SELLER,
            target_email="seller@example.com",
        )

        transaction.refresh_from_db()
        self.assertEqual(transaction.status, TransactionStatus.PENDING_INVITATIONS)

    def test_setup_status_sync_changes_to_parties_confirmed_when_required_participants_are_active(self):
        broker = self.create_broker("broker@example.com")
        buyer = self.create_user("buyer@example.com")
        seller = self.create_user("seller@example.com")
        transaction = self.create_transaction_for_broker(broker)

        add_participant(transaction=transaction, user=buyer, role=ParticipantRole.BUYER)
        add_participant(transaction=transaction, user=seller, role=ParticipantRole.SELLER)

        transaction.refresh_from_db()
        self.assertEqual(transaction.status, TransactionStatus.PARTIES_CONFIRMED)

    def test_expired_invitation_cannot_be_accepted(self):
        broker = self.create_broker("broker@example.com")
        buyer = self.create_user("buyer@example.com")
        transaction = self.create_transaction_for_broker(broker)
        invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.BUYER,
            target_user=buyer,
        )
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save(update_fields=["expires_at"])

        with self.assertRaises(ValidationError):
            accept_invitation(invitation=invitation, acting_user=buyer)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.EXPIRED)

    def test_inviting_an_already_active_participant_is_blocked(self):
        broker = self.create_broker("broker@example.com")
        buyer = self.create_user("buyer@example.com")
        transaction = self.create_transaction_for_broker(broker)

        add_participant(transaction=transaction, user=buyer, role=ParticipantRole.BUYER)

        with self.assertRaises(ValidationError):
            invite_participant(
                transaction=transaction,
                sent_by_user=broker,
                intended_role=ParticipantRole.BUYER,
                target_user=buyer,
            )

    def test_non_matching_user_cannot_accept_invitation(self):
        broker = self.create_broker("broker@example.com")
        target_user = self.create_user("target@example.com")
        other_user = self.create_user("other@example.com")
        transaction = self.create_transaction_for_broker(broker)
        invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.BUYER,
            target_user=target_user,
        )

        with self.assertRaises(ValidationError):
            accept_invitation(invitation=invitation, acting_user=other_user)

    def test_sync_transaction_setup_status_returns_draft_without_required_invites(self):
        broker = self.create_broker("broker@example.com")
        transaction = self.create_transaction_for_broker(broker)

        sync_transaction_setup_status(transaction=transaction)
        transaction.refresh_from_db()

        self.assertEqual(transaction.status, TransactionStatus.DRAFT)
