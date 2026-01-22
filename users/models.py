from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

USER_TYPE_CHOICES = (
    (1, "Admin"),
    (2, "Member"),
    (3, "Tester"),
)


class Users(AbstractUser):
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )
    is_active = models.BooleanField(default=True)

    is_deleted = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES, default=2)
