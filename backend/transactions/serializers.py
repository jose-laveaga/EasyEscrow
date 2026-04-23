from django.contrib.auth import get_user_model
from rest_framework import serializers

from transactions.models import (
    Invitation,
    InvitationDeliveryMethod,
    Property,
    Transaction,
    TransactionParticipant,
    TransactionType,
)


User = get_user_model()


class TransactionUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "middle_name", "last_name"]
        read_only_fields = fields


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = [
            "id",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "parcel_number",
            "legal_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PropertyInputSerializer(serializers.Serializer):
    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120)
    state = serializers.CharField(max_length=120)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=120, required=False, allow_blank=True)
    parcel_number = serializers.CharField(max_length=120, required=False, allow_blank=True)
    legal_description = serializers.CharField(required=False, allow_blank=True)


class TransactionParticipantSerializer(serializers.ModelSerializer):
    user = TransactionUserSerializer(read_only=True)

    class Meta:
        model = TransactionParticipant
        fields = [
            "id",
            "user",
            "role",
            "status",
            "joined_at",
            "left_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvitationSerializer(serializers.ModelSerializer):
    sent_by_user = TransactionUserSerializer(read_only=True)
    target_user = TransactionUserSerializer(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "transaction",
            "sent_by_user",
            "target_user",
            "target_email",
            "intended_role",
            "delivery_method",
            "token",
            "status",
            "accepted_participant",
            "expires_at",
            "responded_at",
            "accepted_at",
            "declined_at",
            "revoked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    property = PropertySerializer(read_only=True)
    created_by = TransactionUserSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "reference_code",
            "transaction_type",
            "status",
            "title",
            "description",
            "property",
            "created_by",
            "purchase_price",
            "earnest_money_amount",
            "currency",
            "closing_date_target",
            "opened_at",
            "funded_at",
            "closed_at",
            "cancelled_at",
            "failed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TransactionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    transaction_type = serializers.ChoiceField(choices=TransactionType.choices)
    property_data = PropertyInputSerializer(required=False, allow_null=True)
    purchase_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    earnest_money_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(max_length=10, required=False, default="MXN")
    closing_date_target = serializers.DateField(required=False, allow_null=True)


class InvitationCreateSerializer(serializers.Serializer):
    target_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    target_email = serializers.EmailField(required=False, allow_blank=True)
    intended_role = serializers.ChoiceField(choices=TransactionParticipant._meta.get_field("role").choices)
    delivery_method = serializers.ChoiceField(
        choices=InvitationDeliveryMethod.choices,
        required=False,
        default=InvitationDeliveryMethod.EMAIL,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("target_user") and not attrs.get("target_email", "").strip():
            raise serializers.ValidationError(
                {"non_field_errors": ["Provide target_user or target_email."]}
            )
        return attrs


class InvitationActionSerializer(serializers.Serializer):
    pass
