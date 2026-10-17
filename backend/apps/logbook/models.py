import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Department, Institution, Specialty

from .uploads import private_storage

# Fields snapshotted into every ProcedureNoteVersion.
NOTE_SNAPSHOT_FIELDS = (
    "procedure_name",
    "indication",
    "summary",
    "complications",
    "postoperative",
    "training_objectives",
)


# ── Status enums ───────────────────────────────────────────────────────
class ProcedureStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under review"
    APPROVED = "approved", "Approved"
    RETURNED = "returned", "Returned for correction"
    ARCHIVED = "archived", "Archived"


class ParticipantRole(models.TextChoices):
    PRIMARY_OPERATOR = "primary_operator", "Primary operator"
    ASSISTANT = "assistant", "Assistant"
    OBSERVER = "observer", "Observer"


class ReviewDecisionType(models.TextChoices):
    START_REVIEW = "start_review", "Review started"
    APPROVE = "approve", "Approve"
    REQUEST_CORRECTION = "request_correction", "Request correction"
    REJECT = "reject", "Reject"


class VersionChangeKind(models.TextChoices):
    SUBMITTED = "submitted", "Submitted snapshot"
    CORRECTION = "correction", "Post-approval correction"


# ── Pseudonymized patient references ───────────────────────────────────
class PatientReference(UUIDModel, TimeStampedModel):
    """Random pseudonymous patient code, unique inside one institution.

    The code is generated from `secrets`, never derived from names, dates of
    birth or any other identifier, and no re-identification mapping is stored
    by STAR itself (the authoritative mapping stays in the hospital record
    system outside this platform).
    """

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="patient_references"
    )
    code = models.CharField(max_length=32, db_index=True)
    label = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional non-identifying working label (e.g. 'OR-3 case').",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_patient_references",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "patient reference"
        verbose_name_plural = "patient references"
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"], name="uniq_patient_ref_per_institution"
            ),
        ]
        indexes = [
            models.Index(fields=["institution", "is_active"], name="patref_inst_active"),
        ]

    @staticmethod
    def generate_code() -> str:
        return f"PR-{secrets.token_hex(4).upper()}"

    def save(self, *args, **kwargs):
        if not self.code:
            code = self.generate_code()
            while PatientReference.objects.filter(
                institution=self.institution, code=code
            ).exists():
                code = self.generate_code()
            self.code = code
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} ({self.institution.name})"


# ── Surgical records ───────────────────────────────────────────────────
def _new_reference() -> str:
    return f"STAR-{timezone.now().year}-{secrets.token_hex(3).upper()}"


