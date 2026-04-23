from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from accounts.serializers import (
    BrokerApplicationDraftSerializer,
    BrokerApplicationSerializer,
    BrokerApplicationSubmitSerializer,
    BrokerProfileSerializer,
    IdentityVerificationDraftSerializer,
    IdentityVerificationSerializer,
    IdentityVerificationSubmitSerializer,
    UserProfileSerializer,
)
from accounts.models import IdentityVerificationStatus, UserProfile
from accounts.services.broker import (
    get_broker_application_for_user,
    get_broker_profile_for_user,
    save_broker_application_draft,
    submit_broker_application,
)
from accounts.services.identity import (
    get_identity_verification_for_user,
    save_identity_verification_draft,
    submit_identity_verification,
)


def _raise_drf_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise DRFValidationError(exc.message_dict)
    raise DRFValidationError(exc.messages)


def _get_or_create_user_profile(user) -> UserProfile:
    profile, _ = UserProfile.objects.select_related("user").get_or_create(
        user=user,
        defaults={"status": IdentityVerificationStatus.DRAFT},
    )
    return profile


class ProfileView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return _get_or_create_user_profile(self.request.user)

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            profile = serializer.save()
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        return Response(self.get_serializer(profile).data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = serializer.save()
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        return Response(self.get_serializer(profile).data, status=status.HTTP_200_OK)


class IdentityVerificationView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = IdentityVerificationDraftSerializer

    def get(self, request, *args, **kwargs):
        identity_verification = get_identity_verification_for_user(request.user)
        if not identity_verification:
            return Response(
                {"detail": "Identity verification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response_serializer = IdentityVerificationSerializer(identity_verification)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            identity_verification = save_identity_verification_draft(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = IdentityVerificationSerializer(identity_verification)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)


class IdentityVerificationSubmitView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = IdentityVerificationSubmitSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            identity_verification = submit_identity_verification(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = IdentityVerificationSerializer(identity_verification)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class BrokerProfileView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BrokerProfileSerializer

    def get(self, request, *args, **kwargs):
        profile = get_broker_profile_for_user(request.user)
        if not profile:
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
        application = get_broker_application_for_user(request.user)
        if not application:
            return Response(
                {"detail": "Broker application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        response_serializer = BrokerApplicationSerializer(application)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            application = save_broker_application_draft(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = BrokerApplicationSerializer(application)
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
            application = submit_broker_application(
                user=request.user,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            _raise_drf_validation_error(exc)

        response_serializer = BrokerApplicationSerializer(application)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


def index(request):
    return render(request, "index.html")


@login_required
def secret(request):
    return render(request, "secret.html")
