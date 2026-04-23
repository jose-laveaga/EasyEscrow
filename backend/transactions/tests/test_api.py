from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from transactions.models import InvitationStatus, ParticipantRole, ParticipantStatus, TransactionType
from transactions.services.invitation import invite_participant
from transactions.tests.test_fixtures import TransactionFixturesMixin


class TransactionApiTests(TransactionFixturesMixin, APITestCase):
    def test_transaction_create_endpoint_requires_broker_permission(self):
        user = self.create_user("user@example.com")
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("transaction-list-create"),
            {
                "title": "Roma Norte purchase",
                "transaction_type": TransactionType.STANDARD,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_transaction_endpoints_create_list_detail_and_participants(self):
        broker = self.create_broker("broker@example.com")
        self.client.force_authenticate(user=broker)

        create_response = self.client.post(
            reverse("transaction-list-create"),
            {
                "title": "Roma Norte purchase",
                "description": "Residential resale escrow.",
                "transaction_type": TransactionType.STANDARD,
                "property_data": {
                    "address_line1": "Av. Alvaro Obregon 100",
                    "city": "Ciudad de Mexico",
                    "state": "Ciudad de Mexico",
                    "postal_code": "06700",
                },
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        transaction_id = create_response.data["id"]

        list_response = self.client.get(reverse("transaction-list-create"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        detail_response = self.client.get(reverse("transaction-detail", args=[transaction_id]))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["title"], "Roma Norte purchase")
        self.assertEqual(detail_response.data["property"]["address_line1"], "Av. Alvaro Obregon 100")

        participants_response = self.client.get(
            reverse("transaction-participants", args=[transaction_id])
        )
        self.assertEqual(participants_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(participants_response.data), 1)
        self.assertEqual(participants_response.data[0]["role"], ParticipantRole.PRIMARY_BROKER)
        self.assertEqual(participants_response.data[0]["status"], ParticipantStatus.ACTIVE)

    def test_invitation_endpoints_support_send_accept_and_reject(self):
        broker = self.create_broker("broker@example.com")
        buyer = self.create_user("buyer@example.com")
        seller = self.create_user("seller@example.com")
        transaction = self.create_transaction_for_broker(broker)

        self.client.force_authenticate(user=broker)
        invite_response = self.client.post(
            reverse("transaction-invitations", args=[transaction.id]),
            {
                "target_user": buyer.id,
                "intended_role": ParticipantRole.BUYER,
            },
            format="json",
        )

        self.assertEqual(invite_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(invite_response.data["target_email"], buyer.email)
        invitation_id = invite_response.data["id"]

        self.client.force_authenticate(user=buyer)
        accept_response = self.client.post(
            reverse("invitation-accept", args=[invitation_id]),
            {},
            format="json",
        )

        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)
        self.assertEqual(accept_response.data["role"], ParticipantRole.BUYER)

        seller_invitation = invite_participant(
            transaction=transaction,
            sent_by_user=broker,
            intended_role=ParticipantRole.SELLER,
            target_user=seller,
        )

        self.client.force_authenticate(user=seller)
        reject_response = self.client.post(
            reverse("invitation-reject", args=[seller_invitation.id]),
            {},
            format="json",
        )

        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reject_response.data["status"], InvitationStatus.DECLINED)
