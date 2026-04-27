from rest_framework import serializers

from documents.models import PurchaseAgreement, TransactionDocument
from transactions.serializers import TransactionUserSerializer


class TransactionDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_user = TransactionUserSerializer(read_only=True)

    class Meta:
        model = TransactionDocument
        fields = [
            "id",
            "document_type",
            "status",
            "title",
            "file",
            "version",
            "is_required",
            "uploaded_by_user",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PurchaseAgreementSerializer(serializers.ModelSerializer):
    document = TransactionDocumentSerializer(read_only=True)
    confirmed_by_user = TransactionUserSerializer(read_only=True)

    class Meta:
        model = PurchaseAgreement
        fields = [
            "id",
            "document",
            "purchase_price",
            "earnest_money_amount",
            "currency",
            "seller_names",
            "seller_address",
            "buyer_names",
            "buyer_address",
            "property_address",
            "property_legal_description",
            "executed_date",
            "closing_date",
            "inspection_days",
            "payment_scheme_summary",
            "payment_milestones",
            "contingencies",
            "special_conditions",
            "disbursement_conditions",
            "disbursement_payees",
            "disbursement_amounts",
            "disbursement_purposes",
            "gf_number",
            "escrow_agent",
            "escrow_fee",
            "escrow_bank_account",
            "wire_reference",
            "payee_wire_information",
            "broker_commission_allocations",
            "raw_extraction",
            "extraction_status",
            "extraction_error",
            "confirmed_by_user",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PurchaseAgreementUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=255, required=False, default="Purchase agreement")


class PurchaseAgreementConfirmSerializer(serializers.Serializer):
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
    seller_names = serializers.JSONField(required=False)
    seller_address = serializers.CharField(required=False, allow_blank=True)
    buyer_names = serializers.JSONField(required=False)
    buyer_address = serializers.CharField(required=False, allow_blank=True)
    property_address = serializers.CharField(required=False, allow_blank=True)
    property_legal_description = serializers.CharField(required=False, allow_blank=True)
    executed_date = serializers.DateField(required=False, allow_null=True)
    closing_date = serializers.DateField(required=False, allow_null=True)
    inspection_days = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    payment_scheme_summary = serializers.CharField(required=False, allow_blank=True)
    payment_milestones = serializers.JSONField(required=False)
    contingencies = serializers.CharField(required=False, allow_blank=True)
    special_conditions = serializers.CharField(required=False, allow_blank=True)
    disbursement_conditions = serializers.CharField(required=False, allow_blank=True)
    disbursement_payees = serializers.JSONField(required=False)
    disbursement_amounts = serializers.JSONField(required=False)
    disbursement_purposes = serializers.JSONField(required=False)
    gf_number = serializers.CharField(max_length=120, required=False, allow_blank=True)
    escrow_agent = serializers.CharField(max_length=255, required=False, allow_blank=True)
    escrow_fee = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    escrow_bank_account = serializers.CharField(required=False, allow_blank=True)
    wire_reference = serializers.CharField(max_length=255, required=False, allow_blank=True)
    payee_wire_information = serializers.JSONField(required=False)
    broker_commission_allocations = serializers.JSONField(required=False)
