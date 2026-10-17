from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import INSTITUTION_SCOPED_ROLES, RoleAssignment, UserRole
from apps.core.audit import record_audit
from apps.core.models import AuditEvent
from apps.logbook.models import ParticipantRole, ProcedureStatus, SurgicalProcedure
from apps.logbook.services import has_institution_role, is_marketplace_only

from .models import (
    Assessment,
    AssessmentStatus,
    Competency,
    CompetencyRubricVersion,
    ExaminerAssignment,
    PlacementStatus,
    TrainingPlacement,
)

# Roles that manage placements anywhere inside their institution.
PLACEMENT_MANAGER_ROLES = frozenset(
    {UserRole.SUPERVISOR, UserRole.DEPARTMENT_MANAGER, UserRole.INSTITUTION_ADMIN}
)

# Roles that manage the competency catalog and rubrics.
COMPETENCY_MANAGER_ROLES = frozenset(
    {UserRole.DEPARTMENT_MANAGER, UserRole.INSTITUTION_ADMIN}
)

# Examiner decisions require an explicit assignment (plus oversight roles).
ASSESSMENT_DECIDER_ROLES = frozenset(
    {UserRole.SUPERVISOR, UserRole.DEPARTMENT_MANAGER, UserRole.INSTITUTION_ADMIN}
)


# ── Role helpers ───────────────────────────────────────────────────────
def _active_roles(user) -> list[RoleAssignment]:
    if not user or not user.is_authenticated or not user.is_active:
        return []
    return list(
        RoleAssignment.objects.filter(user=user, is_active=True).select_related(
            "institution"
        )
    )


def viewer_institution_ids(user) -> list:
    """Institutions where the user may browse training data at all."""
    if is_marketplace_only(user):
        return []
    return [
        assignment.institution_id
        for assignment in _active_roles(user)
        if assignment.role in INSTITUTION_SCOPED_ROLES
        and assignment.institution_id is not None
    ]


def manager_institution_ids(user) -> list:
    """Institutions where the user manages training (supervisors + managers)."""
    if is_marketplace_only(user):
        return []
    return [
        assignment.institution_id
        for assignment in _active_roles(user)
        if assignment.role in PLACEMENT_MANAGER_ROLES
        and assignment.institution_id is not None
    ]


def can_manage_placement(user, placement: TrainingPlacement) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user):
        return False
    if placement.trainee_id == user.pk:
        return False
    return has_institution_role(user, placement.institution_id, PLACEMENT_MANAGER_ROLES)


def can_create_placement_in(user, institution) -> bool:
    if institution is None or not institution.is_active:
        return False
    return has_institution_role(user, institution.pk, PLACEMENT_MANAGER_ROLES)


def visible_placements(user):
    """Trainees see their own placements, supervisors/managers their
    institution's, and examiners only the placements they are assigned to."""
    if not user or not user.is_authenticated or not user.is_active:
        return TrainingPlacement.objects.none()
    if is_marketplace_only(user):
        return TrainingPlacement.objects.none()
    scope = Q(institution_id__in=manager_institution_ids(user))
    related = (
        Q(trainee=user)
        | Q(supervisor=user)
        | Q(examiner_assignments__examiner=user)
    )
    return TrainingPlacement.objects.filter(scope | related).distinct()


def is_assigned_examiner(user, placement: TrainingPlacement) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user):
        return False
    return placement.examiner_assignments.filter(examiner=user).exists()


def can_assign_examiner(user, placement: TrainingPlacement) -> bool:
    return can_manage_placement(user, placement)


