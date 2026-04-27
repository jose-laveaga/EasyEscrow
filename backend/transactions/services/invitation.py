from __future__ import annotations

from datetime import timedelta
import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction as db_transaction
from django.db.models import Q
from django.utils import timezone

from transactions.models import (
    Invitation,
    InvitationStatus,
    ParticipantRole,
    ParticipantStatus,
    Transaction,
    TransactionParticipant,
    TransactionType,
)


BROKER_INVITER_ROLES = {
    ParticipantRole.PRIMARY_BROKER,
    ParticipantRole.COOPERATING_BROKER,
}
SINGLE_OCCUPANT_INVITATION_ROLES = {
    ParticipantRole.PRIMARY_BROKER,
    ParticipantRole.COOPERATING_BROKER,
    ParticipantRole.BUYER,
    ParticipantRole.SELLER,
    ParticipantRole.ESCROW_OFFICER,
}
User = get_user_model()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _lock_transaction(transaction: Transaction) -> Transaction:
    return Transaction.objects.select_for_update().get(pk=transaction.pk)


def _lock_invitation(invitation: Invitation) -> Invitation:
    return Invitation.objects.select_for_update().select_related(
        "transaction",
        "sent_by_user",
        "target_user",
    ).get(pk=invitation.pk)


def _raise_invitation_integrity_validation_error(error: IntegrityError) -> None:
    message = str(error)
    if "uniq_pending_invitation_per_target_user" in message:
        raise ValidationError({"target_user": "This user already has a pending invitation for this transaction."}) from error
    if "uniq_pending_invitation_per_target_email" in message:
        raise ValidationError({"target_email": "This email already has a pending invitation for this transaction."}) from error
    if "uniq_pending_invitation_per_single_role" in message:
        raise ValidationError({"intended_role": "This role already has a pending invitation in this transaction."}) from error
    raise ValidationError({"invitation": "Invitation conflicts with an existing pending invitation."}) from error


def expire_stale_pending_invitations(
    *,
    transaction_ids=None,
    user=None,
    sync_transactions=True,
) -> int:
    now = timezone.now()
    invitations = Invitation.objects.filter(
        status=InvitationStatus.PENDING,
        expires_at__lte=now,
    )

    if transaction_ids is not None:
        invitations = invitations.filter(transaction_id__in=transaction_ids)

    if user is not None:
        invitations = invitations.filter(
            Q(sent_by_user=user)
            | Q(target_user=user)
            | Q(target_user__isnull=True, target_email__iexact=user.email)
        )

    transaction_ids_to_sync = list(
        invitations.values_list("transaction_id", flat=True).distinct()
    )
    updated_count = invitations.update(status=InvitationStatus.EXPIRED, updated_at=now)

    if updated_count and sync_transactions:
        from .transaction import sync_transaction_setup_status

        for transaction in Transaction.objects.filter(pk__in=transaction_ids_to_sync):
            sync_transaction_setup_status(transaction=transaction)

    return updated_count


def _ensure_sender_can_invite(*, transaction: Transaction, sent_by_user) -> None:
    can_invite = TransactionParticipant.objects.filter(
        transaction=transaction,
        user=sent_by_user,
        status=ParticipantStatus.ACTIVE,
        role__in=BROKER_INVITER_ROLES,
    ).exists()
    if not can_invite:
        raise ValidationError(
            {"sent_by_user": "Only active broker participants can send invitations for this transaction."}
        )


def _ensure_purchase_agreement_uploaded(*, transaction: Transaction) -> None:
    from documents.services.purchase_agreement import transaction_has_purchase_agreement

    if not transaction_has_purchase_agreement(transaction=transaction):
        raise ValidationError(
            {"purchase_agreement": "Upload the purchase agreement before sending invitations."}
        )


def _validate_invitation_role(*, transaction: Transaction, intended_role) -> None:
    if intended_role == ParticipantRole.COOPERATING_BROKER and transaction.transaction_type != TransactionType.DOUBLE_BROKER:
        raise ValidationError({"intended_role": "STANDARD transactions cannot include a cooperating broker."})


