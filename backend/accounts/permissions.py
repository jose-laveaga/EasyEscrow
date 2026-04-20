from rest_framework.permissions import BasePermission

from accounts.services.broker import user_can_create_transactions


class CanCreateTransactions(BasePermission):
    message = "Only approved active brokers can create transactions."

    def has_permission(self, request, view):
        return user_can_create_transactions(request.user)