# ── Placements ─────────────────────────────────────────────────────────
@transaction.atomic
def create_placement(
    user,
    *,
    validated_data: dict,
    expected_competency_ids: list | None = None,
    request=None,
) -> TrainingPlacement:
    institution = validated_data.get("institution")
    if not can_create_placement_in(user, institution):
        raise exceptions.PermissionDenied(
            "You are not allowed to create training placements in this institution.",
            code="permission_denied",
        )
    trainee = validated_data.get("trainee")
    if trainee is not None and not trainee.is_active:
        raise exceptions.ValidationError({"trainee": "This account is inactive."})
    if trainee is not None and is_marketplace_only(trainee):
        raise exceptions.ValidationError(
            {"trainee": "Marketplace accounts cannot hold training placements."}
        )
    if trainee is not None and TrainingPlacement.objects.filter(
        trainee=trainee, status=PlacementStatus.ACTIVE
    ).exists():
        raise exceptions.ValidationError(
            {"trainee": "This trainee already has an active placement."}
        )

    placement = TrainingPlacement(created_by=user, **validated_data)
    try:
        placement.full_clean()
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(_details(exc)) from exc
    expected = _validated_competencies(institution, expected_competency_ids)
    try:
        placement.save()
    except IntegrityError as exc:
        raise exceptions.ValidationError(
            {"trainee": "This trainee already has an active placement."}
        ) from exc
    if expected:
        placement.expected_competencies.set(expected)

    record_audit(
        request=request,
        actor=user,
        action=AuditEvent.Action.PLACEMENT_CREATED,
        object_type="training_placement",
        object_pk=placement.pk,
        institution=placement.institution,
        metadata={
            "title": placement.title,
            "trainee": getattr(trainee, "email", ""),
            "start_date": str(placement.start_date),
        },
    )
    return placement


def _validated_competencies(institution, competency_ids: list | None) -> list[Competency]:
    if not competency_ids:
        return []
    competencies = list(
        Competency.objects.filter(
            pk__in=competency_ids, institution=institution, is_active=True
        )
    )
    if len(competencies) != len(set(competency_ids)):
        raise exceptions.ValidationError(
            {
                "expected_competency_ids": (
                    "Competencies must exist in this institution and be active."
                )
            }
        )
    return competencies


def _details(exc: DjangoValidationError) -> dict:
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"non_field_errors": list(exc.messages)}


@transaction.atomic
def update_placement(
    placement: TrainingPlacement,
    *,
    actor,
    validated_data: dict,
    expected_competency_ids: list | None = None,
    request=None,
) -> TrainingPlacement:
    if not can_manage_placement(actor, placement):
        raise exceptions.PermissionDenied(
            "You are not allowed to manage this training placement.",
            code="permission_denied",
        )
    if not placement.is_active:
        raise exceptions.ValidationError(
            {"status": "Completed or cancelled placements are read-only."}
        )
    changed = [
        field
        for field, value in validated_data.items()
        if getattr(placement, field, None) != value
    ]
    for field, value in validated_data.items():
        setattr(placement, field, value)
    try:
        placement.full_clean()
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(_details(exc)) from exc
    placement.save()

    competency_ids = None
    if expected_competency_ids is not None:
        competency_ids = [str(pk) for pk in expected_competency_ids]
        expected = _validated_competencies(placement.institution, competency_ids)
        placement.expected_competencies.set(expected)
        changed.append("expected_competencies")

    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.PLACEMENT_UPDATED,
        object_type="training_placement",
        object_pk=placement.pk,
        institution=placement.institution,
        metadata={"title": placement.title, "fields": sorted(set(changed))},
    )
    return placement


@transaction.atomic
def complete_placement(
    placement: TrainingPlacement, *, actor, request=None
) -> TrainingPlacement:
    if not can_manage_placement(actor, placement):
        raise exceptions.PermissionDenied(
            "You are not allowed to manage this training placement.",
            code="permission_denied",
        )
    if placement.status != PlacementStatus.ACTIVE:
        raise exceptions.ValidationError(
            {"status": "Only active placements can be completed."}
        )
    placement.status = PlacementStatus.COMPLETED
    placement.completed_at = timezone.now()
    placement.save(update_fields=["status", "completed_at", "updated_at"])
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.PLACEMENT_COMPLETED,
        object_type="training_placement",
        object_pk=placement.pk,
        institution=placement.institution,
        metadata={"title": placement.title},
    )
    return placement


@transaction.atomic
def cancel_placement(
    placement: TrainingPlacement, *, actor, reason: str = "", request=None
) -> TrainingPlacement:
    if not can_manage_placement(actor, placement):
        raise exceptions.PermissionDenied(
            "You are not allowed to manage this training placement.",
            code="permission_denied",
        )
    if placement.status != PlacementStatus.ACTIVE:
        raise exceptions.ValidationError(
            {"status": "Only active placements can be cancelled."}
        )
    placement.status = PlacementStatus.CANCELLED
    placement.closure_reason = reason.strip()
    placement.cancelled_at = timezone.now()
    placement.save(
        update_fields=["status", "closure_reason", "cancelled_at", "updated_at"]
    )
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.PLACEMENT_CANCELLED,
        object_type="training_placement",
        object_pk=placement.pk,
        institution=placement.institution,
        metadata={"title": placement.title, "reason_provided": bool(reason.strip())},
    )
    return placement


