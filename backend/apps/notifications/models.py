from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Institution


class NotificationCategory(models.TextChoices):
    PROCEDURE_SUBMITTED = "procedure_submitted", "Record submitted for review"
    PROCEDURE_APPROVED = "procedure_approved", "Record approved"
    PROCEDURE_RETURNED = "procedure_returned", "Record returned for correction"
    PLACEMENT_UPDATE = "placement_update", "Training placement update"
    EXAMINER_ASSIGNED = "examiner_assigned", "Examiner assignment"
    ASSESSMENT_SUBMITTED = "assessment_submitted", "Assessment awaiting decision"
    ASSESSMENT_RESULT = "assessment_result", "Assessment decision"
    ASSESSMENT_CORRECTION = "assessment_correction", "Assessment corrections requested"


# All categories shown in the preference center (order matters for the UI).
ALL_CATEGORIES = tuple(NotificationCategory.values)


class Notification(UUIDModel, TimeStampedModel):
    """In-app message for one recipient.

    Previews (title/body) must stay generic: no patient identifiers, no
    clinical note text, no secrets — the authoritative content always lives
    behind the permission-checked `link`.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    institution = models.ForeignKey(
        Institution, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="notifications",
    )
    category = models.CharField(max_length=32, choices=NotificationCategory.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="notifications_sent",
    )
    object_type = models.CharField(max_length=64, blank=True)
    object_pk = models.CharField(max_length=64, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notif_recipient_read",
            ),
            models.Index(
                fields=["recipient", "category"], name="notif_recipient_category"
            ),
        ]

    def __str__(self):
        return f"{self.recipient.email} · {self.category} · {self.title}"


class NotificationPreference(UUIDModel, TimeStampedModel):
    """Per-user channel toggles; absent rows mean platform defaults."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    category = models.CharField(max_length=32, choices=NotificationCategory.choices)
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=False)

    class Meta:
        ordering = ["category"]
        verbose_name = "notification preference"
        verbose_name_plural = "notification preferences"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"], name="uniq_notification_pref"
            ),
        ]

    def __str__(self):
        return f"{self.user.email} · {self.category} · in_app={self.in_app}"
