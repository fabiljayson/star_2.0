from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.logbook.models import SurgicalProcedure
from apps.organizations.models import Department, Institution, Specialty

# Default evaluation scale — kept separate from quantitative procedure
# counts: reaching a count never makes a trainee "competent".
DEFAULT_RUBRIC_TEMPLATE: dict = {
    "scale": [
        {"key": "novice", "label": "Novice", "rank": 1},
        {"key": "advanced_beginner", "label": "Advanced beginner", "rank": 2},
        {"key": "competent", "label": "Competent", "rank": 3},
        {"key": "proficient", "label": "Proficient", "rank": 4},
        {"key": "expert", "label": "Expert", "rank": 5},
    ],
    "criteria": [
        {"key": "planning", "label": "Indication and planning"},
        {"key": "technique", "label": "Operative technique"},
        {"key": "safety", "label": "Safety and complication management"},
        {"key": "professionalism", "label": "Professionalism and teamwork"},
    ],
}


# ── Status enums ───────────────────────────────────────────────────────
class PlacementStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class AssessmentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    NEEDS_CORRECTION = "needs_correction", "Needs correction"
    REJECTED = "rejected", "Rejected"


# ── Competency catalog ─────────────────────────────────────────────────
class Competency(UUIDModel, TimeStampedModel):
    """Institution-scoped competency catalog entry."""

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="competencies"
    )
    code = models.CharField(max_length=32, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    specialty = models.ForeignKey(
        Specialty, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="competencies",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = "competency"
        verbose_name_plural = "competencies"
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"], name="uniq_competency_per_institution"
            ),
        ]
        indexes = [
            models.Index(fields=["institution", "is_active"], name="comp_inst_active"),
        ]

    def clean(self):
        super().clean()
        if self.code and not self.code.strip():
            raise ValidationError({"code": "Code cannot be blank."})

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.title}"


class CompetencyRubricVersion(UUIDModel, TimeStampedModel):
    """Immutable rubric snapshot; assessments keep referencing their version."""

    competency = models.ForeignKey(
        Competency, on_delete=models.CASCADE, related_name="rubric_versions"
    )
    version = models.PositiveIntegerField()
    levels = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    is_current = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="rubric_versions_created",
    )

    class Meta:
        ordering = ["-version"]
        verbose_name = "competency rubric version"
        verbose_name_plural = "competency rubric versions"
        constraints = [
            models.UniqueConstraint(
                fields=["competency", "version"], name="uniq_rubric_version"
            ),
        ]

    @staticmethod
    def default_levels() -> dict:
        import copy

        return copy.deepcopy(DEFAULT_RUBRIC_TEMPLATE)

    @property
    def scale_keys(self) -> set[str]:
        return {level.get("key") for level in self.levels.get("scale", [])}

    @property
    def criterion_keys(self) -> set[str]:
        return {c.get("key") for c in self.levels.get("criteria", [])}

    def __str__(self):
        return f"{self.competency.code} rubric v{self.version}"