# ── Examiner assignments ───────────────────────────────────────────────
@transaction.atomic
def assign_examiner(
    placement: TrainingPlacement, *, actor, examiner, request=None
) -> ExaminerAssignment:
    if not can_assign_examiner(actor, placement):
        raise exceptions.PermissionDenied(
            "Only placement managers can assign examiners.",
            code="permission_denied",
        )
    if not placement.is_active:
        raise exceptions.ValidationError(
            {"status": "Examiners can only be assigned to active placements."}
        )
    if placement.examiner_assignments.filter(examiner=examiner).exists():
        raise exceptions.ValidationError(
            {"examiner": "This examiner is already assigned to the placement."}
        )
    assignment = ExaminerAssignment(
        placement=placement, examiner=examiner, assigned_by=actor
    )
    try:
        assignment.save()
    except IntegrityError as exc:
        raise exceptions.ValidationError(
            {"examiner": "This examiner is already assigned to the placement."}
        ) from exc
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(_details(exc)) from exc
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.EXAMINER_ASSIGNED,
        object_type="examiner_assignment",
        object_pk=assignment.pk,
        institution=placement.institution,
        metadata={"examiner": examiner.email, "title": placement.title},
    )
    return assignment


@transaction.atomic
def revoke_examiner(
    placement: TrainingPlacement, assignment: ExaminerAssignment, *, actor, request=None
) -> None:
    if not can_assign_examiner(actor, placement):
        raise exceptions.PermissionDenied(
            "Only placement managers can revoke examiner assignments.",
            code="permission_denied",
        )
    examiner_email = assignment.examiner.email
    assignment.delete()
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.EXAMINER_REVOKED,
        object_type="examiner_assignment",
        object_pk=str(assignment.pk),
        institution=placement.institution,
        metadata={"examiner": examiner_email, "title": placement.title},
    )


# ── Competency catalog ─────────────────────────────────────────────────
def visible_competencies(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Competency.objects.none()
    if is_marketplace_only(user):
        return Competency.objects.none()
    return Competency.objects.filter(
        institution_id__in=viewer_institution_ids(user)
    )


def can_manage_competency(user, competency: Competency) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user):
        return False
    return has_institution_role(
        user, competency.institution_id, COMPETENCY_MANAGER_ROLES
    )


def ensure_can_create_competency(user, institution) -> None:
    if is_marketplace_only(user) or institution is None:
        raise exceptions.PermissionDenied(
            "You are not allowed to manage the competency catalog.",
            code="permission_denied",
        )
    if not has_institution_role(user, institution.pk, COMPETENCY_MANAGER_ROLES):
        raise exceptions.PermissionDenied(
            "Only department managers and institution administrators can manage "
            "the competency catalog.",
            code="permission_denied",
        )


@transaction.atomic
def create_rubric_version(
    competency: Competency,
    *,
    actor,
    levels: dict | None = None,
    notes: str = "",
    request=None,
) -> CompetencyRubricVersion:
    if not can_manage_competency(actor, competency):
        raise exceptions.PermissionDenied(
            "Only competency managers can create rubric versions.",
            code="permission_denied",
        )
    last = (
        competency.rubric_versions.values_list("version", flat=True).order_by(
            "-version"
        ).first()
        or 0
    )
    rubric = CompetencyRubricVersion(
        competency=competency,
        version=last + 1,
        levels=levels or CompetencyRubricVersion.default_levels(),
        notes=notes,
        created_by=actor,
    )
    try:
        rubric.full_clean()
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(_details(exc)) from exc
    competency.rubric_versions.filter(is_current=True).update(is_current=False)
    rubric.save()
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.RUBRIC_VERSION_CREATED,
        object_type="competency_rubric_version",
        object_pk=rubric.pk,
        institution=competency.institution,
        metadata={"code": competency.code, "version": rubric.version},
    )
    return rubric


def current_rubric_for(competency: Competency) -> CompetencyRubricVersion | None:
    return competency.rubric_versions.filter(is_current=True).first()


