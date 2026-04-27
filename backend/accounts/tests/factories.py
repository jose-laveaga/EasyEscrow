from django.utils import timezone
import factory

from accounts.models import (
    BrokerProfile,
    BrokerType,
    IdentityVerificationStatus,
    User,
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = "Test"
    last_name = "User"
    password = "testpass123"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123")
        return model_class.objects.create_user(*args, password=password, **kwargs)


class BrokerProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BrokerProfile
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    broker_type = BrokerType.INDIVIDUAL
    is_active_broker = True
    approved_at = factory.LazyFunction(timezone.now)

    @factory.post_generation
    def verified_identity(self, create, extracted, **kwargs):
        if not create:
            return

        profile = self.user.profile
        profile.status = IdentityVerificationStatus.VERIFIED
        profile.verified_at = profile.verified_at or timezone.now()
        profile.save(update_fields=["status", "verified_at", "updated_at"])


class EligibleBrokerUserFactory(UserFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    @factory.post_generation
    def broker_profile(self, create, extracted, **kwargs):
        if not create:
            return

        profile = self.profile
        profile.status = IdentityVerificationStatus.VERIFIED
        profile.verified_at = profile.verified_at or timezone.now()
        profile.save(update_fields=["status", "verified_at", "updated_at"])

        BrokerProfile.objects.get_or_create(
            user=self,
            defaults={
                "broker_type": BrokerType.INDIVIDUAL,
                "is_active_broker": True,
                "approved_at": timezone.now(),
            },
        )
