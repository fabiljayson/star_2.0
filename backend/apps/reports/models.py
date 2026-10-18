from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel
from apps.logbook.uploads import private_storage


class ReportType(models.TextChoices):
    INDIVIDUAL_LOGBOOK = "individual_logbook", "Individual surgical logbook"
    ACTIVITY_BY_DATE = "activity_by_date", "Activity by date range"
    ACTIVITY_BY_SPECIALTY = "activity_by_specialty", "Activity by specialty and institution"
    PARTICIPATION_ROLES = "participation_roles", "Procedures grouped by participation role"
    TRAINEE_PROGRESS = "trainee_progress", "Trainee progress report"
    COMPETENCY_ASSESSMENTS = "competency_assessments", "Competency assessment report"
    EXAMINER_REVIEWS = "examiner_reviews", "Examiner review report"
    PLACEMENT_COMPLETION = "placement_completion", "Placement completion report"
    INSTITUTION_SUMMARY = "institution_summary", "Institution-level aggregated report"
    SUPPLIER_SALES = "supplier_sales", "Supplier sales report"
    BUYER_ORDERS = "buyer_orders", "Buyer orders report"
    MARKETPLACE_SUMMARY = "marketplace_summary", "Marketplace sales summary"


class ReportFormat(models.TextChoices):
    CSV = "csv", "CSV"
    PDF = "pdf", "PDF"


class ReportStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


def _parse_date(value, field_name):
    from datetime import date

    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError({field_name: "Expected an ISO date (YYYY-MM-DD)."}) from None


class ReportJob(UUIDModel, TimeStampedModel):
    """One requested export; the artifact expires after a TTL."""

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="report_jobs",
    )
    institution = models.ForeignKey(
        "organizations.Institution",
        on_delete=models.PROTECT,
        related_name="report_jobs",
        null=True,
        blank=True,
    )
    report_type = models.CharField(max_length=40, choices=ReportType.choices)
    format = models.CharField(max_length=8, choices=ReportFormat.choices)
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=ReportStatus.choices, default=ReportStatus.PENDING
    )
    error = models.TextField(blank=True)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    artifact = models.FileField(
        upload_to="reports/%Y/%m/", storage=private_storage, blank=True
    )
    artifact_name = models.CharField(max_length=255, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["requester", "-created_at"], name="report_owner_time"),
            models.Index(fields=["institution", "-created_at"], name="report_inst_time"),
        ]

    def __str__(self) -> str:
        return f"{self.report_type} ({self.format}) · {self.status}"

    def clean(self):
        parameters = self.parameters or {}
        date_from = _parse_date(parameters.get("date_from"), "date_from")
        date_to = _parse_date(parameters.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_from": "date_from must not be after date_to."})
        if self.report_type in {
            ReportType.INDIVIDUAL_LOGBOOK,
            ReportType.TRAINEE_PROGRESS,
        } and not parameters.get("target_user"):
            raise ValidationError({"target_user": "This report needs a target_user."})

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_downloadable(self) -> bool:
        return (
            self.status == ReportStatus.SUCCEEDED
            and bool(self.artifact)
            and not self.is_expired
        )
