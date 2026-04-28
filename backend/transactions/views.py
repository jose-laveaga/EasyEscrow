from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from accounts.permissions import CanCreateTransactions
from transactions.models import Invitation
from transactions.selectors import (
    get_transaction_visible_to_user,
    get_transactions_visible_to_user,
    get_user_draft_and_active_transactions,
    get_user_invitations,
)
from transactions.serializers import (
    BrokerCommissionAgreementActionSerializer,
    BrokerCommissionAgreementProposeSerializer,
    BrokerCommissionAgreementSerializer,
    InvitationActionSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    TransactionCreateSerializer,
    TransactionParticipantSerializer,
    TransactionSerializer,
    UserInvitationSerializer,
)
from transactions.services.commission import (
    accept_commission_agreement,
    get_commission_agreement,
    propose_commission_agreement,
)
from transactions.services.invitation import accept_invitation, invite_participant, reject_invitation
from transactions.services.transaction import create_transaction


def _raise_drf_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise DRFValidationError(exc.message_dict)
    raise DRFValidationError(exc.messages)


class TransactionListCreateView(generics.GenericAPIView):
    serializer_class = TransactionCreateSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), CanCreateTransactions()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return get_transactions_visible_to_user(user=self.request.user)

    def get(self, request, *args, **kwargs):
        transactions = get_transactions_visible_to_user(user=request.user)
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            transaction = create_transaction(
                created_by=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = TransactionSerializer(transaction)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class TransactionDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        transaction = get_transaction_visible_to_user(
            user=self.request.user,
            transaction_id=self.kwargs["pk"],
        )
        if transaction is None:
            raise Http404("Transaction not found.")
        return transaction

    def get(self, request, *args, **kwargs):
        serializer = TransactionSerializer(self.get_object())
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionParticipantsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        transaction = get_transaction_visible_to_user(
            user=self.request.user,
            transaction_id=self.kwargs["pk"],
        )
        if transaction is None:
            raise Http404("Transaction not found.")
        return transaction

    def get(self, request, *args, **kwargs):
        transaction = self.get_object()
        serializer = TransactionParticipantSerializer(transaction.participants.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TransactionCommissionAgreementView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BrokerCommissionAgreementProposeSerializer
        return BrokerCommissionAgreementSerializer

    def get_transaction(self):
        transaction = get_transaction_visible_to_user(
            user=self.request.user,
            transaction_id=self.kwargs["pk"],
        )
        if transaction is None:
            raise Http404("Transaction not found.")
        return transaction

    def get(self, request, *args, **kwargs):
        agreement = get_commission_agreement(transaction=self.get_transaction())
        if agreement is None:
            raise Http404("Commission agreement not found.")
        serializer = BrokerCommissionAgreementSerializer(agreement)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        transaction = self.get_transaction()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            agreement = propose_commission_agreement(
                transaction=transaction,
                proposed_by_user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = BrokerCommissionAgreementSerializer(agreement)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class TransactionCommissionAgreementAcceptView(generics.GenericAPIView):
    serializer_class = BrokerCommissionAgreementActionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_transaction(self):
        transaction = get_transaction_visible_to_user(
            user=self.request.user,
            transaction_id=self.kwargs["pk"],
        )
        if transaction is None:
            raise Http404("Transaction not found.")
        return transaction

    def post(self, request, *args, **kwargs):
        try:
            agreement = accept_commission_agreement(
                transaction=self.get_transaction(),
                accepted_by_user=request.user,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        serializer = BrokerCommissionAgreementSerializer(agreement)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserTransactionOverviewView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        grouped_transactions = get_user_draft_and_active_transactions(user=request.user)
        response_data = {
            "draft": TransactionSerializer(grouped_transactions["draft"], many=True).data,
            "active": TransactionSerializer(grouped_transactions["active"], many=True).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class UserInvitationOverviewView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        grouped_invitations = get_user_invitations(user=request.user)
        response_data = {
            "sent": UserInvitationSerializer(grouped_invitations["sent"], many=True).data,
            "received": UserInvitationSerializer(grouped_invitations["received"], many=True).data,
        }
        return Response(response_data, status=status.HTTP_200_OK)


class TransactionInvitationCreateView(generics.GenericAPIView):
    serializer_class = InvitationCreateSerializer
    permission_classes = [permissions.IsAuthenticated, CanCreateTransactions]

    def get_transaction(self):
        transaction = get_transaction_visible_to_user(
            user=self.request.user,
            transaction_id=self.kwargs["pk"],
        )
        if transaction is None:
            raise Http404("Transaction not found.")
        return transaction

    def post(self, request, *args, **kwargs):
        transaction = self.get_transaction()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invitation = invite_participant(
                transaction=transaction,
                sent_by_user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = InvitationSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class InvitationAcceptView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvitationActionSerializer

    def post(self, request, *args, **kwargs):
        try:
            invitation = Invitation.objects.select_related("transaction", "target_user").get(
                pk=self.kwargs["pk"]
            )
            participant = accept_invitation(
                invitation=invitation,
                acting_user=request.user,
            )
        except Invitation.DoesNotExist as exc:
            raise Http404("Invitation not found.") from exc
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = TransactionParticipantSerializer(participant)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class InvitationRejectView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvitationActionSerializer

    def post(self, request, *args, **kwargs):
        try:
            invitation = Invitation.objects.select_related("transaction", "target_user").get(
                pk=self.kwargs["pk"]
            )
            invitation = reject_invitation(
                invitation=invitation,
                acting_user=request.user,
            )
        except Invitation.DoesNotExist as exc:
            raise Http404("Invitation not found.") from exc
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = InvitationSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
