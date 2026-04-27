from datetime import timedelta

from django.utils import timezone
import factory

from accounts.tests.factories import EligibleBrokerUserFactory, UserFactory
from transactions.models import (
    Invitation,
    InvitationDeliveryMethod,
    InvitationStatus,
    ParticipantRole,
    ParticipantStatus,
    Transaction,
    TransactionParticipant,
    TransactionType,
)


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    reference_code = factory.Sequence(lambda n: f"TXN-TEST-{n:06d}")
    transaction_type = TransactionType.STANDARD
    status = "DRAFT"
    title = factory.Sequence(lambda n: f"Test transaction {n}")
    description = "Escrow workflow test transaction."
    created_by = factory.SubFactory(EligibleBrokerUserFactory)


class TransactionParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TransactionParticipant

    transaction = factory.SubFactory(TransactionFactory)
    user = factory.SubFactory(UserFactory)
    role = ParticipantRole.BUYER
    status = ParticipantStatus.ACTIVE
    joined_at = factory.LazyFunction(timezone.now)


class InvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invitation

    transaction = factory.SubFactory(TransactionFactory)
    sent_by_user = factory.SelfAttribute("transaction.created_by")
    target_user = factory.SubFactory(UserFactory)
    target_email = factory.LazyAttribute(lambda invitation: invitation.target_user.email)
    intended_role = ParticipantRole.BUYER
    delivery_method = InvitationDeliveryMethod.EMAIL
    token = factory.Sequence(lambda n: f"test-invitation-token-{n}")
    status = InvitationStatus.PENDING
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
