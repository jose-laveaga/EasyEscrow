from django.utils import timezone

from accounts.models import BrokerProfile, BrokerType, IdentityVerificationStatus, User
from documents.models import (
    DocumentType,
    PurchaseAgreement,
    PurchaseAgreementExtractionStatus,
    TransactionDocument,
)
from transactions.models import TransactionType
from transactions.services.transaction import create_transaction


class TransactionFixturesMixin:
    password = "testpass123"

    def create_user(self, email, *, first_name="Test", last_name="User"):
        return User.objects.create_user(
            email=email,
            password=self.password,
            first_name=first_name,
            last_name=last_name,
        )

    def make_eligible_broker(self, user):
        profile = user.profile
        profile.status = IdentityVerificationStatus.VERIFIED
        profile.verified_at = timezone.now()
        profile.save(update_fields=["status", "verified_at"])

        broker_profile, _ = BrokerProfile.objects.get_or_create(
            user=user,
            defaults={"broker_type": BrokerType.INDIVIDUAL},
        )
        broker_profile.broker_type = BrokerType.INDIVIDUAL
        broker_profile.is_active_broker = True
        broker_profile.approved_at = timezone.now()
        broker_profile.save()
        return broker_profile

    def create_broker(self, email):
        user = self.create_user(email)
        self.make_eligible_broker(user)
        return user

    def attach_purchase_agreement(self, transaction):
        document = TransactionDocument.objects.create(
            transaction=transaction,
            uploaded_by_user=transaction.created_by,
            document_type=DocumentType.PURCHASE_AGREEMENT,
            title="Purchase agreement",
            file="transactions/documents/purchase-agreement.pdf",
            is_required=True,
        )
        return PurchaseAgreement.objects.create(
            document=document,
            purchase_price="2500000.00",
            earnest_money_amount="100000.00",
            extraction_status=PurchaseAgreementExtractionStatus.CONFIRMED,
            confirmed_by_user=transaction.created_by,
            confirmed_at=timezone.now(),
        )

    def create_transaction_for_broker(self, broker, *, with_purchase_agreement=True, **overrides):
        payload = {
            "title": "Casa Azul Purchase",
            "description": "Escrow setup for the purchase transaction.",
            "transaction_type": TransactionType.STANDARD,
        }
        payload.update(overrides)
        transaction = create_transaction(created_by=broker, **payload)
        if with_purchase_agreement:
            self.attach_purchase_agreement(transaction)
        return transaction
