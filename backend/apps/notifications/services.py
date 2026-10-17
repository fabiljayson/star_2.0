from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User

from .models import ALL_CATEGORIES, Notification, NotificationPreference


def _prefers(user: User, category: str) -> bool:
    preference = NotificationPreference.objects.filter(
        user=user, category=category
    ).first()
    if preference is None:
        return True  # platform default: in-app on
    return preference.in_app


def notify(
    *,
    recipients,
    category: str,
    title: str,
    body: str = "",
    link: str = "",
    actor=None,
    institution=None,
    object_type: str = "",
    object_pk="",
) -> int:
    """Create in-app notifications; returns how many were actually created.

    Callers are responsible for keeping `title`/`body` free of patient
    identifiers and clinical note text.
    """
    if isinstance(recipients, QuerySet):
        recipients = list(recipients)
    created = 0
    for user in recipients:
        if user is None or not getattr(user, "is_active", False):
            continue
        if not _prefers(user, category):
            continue
        Notification.objects.create(
            recipient=user,
            institution=institution,
            category=category,
            title=title[:200],
            body=body,
            link=link[:500],
            actor=actor,
            object_type=object_type,
            object_pk=str(object_pk or ""),
        )
        created += 1
    return created


def visible_notifications(user) -> Notification:
    if not user or not user.is_authenticated or not user.is_active:
        return Notification.objects.none()
    return Notification.objects.filter(recipient=user)


def unread_count(user) -> int:
    return visible_notifications(user).filter(is_read=False).count()


def _get_own(user, pk) -> Notification:
    notification = visible_notifications(user).filter(pk=pk).first()
    if notification is None:
        raise exceptions.NotFound()
    return notification


def mark_read(user, pk) -> Notification:
    notification = _get_own(user, pk)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_all_read(user) -> int:
    updated = visible_notifications(user).filter(is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    return updated


# ── Preferences ────────────────────────────────────────────────────────
def list_preferences(user) -> list[NotificationPreference]:
    existing = {
        preference.category: preference
        for preference in NotificationPreference.objects.filter(user=user)
    }
    preferences = []
    for category in ALL_CATEGORIES:
        preferences.append(
            existing.get(category)
            or NotificationPreference(user=user, category=category)
        )
    return preferences


def update_preferences(user, items: list[dict]) -> list[NotificationPreference]:
    allowed_fields = {"in_app", "email"}
    for item in items:
        category = item.get("category")
        if category not in ALL_CATEGORIES:
            raise exceptions.ValidationError(
                {"category": f"Unknown notification category '{category}'."}
            )
        unknown = set(item) - {"category"} - allowed_fields
        if unknown:
            raise exceptions.ValidationError(
                {"fields": f"Unsupported fields: {', '.join(sorted(unknown))}."}
            )
        if not allowed_fields & set(item):
            raise exceptions.ValidationError(
                {"fields": "Provide at least 'in_app' or 'email'."}
            )
    for item in items:
        defaults = {key: item[key] for key in allowed_fields if key in item}
        NotificationPreference.objects.update_or_create(
            user=user, category=item["category"], defaults=defaults
        )
    return list_preferences(user)
