import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import INSTITUTION_SCOPED_ROLES, UserRole
from apps.core.models import TimeStampedModel, UUIDModel

INVITATION_TTL = timedelta(days=7)


# ── Organization structure ─────────────────────────────────────────────
class InstitutionType(models.TextChoices):
    HOSPITAL = "hospital", "Hospital"
    UNIVERSITY = "university", "University / faculty"
    CLINIC = "clinic", "Clinic"
    TRAINING_CENTER = "training_center", "Training center"
    OTHER = "other", "Other"


class Institution(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    institution_type = models.CharField(
        max_length=32,
        choices=InstitutionType.choices,
        default=InstitutionType.HOSPITAL,
    )
    country = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "institution"
        verbose_name_plural = "institutions"
        indexes = [models.Index(fields=["name"], name="institution_name_idx")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "institution"
            slug = base
            suffix = 2
            while Institution.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Department(UUIDModel, TimeStampedModel):
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="departments"
    )
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["institution__name", "name"]
        verbose_name = "department"
        verbose_name_plural = "departments"
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"],
                condition=~models.Q(code=""),
                name="uniq_department_code_per_institution",
            ),
        ]

    def clean(self):
        super().clean()
        if Department.objects.filter(
            institution=self.institution, name__iexact=self.name
        ).exclude(pk=self.pk).exists():
            raise ValidationError({"name": "A department with this name already exists."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.institution.name})"


class Specialty(UUIDModel, TimeStampedModel):
    """Global surgical specialty catalog."""

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "specialty"
        verbose_name_plural = "specialties"

    def __str__(self):
        return self.name


# ── Invitations ────────────────────────────────────────────────────────
class Invitation(UUIDModel, TimeStampedModel):
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=40, choices=UserRole.choices)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="sent_invitations",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_invitations",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "invitation"
        verbose_name_plural = "invitations"
        indexes = [
            models.Index(fields=["institution", "-created_at"], name="invite_inst_time"),
            models.Index(fields=["email", "expires_at"], name="invite_email_time"),
        ]

    def clean(self):
        super().clean()
        if self.role not in INSTITUTION_SCOPED_ROLES:
            raise ValidationError({"role": "Only institutional roles can be invited."})
        if self.department_id and self.institution_id:
            if self.department.institution_id != self.institution_id:
                raise ValidationError(
                    {"department": "Department does not belong to this institution."}
                )

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + INVITATION_TTL
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_valid(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"{self.email} → {self.institution.name} ({self.role})"