def _validate_pending_invitation_conflicts(
    *,
    transaction: Transaction,
    target_user,
    target_email: str,
    intended_role,
) -> None:
    now = timezone.now()

    if target_user and Invitation.objects.filter(
        transaction=transaction,
        target_user=target_user,
        status=InvitationStatus.PENDING,
        expires_at__gt=now,
    ).exists():
        raise ValidationError({"target_user": "This user already has a pending invitation for this transaction."})

    if target_email and Invitation.objects.filter(
        transaction=transaction,
        target_email__iexact=target_email,
        status=InvitationStatus.PENDING,
        expires_at__gt=now,
    ).exists():
        raise ValidationError({"target_email": "This email already has a pending invitation for this transaction."})

    if intended_role in SINGLE_OCCUPANT_INVITATION_ROLES and Invitation.objects.filter(
        transaction=transaction,
        intended_role=intended_role,
        status=InvitationStatus.PENDING,
        expires_at__gt=now,
    ).exists():
        raise ValidationError({"intended_role": "This role already has a pending invitation in this transaction."})


def _mark_invitation_expired(*, invitation: Invitation) -> Invitation:
    if invitation.status != InvitationStatus.PENDING:
        return invitation

    invitation.status = InvitationStatus.EXPIRED
    invitation.save(update_fields=["status", "updated_at"])

    from .transaction import sync_transaction_setup_status

    sync_transaction_setup_status(transaction=invitation.transaction)
    return invitation


def _resolve_acting_user(invitation: Invitation, acting_user):
    if acting_user is not None:
        return acting_user
    if invitation.target_user_id is not None:
        return invitation.target_user
    raise ValidationError({"acting_user": "An authenticated user is required for this invitation."})


def _ensure_invitation_is_pending(*, invitation: Invitation) -> None:
    if invitation.status == InvitationStatus.EXPIRED:
        raise ValidationError({"invitation": "This invitation has expired."})
    if invitation.status != InvitationStatus.PENDING:
        raise ValidationError({"invitation": "This invitation is no longer pending."})


def _ensure_invitation_actor_matches(*, invitation: Invitation, acting_user) -> None:
    if invitation.target_user_id is not None:
        if acting_user.pk != invitation.target_user_id:
            raise ValidationError({"acting_user": "This invitation was sent to a different user."})
        return

    if _normalize_email(invitation.target_email) != _normalize_email(acting_user.email):
        raise ValidationError({"acting_user": "This invitation was sent to a different email address."})


@db_transaction.atomic
def invite_participant(
    *,
    transaction: Transaction,
    sent_by_user,
    intended_role,
    target_user=None,
    target_email="",
    delivery_method="EMAIL",
    expires_at=None,
) -> Invitation:
    transaction = _lock_transaction(transaction)
    expire_stale_pending_invitations(transaction_ids=[transaction.pk], sync_transactions=False)

    _ensure_sender_can_invite(transaction=transaction, sent_by_user=sent_by_user)
    _ensure_purchase_agreement_uploaded(transaction=transaction)
    _validate_invitation_role(transaction=transaction, intended_role=intended_role)

    normalized_email = _normalize_email(target_email)
    if target_user is None and not normalized_email:
        raise ValidationError({"target_email": "Provide target_user or target_email."})

    if target_user is not None:
        target_user_email = _normalize_email(target_user.email)
        if normalized_email and normalized_email != target_user_email:
            raise ValidationError({"target_email": "target_email must match target_user.email when both are provided."})
        normalized_email = target_user_email

    if expires_at is None:
        expires_at = timezone.now() + timedelta(days=7)
    if expires_at <= timezone.now():
        raise ValidationError({"expires_at": "expires_at must be in the future."})

    from .participant import validate_participant_role_assignment

    if target_user is not None:
        validate_participant_role_assignment(
            transaction=transaction,
            user=target_user,
            role=intended_role,
        )
    else:
        target_email_user = User.objects.filter(email__iexact=normalized_email).first()
        if target_email_user is not None:
            validate_participant_role_assignment(
                transaction=transaction,
                user=target_email_user,
                role=intended_role,
            )

    if target_user is None and intended_role in SINGLE_OCCUPANT_INVITATION_ROLES and TransactionParticipant.objects.filter(
        transaction=transaction,
        role=intended_role,
        status=ParticipantStatus.ACTIVE,
    ).exists():
        raise ValidationError({"intended_role": "This role is already assigned in this transaction."})

    _validate_pending_invitation_conflicts(
        transaction=transaction,
        target_user=target_user,
        target_email=normalized_email,
        intended_role=intended_role,
    )

    invitation = Invitation(
        transaction=transaction,
        sent_by_user=sent_by_user,
        target_user=target_user,
        target_email=normalized_email,
        intended_role=intended_role,
        delivery_method=delivery_method,
        token=secrets.token_urlsafe(32),
        status=InvitationStatus.PENDING,
        expires_at=expires_at,
    )
    invitation.full_clean()
    try:
        with db_transaction.atomic():
            invitation.save()
    except IntegrityError as error:
        _raise_invitation_integrity_validation_error(error)

    from .transaction import sync_transaction_setup_status

    sync_transaction_setup_status(transaction=transaction)
    return invitation


