from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import RoleAssignment, User, UserRole
from apps.core.audit import record_audit
from apps.core.models import AuditEvent
from apps.logbook.services import has_institution_role

from .generators import build_report
from .models import ReportJob, ReportStatus, ReportType
from .rendering import render_document

logger = logging.getLogger("star.api")


# Roles that may request institution-wide activity reports.
REPORT_READER_ROLES = frozenset(
    {UserRole.SUPERVISOR, UserRole.DEPARTMENT_MANAGER, UserRole.INSTITUTION_ADMIN}
)
# Roles that may export a colleague's logbook inside their institution.
LOGBOOK_EXPORTER_ROLES = frozenset(
    {UserRole.DEPARTMENT_MANAGER, UserRole.INSTITUTION_ADMIN}
)


def _is_member(user, institution_id) -> bool:
    return RoleAssignment.objects.filter(
        user=user, institution_id=institution_id, is_active=True
    ).exists()


def can_request_report(user, report_type: str, institution_id, target=None) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if not _is_member(user, institution_id):
        return False
    if report_type == ReportType.INDIVIDUAL_LOGBOOK:
        if target is None or target.pk == user.pk:
            return True
        return has_institution_role(user, institution_id, LOGBOOK_EXPORTER_ROLES)
    return has_institution_role(user, institution_id, REPORT_READER_ROLES)


def resolve_target(user, institution_id, target_user_pk):
    if target_user_pk in (None, "", user.pk):
        return user
    target = (
        User.objects.filter(pk=target_user_pk, is_active=True)
        .filter(role_assignments__institution_id=institution_id, role_assignments__is_active=True)
        .distinct()
        .first()
    )
    if target is None:
        raise exceptions.ValidationError(
            {"target_user": "No active member with that id in this institution."}
        )
    return target


def request_report(
    user,
    *,
    institution,
    report_type: str,
    report_format: str,
    parameters: dict,
    request=None,
) -> ReportJob:
    target = None
    if report_type == ReportType.INDIVIDUAL_LOGBOOK:
        target = resolve_target(user, institution.pk, parameters.get("target_user"))
        parameters = {**parameters, "target_user": str(target.pk)}
    if not can_request_report(user, report_type, institution.pk, target=target):
        raise exceptions.PermissionDenied(
            "You are not allowed to request this report.", code="permission_denied"
        )

    with transaction.atomic():
        job = ReportJob.objects.create(
            requester=user,
            institution=institution,
            report_type=report_type,
            format=report_format,
            parameters=parameters,
            status=ReportStatus.RUNNING,
        )
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.REPORT_REQUESTED,
            object_type="report_job",
            object_pk=job.pk,
            institution=institution,
            metadata={"report_type": report_type, "format": report_format},
        )
    return _generate(job, request=request)


def _generate(job: ReportJob, *, request=None) -> ReportJob:
    try:
        title, headers, rows = build_report(
            job.report_type, job.requester, job.parameters
        )
        limit = settings.REPORT_SYNC_ROW_LIMIT
        if len(rows) > limit:
            raise exceptions.ValidationError(
                {
                    "parameters": (
                        f"This export has {len(rows)} rows which exceeds the "
                        f"synchronous limit of {limit}. Narrow the date range."
                    )
                }
            )
        subtitle = (
            f"{job.institution.name} · requested by {job.requester.email} · "
            f"{timezone.now().date().isoformat()}"
        )
        content, content_type = render_document(
            job.format, title, subtitle, headers, rows
        )
        name = f"{job.report_type}-{job.pk}.{job.format}"
        job.artifact.save(name, ContentFile(content), save=False)
        job.artifact_name = name
        job.row_count = len(rows)
        job.status = ReportStatus.SUCCEEDED
        job.completed_at = timezone.now()
        job.expires_at = job.completed_at + timedelta(
            hours=settings.REPORT_ARTIFACT_TTL_HOURS
        )
        job.error = ""
        job.save()
        return job
    except exceptions.ValidationError as error:
        job.status = ReportStatus.FAILED
        job.error = str(error.detail)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error", "completed_at", "updated_at"])
        record_audit(
            request=request,
            actor=job.requester,
            action=AuditEvent.Action.REPORT_FAILED,
            object_type="report_job",
            object_pk=job.pk,
            institution=job.institution,
            metadata={"report_type": job.report_type, "reason": "validation"},
        )
        raise
    except Exception:
        logger.exception("Report generation failed (job=%s)", job.pk)
        job.status = ReportStatus.FAILED
        job.error = "Report generation failed unexpectedly."
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error", "completed_at", "updated_at"])
        record_audit(
            request=request,
            actor=job.requester,
            action=AuditEvent.Action.REPORT_FAILED,
            object_type="report_job",
            object_pk=job.pk,
            institution=job.institution,
            metadata={"report_type": job.report_type, "reason": "unexpected"},
        )
        raise exceptions.ValidationError(
            {"detail": "Report generation failed. Please try again."}
        ) from None


def visible_report_jobs(user):
    if not user or not user.is_authenticated or not user.is_active:
        return ReportJob.objects.none()
    return ReportJob.objects.filter(requester=user)
