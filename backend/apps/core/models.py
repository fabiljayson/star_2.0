import uuid

from django.conf import settings
from django.db import models


# ── Abstract bases ─────────────────────────────────────────────────────
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


# ── Audit trail ────────────────────────────────────────────────────────
class AuditEvent(UUIDModel, TimeStampedModel):
    """Append-only security/business audit trail.

    Metadata must never contain clinical text, passwords, tokens or payment
    secrets — callers pass non-sensitive values only.
    """

    class Action(models.TextChoices):
        AUTH_REGISTERED = "auth.registered", "Account registered"
        AUTH_EMAIL_VERIFIED = "auth.email_verified", "Email verified"
        AUTH_LOGIN = "auth.login", "Login succeeded"
        AUTH_LOGOUT = "auth.logout", "Logout"
        AUTH_LOGOUT_ALL = "auth.logout_all", "All sessions revoked"
        AUTH_PASSWORD_RESET_REQUESTED = (
            "auth.password_reset_requested",
            "Password reset requested",
        )
        AUTH_PASSWORD_RESET = "auth.password_reset", "Password reset completed"
        AUTH_MFA_ENABLED = "auth.mfa_enabled", "MFA enabled"
        AUTH_MFA_DISABLED = "auth.mfa_disabled", "MFA disabled"
        USER_UPDATED = "user.updated", "Profile updated"
        INSTITUTION_CREATED = "institution.created", "Institution created"
        INSTITUTION_UPDATED = "institution.updated", "Institution updated"
        DEPARTMENT_CREATED = "department.created", "Department created"
        DEPARTMENT_UPDATED = "department.updated", "Department updated"
        DEPARTMENT_DELETED = "department.deleted", "Department deleted"
        SPECIALTY_CREATED = "specialty.created", "Specialty created"
        ROLE_GRANTED = "role.granted", "Role granted"
        ROLE_UPDATED = "role.updated", "Role updated"
        ROLE_REVOKED = "role.revoked", "Role revoked"
        INVITATION_SENT = "invitation.sent", "Invitation sent"
        INVITATION_ACCEPTED = "invitation.accepted", "Invitation accepted"
        INVITATION_REVOKED = "invitation.revoked", "Invitation revoked"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    actor_email = models.EmailField(blank=True, db_index=True)
    action = models.CharField(max_length=64, choices=Action.choices, db_index=True)
    object_type = models.CharField(max_length=64, blank=True, db_index=True)
    object_pk = models.CharField(max_length=64, blank=True)
    institution = models.ForeignKey(
        "organizations.Institution",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["institution", "-created_at"], name="audit_inst_time"),
            models.Index(fields=["actor", "-created_at"], name="audit_actor_time"),
            models.Index(fields=["action", "-created_at"], name="audit_action_time"),
        ]
        verbose_name = "audit event"
        verbose_name_plural = "audit events"

    def __str__(self):
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
