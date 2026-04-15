from rest_framework import serializers

from accounts.models import BrokerProfile, BrokerType


class BrokerProfileSerializer(serializers.ModelSerializer):
    can_create_transactions = serializers.ReadOnlyField()

    class Meta:
        model = BrokerProfile
        fields = [
            "id",
            "broker_type",
            "rfc",
            "state",
            "city",
            "brokerage_name",
            "certification_name",
            "certification_number",
            "company_legal_name",
            "company_rfc",
            "representative_job_title",
            "has_authority_to_represent",
            "identity_verified",
            "application_status",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "needs_info_at",
            "accepted_broker_declaration_at",
            "review_notes",
            "can_create_transactions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "application_status",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "needs_info_at",
            "accepted_broker_declaration_at",
            "review_notes",
            "can_create_transactions",
            "created_at",
            "updated_at",
        ]


def validate_company_rfc(value):
    return value.strip().upper()


def validate_rfc(value):
    return value.strip().upper()


class BrokerApplicationSerializer(serializers.Serializer):
    broker_type = serializers.ChoiceField(choices=BrokerType.choices)
    rfc = serializers.CharField(max_length=13)
    state = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)

    brokerage_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    certification_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    certification_number = serializers.CharField(max_length=100, required=False, allow_blank=True)

    company_legal_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    company_rfc = serializers.CharField(max_length=13, required=False, allow_blank=True)
    representative_job_title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    has_authority_to_represent = serializers.BooleanField(required=False, default=False)

    identity_verified = serializers.BooleanField()
    accepted_broker_declaration = serializers.BooleanField(write_only=True)

    def validate(self, attrs):
        broker_type = attrs.get("broker_type")

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