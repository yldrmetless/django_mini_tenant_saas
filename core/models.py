import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


# Create your models here.
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(models.Model):
    name = models.CharField(max_length=255)

    slug = models.SlugField(unique=True)

    is_active = models.BooleanField(default=True)

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    owner_email = models.EmailField(blank=True, null=True)

    plan = models.CharField(max_length=100, default="free")

    max_users = models.IntegerField(default=1)

    def __str__(self):
        return self.name


class Invitation(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    invited_by = models.ForeignKey(
        "users.Users",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )

    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=2)
        super().save(*args, **kwargs)

    def is_valid(self):
        return (not self.is_used) and (timezone.now() < self.expires_at)


PROJECT_STATUS_CHOICES = [
    ("active", "Active"),
    ("on_hold", "On Hold"),
    ("test", "Test"),
    ("archived", "Archived"),
    ("completed", "Completed"),
]


class Projects(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="projects"
    )

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=20, choices=PROJECT_STATUS_CHOICES, default="active"
    )

    created_by = models.ForeignKey(
        "users.Users",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )

    is_deleted = models.BooleanField(default=False)

    appointed_person = models.ForeignKey(
        "users.Users",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointed_projects",
    )

    def __str__(self):
        return self.name
