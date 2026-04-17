from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.models import BrokerProfile, BrokerType, GovernmentIDType, UserProfile


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
            "rfc",
            "curp",
            "id_type",
            "id_image",
            "identity_status",
            "profile_completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "identity_status",
            "profile_completed_at",
            "created_at",
            "updated_at",
        ]


class BrokerProfileSerializer(serializers.ModelSerializer):
    user_profile = serializers.SerializerMethodField()

    class Meta:
        model = BrokerProfile
        fields = [
            "id",
            "broker_type",
            "application_status",
            "can_create_transactions",
            "is_active_broker",
            "identity_verified",
            "professional_info_verified",
            "manual_review_required",
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
            "reviewed_at",
            "approved_at",
            "rejected_at",
            "review_notes",
            "user_profile",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "application_status",
            "can_create_transactions",
            "is_active_broker",
            "submitted_at",
            "reviewed_at",
            "approved_at",
            "rejected_at",
            "accepted_broker_declaration_at",
            "review_notes",
            "user_profile",
            "created_at",
            "updated_at",
        ]

    def get_user_profile(self, obj):
        try:
            profile = obj.user.profile
        except ObjectDoesNotExist:
            return None
        return UserProfileSerializer(profile).data


def validate_company_rfc(value):
    return value.strip().upper()


def validate_rfc(value):
    return value.strip().upper()


class BrokerApplicationSerializer(serializers.Serializer):
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address_line_1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=5, required=False, allow_blank=True)
    rfc = serializers.CharField(max_length=13, required=False, allow_blank=True)
    curp = serializers.CharField(max_length=18, required=False, allow_blank=True)
    id_type = serializers.ChoiceField(
        choices=GovernmentIDType.choices,
        required=False,
        allow_blank=True,
    )
    id_image = serializers.FileField(required=False, allow_null=True)

    broker_type = serializers.ChoiceField(choices=BrokerType.choices)

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
    has_authority_to_represent = serializers.BooleanField(required=False, default=False)

    identity_verified = serializers.BooleanField()
    accepted_broker_declaration = serializers.BooleanField(write_only=True)

    def validate(self, attrs):
        broker_type = attrs.get("broker_type")
        request = self.context.get("request")
        user = getattr(request, "user", None)

        try:
            existing_profile = user.profile if user is not None else None
        except ObjectDoesNotExist:
            existing_profile = None

        if not attrs.get("accepted_broker_declaration"):
            raise serializers.ValidationError(
                {
                    "accepted_broker_declaration": (
                        "You must accept the broker declaration before submitting."
                    )
                }
            )

        if not attrs.get("identity_verified"):
            raise serializers.ValidationError(
                {
                    "identity_verified": (
                        "Identity must be verified before submitting the application."
                    )
                }
            )

        provided_profile_data = any(
            attrs.get(field_name)
            for field_name in ("rfc", "curp", "state", "city", "address_line_1", "postal_code")
        )
        existing_profile_data = bool(
            existing_profile
            and any(
                getattr(existing_profile, field_name)
                for field_name in ("rfc", "curp", "state", "city", "address_line_1", "postal_code")
            )
        )

        if not provided_profile_data and not existing_profile_data:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Provide at least some reusable profile information with the broker application."
                    ]
                }
            )

        if broker_type == BrokerType.COMPANY_REPRESENTATIVE:
            required_company_fields = [
                "company_legal_name",
                "company_rfc",
                "representative_job_title",
            ]
            errors = {}

            for field_name in required_company_fields:
                if not attrs.get(field_name):
                    errors[field_name] = "This field is required for company representatives."

            if not attrs.get("has_authority_to_represent"):
                errors["has_authority_to_represent"] = (
                    "Company representatives must declare authority to represent the company."
                )

            if errors:
                raise serializers.ValidationError(errors)

        return attrs
