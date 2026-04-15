from django.shortcuts import render
from allauth.account.decorators import verified_email_required
from django.contrib.auth.decorators import login_required
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from accounts.serializers import BrokerApplicationSerializer, BrokerProfileSerializer
from accounts.services.broker import apply_for_broker_status


class BrokerProfileView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BrokerProfileSerializer

    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, "broker_profile", None)
        if not profile:
            return Response(
                {"detail": "Broker profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BrokerApplicationView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BrokerApplicationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = apply_for_broker_status(
            user=request.user,
            **serializer.validated_data,
        )

        response_serializer = BrokerProfileSerializer(profile)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
def index(request):
    return render(request, 'index.html')

@login_required
def secret(request):
    return render(request, 'secret.html')