from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from documents.serializers import (
    PurchaseAgreementConfirmSerializer,
    PurchaseAgreementSerializer,
    PurchaseAgreementUploadSerializer,
)
from documents.services.purchase_agreement import (
    confirm_purchase_agreement_terms,
    get_latest_purchase_agreement,
    upload_purchase_agreement,
)
from transactions.selectors import get_transaction_visible_to_user


def _raise_drf_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise DRFValidationError(exc.message_dict)
    raise DRFValidationError(exc.messages)


class TransactionPurchaseAgreementView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PurchaseAgreementUploadSerializer
        return PurchaseAgreementSerializer

    def get_transaction(self):
        transaction = get_transaction_visible_to_user(
            user=self.request.user,
            transaction_id=self.kwargs["pk"],
        )
        if transaction is None:
            raise Http404("Transaction not found.")
        return transaction

    def get(self, request, *args, **kwargs):
        agreement = get_latest_purchase_agreement(transaction=self.get_transaction())
        if agreement is None:
            raise Http404("Purchase agreement not found.")
        serializer = PurchaseAgreementSerializer(agreement, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            agreement = upload_purchase_agreement(
                transaction=self.get_transaction(),
                uploaded_by_user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = PurchaseAgreementSerializer(agreement, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class PurchaseAgreementConfirmView(generics.GenericAPIView):
    serializer_class = PurchaseAgreementConfirmSerializer
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
        agreement = get_latest_purchase_agreement(transaction=self.get_transaction())
        if agreement is None:
            raise Http404("Purchase agreement not found.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            agreement = confirm_purchase_agreement_terms(
                purchase_agreement=agreement,
                confirmed_by_user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = PurchaseAgreementSerializer(agreement, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)
