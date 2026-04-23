from django.contrib import admin

from transactions.models import Invitation, Property, Transaction, TransactionParticipant


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("address_line1", "city", "state", "postal_code", "country", "created_at")
    search_fields = ("address_line1", "city", "state", "postal_code", "parcel_number")
    list_filter = ("state", "country", "created_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "title",
        "transaction_type",
        "status",
        "created_by",
        "purchase_price",
        "currency",
        "closing_date_target",
        "created_at",
    )
    list_filter = ("transaction_type", "status", "currency", "created_at")
    search_fields = (
        "reference_code",
        "title",
        "created_by__email",
        "property__address_line1",
        "property__city",
        "property__state",
    )
    raw_id_fields = ("property", "created_by")
    list_select_related = ("property", "created_by")


@admin.register(TransactionParticipant)
class TransactionParticipantAdmin(admin.ModelAdmin):
    list_display = ("transaction", "user", "role", "status", "joined_at", "created_at")
    list_filter = ("role", "status", "created_at")
    search_fields = ("transaction__reference_code", "user__email")
    raw_id_fields = ("transaction", "user")
    list_select_related = ("transaction", "user")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transaction",
        "intended_role",
        "status",
        "delivery_method",
        "target_email",
        "target_user",
        "sent_by_user",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "delivery_method", "intended_role", "created_at")
    search_fields = (
        "transaction__reference_code",
        "token",
        "target_email",
        "target_user__email",
        "sent_by_user__email",
    )
    raw_id_fields = ("transaction", "sent_by_user", "target_user", "accepted_participant")
    list_select_related = ("transaction", "sent_by_user", "target_user", "accepted_participant")