class SurgicalProcedure(UUIDModel, TimeStampedModel):
    class Category(models.TextChoices):
        ELECTIVE = "elective", "Elective"
        EMERGENCY = "emergency", "Emergency"
        TRAUMA = "trauma", "Trauma"
        DIAGNOSTIC = "diagnostic", "Diagnostic"
        OTHER = "other", "Other"

    reference = models.CharField(
        max_length=32, unique=True, default=_new_reference, editable=False, db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=ProcedureStatus.choices,
        default=ProcedureStatus.DRAFT,
        db_index=True,
    )
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="procedures"
    )
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="procedures",
    )
    specialty = models.ForeignKey(
        Specialty, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="procedures",
    )
    patient_reference = models.ForeignKey(
        PatientReference, null=True, blank=True, on_delete=models.PROTECT,
        related_name="procedures",
    )
    procedure_date = models.DateField(db_index=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.ELECTIVE
    )
    procedure_name = models.CharField(max_length=200)
    indication = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    complications = models.TextField(blank=True)
    postoperative = models.TextField(blank=True)
    training_objectives = models.TextField(blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_procedures"
    )
    version = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-procedure_date", "-created_at"]
        verbose_name = "surgical procedure"
        verbose_name_plural = "surgical procedures"
        indexes = [
            models.Index(fields=["institution", "status"], name="proc_inst_status"),
            models.Index(fields=["institution", "procedure_date"], name="proc_inst_date"),
            models.Index(fields=["author", "-procedure_date"], name="proc_author_date"),
            models.Index(fields=["status", "-procedure_date"], name="proc_status_date"),
        ]

    def clean(self):
        super().clean()
        if self.department_id and self.institution_id:
            if self.department.institution_id != self.institution_id:
                raise ValidationError(
                    {"department": "Department does not belong to this institution."}
                )
        if self.patient_reference_id and self.institution_id:
            if self.patient_reference.institution_id != self.institution_id:
                raise ValidationError(
                    {
                        "patient_reference": (
                            "Patient reference belongs to a different institution."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status in {
            ProcedureStatus.DRAFT,
            ProcedureStatus.RETURNED,
            ProcedureStatus.APPROVED,
        }

    def __str__(self):
        return f"{self.reference} · {self.procedure_name} ({self.status})"


class ProcedureParticipant(UUIDModel, TimeStampedModel):
    procedure = models.ForeignKey(
        SurgicalProcedure, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="procedure_participations"
    )
    role = models.CharField(max_length=32, choices=ParticipantRole.choices)

    class Meta:
        ordering = ["role", "created_at"]
        verbose_name = "procedure participant"
        verbose_name_plural = "procedure participants"
        constraints = [
            models.UniqueConstraint(
                fields=["procedure", "user"], name="uniq_participant_per_procedure"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "role"], name="participant_user_role"),
        ]

    def clean(self):
        super().clean()
        if self.procedure_id and self.user_id:
            if self.user_id == self.procedure.author_id:
                raise ValidationError(
                    {"user": "The record author is tracked separately and is not a participant."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} · {self.role} · {self.procedure.reference}"


class ProcedureNoteVersion(UUIDModel, TimeStampedModel):
    """Immutable snapshot of the note fields at a meaningful point in time."""

    procedure = models.ForeignKey(
        SurgicalProcedure, on_delete=models.CASCADE, related_name="note_versions"
    )
    version = models.PositiveIntegerField()
    change_kind = models.CharField(max_length=20, choices=VersionChangeKind.choices)
    snapshot = models.JSONField(default=dict)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="note_version_changes",
    )
    change_summary = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "procedure note version"
        verbose_name_plural = "procedure note versions"
        constraints = [
            models.UniqueConstraint(
                fields=["procedure", "version"], name="uniq_note_version_per_procedure"
            ),
        ]

    def __str__(self):
        return f"{self.procedure.reference} v{self.version} ({self.change_kind})"


class ReviewDecision(UUIDModel, TimeStampedModel):
    procedure = models.ForeignKey(
        SurgicalProcedure, on_delete=models.CASCADE, related_name="review_decisions"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="review_decisions",
    )
    decision = models.CharField(max_length=32, choices=ReviewDecisionType.choices)
    from_status = models.CharField(max_length=20, choices=ProcedureStatus.choices)
    to_status = models.CharField(max_length=20, choices=ProcedureStatus.choices)
    reason = models.TextField(blank=True)
    review_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "review decision"
        verbose_name_plural = "review decisions"

    def clean(self):
        super().clean()
        if self.decision in {
            ReviewDecisionType.REQUEST_CORRECTION,
            ReviewDecisionType.REJECT,
        } and not self.reason.strip():
            raise ValidationError(
                {"reason": "A reason is required when a record is not approved."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.procedure.reference} → {self.decision} ({self.from_status})"


# ── Attachments ────────────────────────────────────────────────────────
class Attachment(UUIDModel, TimeStampedModel):
    procedure = models.ForeignKey(
        SurgicalProcedure, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        max_length=500,
        upload_to="procedures/%Y/%m/",
        storage=private_storage,
    )
    original_name = models.CharField(max_length=255)
    declared_content_type = models.CharField(max_length=100, blank=True)
    detected_kind = models.CharField(max_length=32, blank=True)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_attachments",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "attachment"
        verbose_name_plural = "attachments"

    @property
    def download_name(self) -> str:
        safe = "".join(
            ch for ch in self.original_name if ch.isalnum() or ch in " ._-()"
        ).strip() or "attachment"
        return f"{self.procedure.reference}_{safe}"

    def __str__(self):
        return f"{self.original_name} ({self.procedure.reference})"