def accept_invitation(*, invitation: Invitation, acting_user=None) -> TransactionParticipant:
    invitation_id = invitation.pk

    with db_transaction.atomic():
        invitation = _lock_invitation(invitation)
        acting_user = _resolve_acting_user(invitation, acting_user)
        _ensure_invitation_is_pending(invitation=invitation)

        if invitation.expires_at > timezone.now():
            _ensure_invitation_actor_matches(invitation=invitation, acting_user=acting_user)

            from .participant import add_participant

            participant = add_participant(
                transaction=invitation.transaction,
                user=acting_user,
                role=invitation.intended_role,
                status=ParticipantStatus.ACTIVE,
            )

            responded_at = timezone.now()
            invitation.target_user = invitation.target_user or acting_user
            invitation.status = InvitationStatus.ACCEPTED
            invitation.responded_at = responded_at
            invitation.accepted_at = responded_at
            invitation.accepted_participant = participant
            invitation.full_clean()
            invitation.save()

            return participant

    expire_invitation(invitation=Invitation.objects.get(pk=invitation_id))
    raise ValidationError({"invitation": "This invitation has expired."})


def reject_invitation(*, invitation: Invitation, acting_user=None) -> Invitation:
    invitation_id = invitation.pk

    with db_transaction.atomic():
        invitation = _lock_invitation(invitation)
        acting_user = _resolve_acting_user(invitation, acting_user)
        _ensure_invitation_is_pending(invitation=invitation)

        if invitation.expires_at > timezone.now():
            _ensure_invitation_actor_matches(invitation=invitation, acting_user=acting_user)

            responded_at = timezone.now()
            invitation.target_user = invitation.target_user or acting_user
            invitation.status = InvitationStatus.DECLINED
            invitation.responded_at = responded_at
            invitation.declined_at = responded_at
            invitation.full_clean()
            invitation.save()

            from .transaction import sync_transaction_setup_status

            sync_transaction_setup_status(transaction=invitation.transaction)
            return invitation

    expire_invitation(invitation=Invitation.objects.get(pk=invitation_id))
    raise ValidationError({"invitation": "This invitation has expired."})


@db_transaction.atomic
def expire_invitation(*, invitation: Invitation) -> Invitation:
    invitation = _lock_invitation(invitation)
    if invitation.expires_at > timezone.now():
        raise ValidationError({"invitation": "This invitation has not expired yet."})
    return _mark_invitation_expired(invitation=invitation)


@db_transaction.atomic
def revoke_invitation(*, invitation: Invitation, acting_user) -> Invitation:
    invitation = _lock_invitation(invitation)
    if invitation.status != InvitationStatus.PENDING:
        raise ValidationError({"invitation": "Only pending invitations can be revoked."})

    can_revoke = TransactionParticipant.objects.filter(
        transaction=invitation.transaction,
        user=acting_user,
        status=ParticipantStatus.ACTIVE,
        role__in=BROKER_INVITER_ROLES,
    ).exists()
    if not can_revoke:
        raise ValidationError(
            {"acting_user": "Only active broker participants can revoke invitations for this transaction."}
        )

    if invitation.expires_at <= timezone.now():
        return _mark_invitation_expired(invitation=invitation)

    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = timezone.now()
    invitation.full_clean()
    invitation.save()

    from .transaction import sync_transaction_setup_status

    sync_transaction_setup_status(transaction=invitation.transaction)
    return invitation