# ── Assessments ────────────────────────────────────────────────────────
def visible_assessments(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Assessment.objects.none()
    if is_marketplace_only(user):
        return Assessment.objects.none()
    return Assessment.objects.filter(
        placement__in=visible_placements(user)
    ).distinct()


def can_create_assessment(user, placement: TrainingPlacement) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user) or placement.trainee_id == user.pk:
        return False
    if is_assigned_examiner(user, placement):
        return True
    return has_institution_role(user, placement.institution_id, ASSESSMENT_DECIDER_ROLES)


def can_decide_assessment(user, assessment: Assessment) -> bool:
    """Assessments are decided by someone else than the assessor (no self-approval)."""
    if not user or not user.is_authenticated:
        return False
    if assessment.assessor_id == user.pk:
        return False
    return can_create_assessment(user, assessment.placement)


@transaction.atomic
def create_assessment(
    user,
    *,
    placement: TrainingPlacement,
    competency: Competency,
    rubric_version: CompetencyRubricVersion | None = None,
    validated_data: dict,
    request=None,
) -> Assessment:
    if not can_create_assessment(user, placement):
        raise exceptions.PermissionDenied(
            "You are not allowed to assess trainees in this placement.",
            code="permission_denied",
        )
    rubric = rubric_version or current_rubric_for(competency)
    if rubric is None:
        raise exceptions.ValidationError(
            {"rubric_version": "This competency has no rubric version yet."}
        )
    payload = {
        **validated_data,
        "placement": placement,
        "competency": competency,
        "rubric_version": rubric,
        "assessor": user,
    }
    assessment = Assessment(**payload)
    try:
        assessment.full_clean()
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(_details(exc)) from exc
    assessment.save()
    record_audit(
        request=request,
        actor=user,
        action=AuditEvent.Action.ASSESSMENT_CREATED,
        object_type="competency_assessment",
        object_pk=assessment.pk,
        institution=placement.institution,
        metadata={"code": competency.code, "trainee": placement.trainee.email},
    )
    return assessment


@transaction.atomic
def update_assessment(
    assessment: Assessment,
    *,
    actor,
    validated_data: dict,
    request=None,
) -> Assessment:
    if assessment.assessor_id != actor.pk:
        raise exceptions.PermissionDenied(
            "Only the assessor can edit this assessment.", code="permission_denied"
        )
    if not assessment.is_editable:
        raise exceptions.ValidationError(
            {"status": f"Assessments in status '{assessment.status}' are locked."}
        )
    changed = [
        field
        for field, value in validated_data.items()
        if getattr(assessment, field, None) != value
    ]
    for field, value in validated_data.items():
        setattr(assessment, field, value)
    try:
        assessment.full_clean()
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(_details(exc)) from exc
    assessment.save()
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.ASSESSMENT_UPDATED,
        object_type="competency_assessment",
        object_pk=assessment.pk,
        institution=assessment.placement.institution,
        metadata={"fields": sorted(changed)},
    )
    return assessment


@transaction.atomic
def submit_assessment(
    assessment: Assessment, *, actor, request=None
) -> Assessment:
    if assessment.assessor_id != actor.pk:
        raise exceptions.PermissionDenied(
            "Only the assessor can submit this assessment.", code="permission_denied"
        )
    if assessment.status not in {
        AssessmentStatus.DRAFT,
        AssessmentStatus.NEEDS_CORRECTION,
    }:
        raise exceptions.ValidationError(
            {"status": f"Cannot submit an assessment in status '{assessment.status}'."}
        )
    errors = {}
    if not assessment.scores:
        errors["scores"] = "At least one criterion rating is required."
    if not assessment.overall_level:
        errors["overall_level"] = "An overall level is required."
    if errors:
        raise exceptions.ValidationError(errors)
    assessment.status = AssessmentStatus.SUBMITTED
    assessment.submitted_at = timezone.now()
    assessment.save(update_fields=["status", "submitted_at", "updated_at"])
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.ASSESSMENT_SUBMITTED,
        object_type="competency_assessment",
        object_pk=assessment.pk,
        institution=assessment.placement.institution,
        metadata={"code": assessment.competency.code},
    )
    return assessment


