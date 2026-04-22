from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.models import (
    BrokerApplication,
    BrokerProfile,
    BrokerType,
    GovernmentIDType,
    UserProfile,
)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "date_of_birth",
            "state",
            "city",
            "address_line_1",
            "address_line_2",
            "postal_code",
            "profile_completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "profile_completed_at",
            "created_at",
            "updated_at",
        ]


class IdentityVerificationSummarySerializer(serializers.ModelSerializer):
    is_identity_verified = serializers.ReadOnlyField()

    class Meta:
        model = UserProfile
        fields = [
            "status",
            "is_identity_verified",
            "submitted_at",
            "verified_at",
            "applicant_message",
        ]
        read_only_fields = fields


class IdentityVerificationSerializer(serializers.ModelSerializer):
    is_identity_verified = serializers.ReadOnlyField()

    class Meta:
        model = UserProfile
        fields = [
            "date_of_birth",
            "state",
            "city",
            "address_line_1",
            "address_line_2",
            "postal_code",
            "status",
            "is_identity_verified",
            "legal_first_name",
            "legal_middle_name",
            "legal_last_name",
            "rfc",
            "curp",
            "id_type",
            "id_image",
            "submitted_at",
            "review_started_at",
            "reviewed_at",
            "verified_at",
            "rejected_at",
            "applicant_message",
            "profile_completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "is_identity_verified",
            "submitted_at",
            "review_started_at",
            "reviewed_at",
            "verified_at",
            "rejected_at",
            "applicant_message",
            "profile_completed_at",
            "created_at",
            "updated_at",
        ]


class BrokerProfileSerializer(serializers.ModelSerializer):
    can_create_transactions = serializers.ReadOnlyField()
    identity_verification = serializers.SerializerMethodField()

    class Meta:
        model = BrokerProfile
        fields = [
            "id",
            "approved_application",
            "broker_type",
            "can_create_transactions",
            "is_active_broker",
            "approved_at",
            "brokerage_name",
            "years_of_experience",
            "primary_market",
            "operating_state",
            "license_or_registration_type",
            "license_or_registration_number",
            "issuing_authority",
            "license_expires_at",
            "company_legal_name",
            "company_rfc",
            "representative_job_title",
            "has_authority_to_represent",
            "identity_verification",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_identity_verification(self, obj):
        try:
            identity_profile = obj.user.profile
        except ObjectDoesNotExist:
            return None
        return IdentityVerificationSummarySerializer(identity_profile).data


class BrokerApplicationSerializer(serializers.ModelSerializer):
    identity_verification = serializers.SerializerMethodField()
    has_active_broker_profile = serializers.SerializerMethodField()

    class Meta:
        model = BrokerApplication
        fields = [
            "id",
            "broker_type",
            "status",
            "brokerage_name",
            "years_of_experience",
            "primary_market",
            "operating_state",
            "license_or_registration_type",
            "license_or_registration_number",
            "issuing_authority",
            "license_expires_at",
            "company_legal_name",
            "company_rfc",
            "representative_job_title",
            "has_authority_to_represent",
            "accepted_broker_declaration_at",
            "submitted_at",
            "review_started_at",
            "reviewed_at",
            "approved_at",
            "rejected_at",
            "applicant_message",
            "identity_verification",
            "has_active_broker_profile",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_identity_verification(self, obj):
        try:
            verification = obj.user.profile
        except ObjectDoesNotExist:
            return None
        return IdentityVerificationSummarySerializer(verification).data

    def get_has_active_broker_profile(self, obj):
        return hasattr(obj.user, "broker_profile")


class IdentityVerificationDraftSerializer(serializers.Serializer):
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address_line_1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=5, required=False, allow_blank=True)

    legal_first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    legal_middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    legal_last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    rfc = serializers.CharField(max_length=13, required=False, allow_blank=True)
    curp = serializers.CharField(max_length=18, required=False, allow_blank=True)
    id_type = serializers.ChoiceField(
        choices=GovernmentIDType.choices,
        required=False,
        allow_blank=True,
    )
    id_image = serializers.FileField(required=False, allow_null=True)


class IdentityVerificationSubmitSerializer(IdentityVerificationDraftSerializer):
    pass


class BrokerApplicationDraftSerializer(serializers.Serializer):
    broker_type = serializers.ChoiceField(
        choices=BrokerType.choices,
        required=False,
    )
    accepted_broker_declaration = serializers.BooleanField(required=False)

    brokerage_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    years_of_experience = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    primary_market = serializers.CharField(max_length=255, required=False, allow_blank=True)
    operating_state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    license_or_registration_type = serializers.CharField(max_length=255, required=False, allow_blank=True)
    license_or_registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    issuing_authority = serializers.CharField(max_length=255, required=False, allow_blank=True)
    license_expires_at = serializers.DateField(required=False, allow_null=True)

    company_legal_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    company_rfc = serializers.CharField(max_length=13, required=False, allow_blank=True)
    representative_job_title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    has_authority_to_represent = serializers.BooleanField(required=False)


class BrokerApplicationSubmitSerializer(BrokerApplicationDraftSerializer):
    pass
