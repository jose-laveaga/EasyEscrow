from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import IdentityVerificationStatus, User, UserProfile


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if not created:
        return

    UserProfile.objects.get_or_create(
        user=instance,
        defaults={"status": IdentityVerificationStatus.DRAFT},
    )