@transaction.atomic
def decide_assessment(
    assessment: Assessment,
    *,
    actor,
    decision: str,
    reason: str = "",
    feedback: str = "",
    request=None,
) -> Assessment:
    if not can_decide_assessment(actor, assessment):
        if assessment.assessor_id == getattr(actor, "pk", None):
            raise exceptions.PermissionDenied(
                "You cannot decide an assessment you created yourself.",
                code="permission_denied",
            )
        raise exceptions.PermissionDenied(
            "You are not an authorized reviewer for this assessment.",
            code="permission_denied",
        )
    if assessment.status != AssessmentStatus.SUBMITTED:
        raise exceptions.ValidationError(
            {"status": f"Cannot decide an assessment in status '{assessment.status}'."}
        )
    if decision == AssessmentStatus.APPROVED:
        target = AssessmentStatus.APPROVED
    elif decision == AssessmentStatus.NEEDS_CORRECTION:
        if not reason.strip():
            raise exceptions.ValidationError(
                {"reason": "A reason is required when corrections are requested."}
            )
        target = AssessmentStatus.NEEDS_CORRECTION
    elif decision == AssessmentStatus.REJECTED:
        if not reason.strip():
            raise exceptions.ValidationError(
                {"reason": "A reason is required when an assessment is rejected."}
            )
        target = AssessmentStatus.REJECTED
    else:
        raise exceptions.ValidationError({"decision": "Unknown decision."})

    assessment.status = target
    assessment.decided_by = actor
    assessment.decided_at = timezone.now()
    assessment.decision_reason = reason.strip() if target != AssessmentStatus.APPROVED else ""
    if feedback:
        assessment.feedback = feedback
    assessment.save()
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.ASSESSMENT_DECIDED,
        object_type="competency_assessment",
        object_pk=assessment.pk,
        institution=assessment.placement.institution,
        metadata={"decision": target, "code": assessment.competency.code},
    )
    return assessment


# ── Progress tracking ──────────────────────────────────────────────────
def placement_progress(placement: TrainingPlacement) -> dict:
    """Counts and competency progress for one placement.

    Procedure counts are quantitative facts from the logbook; competency
    levels are qualitative ratings — the two are reported separately and a
    count never marks a competency as achieved.
    """
    trainee = placement.trainee
    authored = SurgicalProcedure.objects.filter(author=trainee)
    participated = SurgicalProcedure.objects.filter(participants__user=trainee)

    performed = authored.count()
    assisted = participated.filter(
        participants__role=ParticipantRole.ASSISTANT
    ).distinct().count()
    observed = participated.filter(
        participants__role=ParticipantRole.OBSERVER
    ).distinct().count()

    awaiting_review = authored.filter(
        status__in=[ProcedureStatus.SUBMITTED, ProcedureStatus.UNDER_REVIEW]
    ).count()
    approved = authored.filter(status=ProcedureStatus.APPROVED).count()
    returned = authored.filter(status=ProcedureStatus.RETURNED).count()

    expected = list(
        placement.expected_competencies.order_by("order", "code").values(
            "id", "code", "title"
        )
    )
    expected_ids = [row["id"] for row in expected]
    assessments = Assessment.objects.filter(
        placement=placement, competency_id__in=expected_ids
    ).select_related("rubric_version")

    latest: dict = {}
    for assessment in assessments:
        current = latest.get(assessment.competency_id)
        if current is None or assessment.created_at > current.created_at:
            latest[assessment.competency_id] = assessment

    competency_progress = []
    for row in expected:
        assessment = latest.get(row["id"])
        competency_progress.append(
            {
                "competency_id": row["id"],
                "code": row["code"],
                "title": row["title"],
                "assessment_status": assessment.status if assessment else None,
                "overall_level": assessment.overall_level if assessment else None,
                "assessed": assessment is not None,
                "approved": bool(
                    assessment and assessment.status == AssessmentStatus.APPROVED
                ),
            }
        )

    status_counts = {
        row["status"]: row["total"]
        for row in Assessment.objects.filter(placement=placement)
        .values("status")
        .annotate(total=Count("id"))
    }

    return {
        "placement_id": placement.pk,
        "placement_status": placement.status,
        "procedures": {
            "performed": performed,
            "assisted": assisted,
            "observed": observed,
            "awaiting_review": awaiting_review,
            "approved": approved,
            "returned": returned,
        },
        "assessments": {
            "draft": status_counts.get(AssessmentStatus.DRAFT, 0),
            "submitted": status_counts.get(AssessmentStatus.SUBMITTED, 0),
            "approved": status_counts.get(AssessmentStatus.APPROVED, 0),
            "needs_correction": status_counts.get(AssessmentStatus.NEEDS_CORRECTION, 0),
            "rejected": status_counts.get(AssessmentStatus.REJECTED, 0),
        },
        "competency_progress": competency_progress,
    }
