from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


# ── Policy structure ───────────────────────────────────────────────────
class PolicyCategory(models.TextChoices):
    PRIVACY = "privacy", "Privacy"
    TERMS = "terms", "Terms of Service"
    MARKETPLACE = "marketplace", "Marketplace"
    PAYMENTS = "payments", "Subscription & payments"
    CLINICAL = "clinical", "Clinical data"
    DATA_RETENTION = "data_retention", "Cookies & data retention"


class Policy(UUIDModel, TimeStampedModel):
    """One logical policy (stable slug) with bilingual versioned texts."""

    slug = models.SlugField(max_length=140, unique=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=24, choices=PolicyCategory.choices)
    summary = models.TextField(blank=True)
    related_policies = models.ManyToManyField("self", blank=True)
    next_review_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["category", "title"]
        verbose_name = "policy"
        verbose_name_plural = "policies"

    def __str__(self) -> str:
        return self.title

    def published_version(self, language: str):
        """Current published version for a language (never a draft)."""
        return self.versions.filter(
            status=PolicyVersion.Status.PUBLISHED,
            language=language,
        ).order_by("-published_at", "-created_at").first()


class PolicyVersion(UUIDModel, TimeStampedModel):
    """One bilingual text of one policy with its own workflow state."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Superseded"
        ARCHIVED = "archived", "Archived"

    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    translation_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="translations",
        help_text="Source version this text translates (EN ↔ FR link).",
    )
    language = models.CharField(max_length=2, choices=[("en", "English"), ("fr", "French")])
    version = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    effective_date = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, help_text="Reviewer remarks.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="policy_versions_authored",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="policy_versions_approved",
    )

    class Meta:
        ordering = ["policy", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "language", "version"],
                name="uniq_policy_version_per_language",
            ),
            # One binding published text per policy and language.
            models.UniqueConstraint(
                fields=["policy", "language"],
                condition=models.Q(status="published"),
                name="uniq_published_version_per_policy_language",
            ),
        ]
        indexes = [
            models.Index(fields=["policy", "language", "-published_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.policy.slug} {self.language}/{self.version} ({self.status})"

    def clean(self) -> None:
        if self.status == self.Status.PUBLISHED and self.effective_date is None:
            raise ValidationError(
                {"effective_date": "A published policy needs an effective date."}
            )

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED


# ── Consent trail ──────────────────────────────────────────────────────
class ConsentContext(models.TextChoices):
    REGISTRATION = "registration", "Registration"
    ACCOUNT = "account", "Account settings"
    MARKETPLACE = "marketplace", "Marketplace checkout"
    SUBSCRIPTION = "subscription", "Seller subscription"
    CLINICAL = "clinical", "Clinical documentation"
    MOBILE = "mobile", "Mobile app"


class PolicyConsent(UUIDModel, TimeStampedModel):
    """Immutable record: user accepted one exact published policy version."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="policy_consents",
    )
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="consents")
    policy_version = models.ForeignKey(
        PolicyVersion,
        on_delete=models.PROTECT,
        related_name="consents",
    )
    context = models.CharField(max_length=24, choices=ConsentContext.choices)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["policy", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.policy.slug} {self.policy_version.version}"

    def clean(self) -> None:
        version = self.policy_version
        if version.policy_id != self.policy_id:
            raise ValidationError("Consent policy must match the recorded version.")
        if version.status != PolicyVersion.Status.PUBLISHED:
            raise ValidationError("Only published versions can be consented to.")


# ── Privacy requests ──────────────────────────────────────────────────
class PrivacyRequest(UUIDModel, TimeStampedModel):
    """User privacy petition (access / export / deletion…), handled by admins."""

    class Kind(models.TextChoices):
        ACCESS = "access", "Access my data"
        EXPORT = "export", "Export my data"
        DELETION = "deletion", "Delete my account data"
        CORRECTION = "correction", "Correct my data"
        OTHER = "other", "Other request"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_REVIEW = "in_review", "In review"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privacy_requests",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    message = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="privacy_requests_handled",
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    response_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.kind} ({self.status}) · user {self.user_id}"


def supersede_published(policy: Policy, language: str, new_version: PolicyVersion):
    """Publish an approved version and retire the sibling that was live.

    Only approved texts may enter the published slot: this function is the
    single write path to `published`, so a draft or a pending translation can
    never go live by being passed here.
    """
    version = new_version
    if version.policy_id != policy.pk:
        raise ValidationError("Version does not belong to this policy.")
    if version.language != language:
        raise ValidationError("Version language does not match the published slot.")
    if version.status != PolicyVersion.Status.APPROVED:
        raise ValidationError(
            {"status": "Only an approved version can become the published text."}
        )
    with transaction.atomic():
        for existing in policy.versions.filter(
            status=PolicyVersion.Status.PUBLISHED,
            language=language,
        ).exclude(pk=version.pk):
            existing.status = PolicyVersion.Status.SUPERSEDED
            existing.save(update_fields=["status", "updated_at"])
        version.status = PolicyVersion.Status.PUBLISHED
        version.published_at = timezone.now()
        version.save(update_fields=["status", "published_at", "updated_at"])