# ── Training placements ────────────────────────────────────────────────
class TrainingPlacement(UUIDModel, TimeStampedModel):
    """A trainee's assignment to an institution/department/period."""

    title = models.CharField(max_length=200)
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="training_placements"
    )
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="training_placements",
    )
    trainee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="placements_as_trainee",
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="placements_supervised",
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PlacementStatus.choices,
        default=PlacementStatus.ACTIVE,
        db_index=True,
    )
    objectives = models.TextField(blank=True)
    closure_reason = models.TextField(blank=True)
    expected_competencies = models.ManyToManyField(
        Competency, blank=True, related_name="placements"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="placements_created",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "training placement"
        verbose_name_plural = "training placements"
        constraints = [
            models.UniqueConstraint(
                fields=["trainee"],
                condition=models.Q(status="active"),
                name="uniq_active_placement_per_trainee",
            ),
        ]
        indexes = [
            models.Index(fields=["institution", "status"], name="place_inst_status"),
            models.Index(fields=["trainee", "status"], name="place_trainee_status"),
        ]

    def clean(self):
        super().clean()
        if self.department_id and self.institution_id:
            if self.department.institution_id != self.institution_id:
                raise ValidationError(
                    {"department": "Department does not belong to this institution."}
                )
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date is before the start date."})
        if self.trainee_id and self.institution_id:
            from apps.accounts.models import RoleAssignment, UserRole

            has_trainee_role = RoleAssignment.objects.filter(
                user=self.trainee_id,
                institution_id=self.institution_id,
                role=UserRole.TRAINEE,
                is_active=True,
            ).exists()
            if not has_trainee_role:
                raise ValidationError(
                    {"trainee": "This user does not hold a trainee role here."}
                )
        if (
            self.supervisor_id
            and self.trainee_id
            and self.supervisor_id == self.trainee_id
        ):
            raise ValidationError(
                {"supervisor": "A trainee cannot supervise their own placement."}
            )
        if self.supervisor_id and self.institution_id:
            from apps.accounts.models import RoleAssignment, UserRole

            has_supervisor_role = RoleAssignment.objects.filter(
                user=self.supervisor_id,
                institution_id=self.institution_id,
                role=UserRole.SUPERVISOR,
                is_active=True,
            ).exists()
            if not has_supervisor_role:
                raise ValidationError(
                    {"supervisor": "This user does not hold a supervisor role here."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        return self.status == PlacementStatus.ACTIVE

    def __str__(self):
        return f"{self.title} · {self.trainee.email} ({self.status})"


class ExaminerAssignment(UUIDModel, TimeStampedModel):
    """Explicit examiner authorization for one placement."""

    placement = models.ForeignKey(
        TrainingPlacement, on_delete=models.CASCADE, related_name="examiner_assignments"
    )
    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="examiner_placement_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="examiner_assignments_made",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "examiner assignment"
        verbose_name_plural = "examiner assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["placement", "examiner"], name="uniq_examiner_per_placement"
            ),
        ]

    def clean(self):
        super().clean()
        if not self.placement_id or not self.examiner_id:
            return
        from apps.accounts.models import RoleAssignment, UserRole

        if self.examiner_id == self.placement.trainee_id:
            raise ValidationError(
                {"examiner": "A trainee cannot examine their own placement."}
            )
        if not self.examiner.is_active:
            raise ValidationError({"examiner": "This account is inactive."})
        has_examiner_role = RoleAssignment.objects.filter(
            user=self.examiner_id,
            institution_id=self.placement.institution_id,
            role=UserRole.EXAMINER,
            is_active=True,
        ).exists()
        if not has_examiner_role:
            raise ValidationError(
                {"examiner": "This user does not hold an examiner role here."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.examiner.email} · {self.placement.title}"


# ── Competency assessments ─────────────────────────────────────────────
class Assessment(UUIDModel, TimeStampedModel):
    """Qualitative competency rating for one trainee/placement/competency.

    Scores are validated against the pinned rubric version, so historical
    assessments stay interpretable after rubric changes.
    """

    placement = models.ForeignKey(
        TrainingPlacement, on_delete=models.CASCADE, related_name="assessments"
    )
    competency = models.ForeignKey(
        Competency, on_delete=models.PROTECT, related_name="assessments"
    )
    rubric_version = models.ForeignKey(
        CompetencyRubricVersion, on_delete=models.PROTECT, related_name="assessments"
    )
    procedure = models.ForeignKey(
        SurgicalProcedure, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="competency_assessments",
    )
    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="assessments_made",
    )
    status = models.CharField(
        max_length=24,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.DRAFT,
        db_index=True,
    )
    scores = models.JSONField(default=dict, blank=True)
    overall_level = models.CharField(max_length=64, blank=True)
    feedback = models.TextField(blank=True)
    decision_reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assessment_decisions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "competency assessment"
        verbose_name_plural = "competency assessments"
        indexes = [
            models.Index(fields=["placement", "status"], name="assess_place_status"),
            models.Index(fields=["status", "-created_at"], name="assess_status_time"),
            models.Index(fields=["competency", "status"], name="assess_comp_status"),
        ]

    def clean(self):
        super().clean()
        if not self.placement_id or not self.competency_id or not self.rubric_version_id:
            return
        if self.competency.institution_id != self.placement.institution_id:
            raise ValidationError(
                {"competency": "Competency belongs to a different institution."}
            )
        if self.rubric_version.competency_id != self.competency_id:
            raise ValidationError(
                {"rubric_version": "Rubric version belongs to another competency."}
            )
        if self.procedure_id and self.placement_id:
            if self.procedure.institution_id != self.placement.institution_id:
                raise ValidationError(
                    {"procedure": "Procedure belongs to a different institution."}
                )
        scale_keys = self.rubric_version.scale_keys
        if self.overall_level and scale_keys and self.overall_level not in scale_keys:
            raise ValidationError(
                {"overall_level": "Unknown rating level for this rubric."}
            )
        criteria = self.rubric_version.criterion_keys
        for key, value in (self.scores or {}).items():
            if criteria and key not in criteria:
                raise ValidationError(
                    {"scores": f"Unknown criterion '{key}' for this rubric."}
                )
            if scale_keys and value not in scale_keys:
                raise ValidationError(
                    {"scores": f"Unknown rating level '{value}' for this rubric."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status in {
            AssessmentStatus.DRAFT,
            AssessmentStatus.NEEDS_CORRECTION,
        }

    def __str__(self):
        return f"{self.competency.code} · {self.placement.trainee.email} ({self.status})"
