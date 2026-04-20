from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from accounts.serializers import (
    BrokerApplicationDraftSerializer,
    BrokerApplicationSubmitSerializer,
    BrokerProfileSerializer,
)
from accounts.services.broker import (
    get_broker_application_for_user,
    save_broker_application_draft,
    submit_broker_application,
)


def _raise_drf_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise DRFValidationError(exc.message_dict)
    raise DRFValidationError(exc.messages)


class BrokerProfileView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BrokerProfileSerializer

    def get(self, request, *args, **kwargs):
        try:
            profile = request.user.broker_profile
        except ObjectDoesNotExist:
            return Response(
                {"detail": "Broker profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BrokerApplicationView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BrokerApplicationDraftSerializer

    def get(self, request, *args, **kwargs):
        profile = get_broker_application_for_user(request.user)
        if not profile:
            return Response(
                {"detail": "Broker application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response_serializer = BrokerProfileSerializer(profile)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            profile = save_broker_application_draft(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = BrokerProfileSerializer(profile)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)


class BrokerApplicationSubmitView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BrokerApplicationSubmitSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            profile = submit_broker_application(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = BrokerProfileSerializer(profile)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


def index(request):
    return render(request, "index.html")


@login_required
def secret(request):
    return render(request, "secret.html")
