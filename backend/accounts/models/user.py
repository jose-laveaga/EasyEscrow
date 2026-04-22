from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from ..validators import name_place_validator, phone_validator


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is False:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is False:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    first_name = models.CharField(
        max_length=150,
        blank=True,
        validators=[name_place_validator],
    )
    middle_name = models.CharField(
        max_length=150,
        blank=True,
        validators=[name_place_validator],
    )
    last_name = models.CharField(
        max_length=150,
        blank=True,
        validators=[name_place_validator],
    )
    email = models.EmailField(unique=True)
    phone = models.CharField(
        max_length=13,
        blank=True,
        validators=[phone_validator],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.first_name:
            self.first_name = self.first_name.strip()
        if self.middle_name:
            self.middle_name = self.middle_name.strip()
        if self.last_name:
            self.last_name = self.last_name.strip()
        if self.phone:
            self.phone = self.phone.strip()
        super().save(*args, **kwargs)
