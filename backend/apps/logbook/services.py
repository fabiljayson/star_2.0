from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import RoleAssignment, UserRole
from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from .models import (
    NOTE_SNAPSHOT_FIELDS,
    PatientReference,
    ProcedureNoteVersion,
    ProcedureStatus,
    ReviewDecision,
    ReviewDecisionType,
    SurgicalProcedure,
    VersionChangeKind,
)

# Roles that see every clinical record of their own institution.
INSTITUTION_WIDE_CLINICAL_ROLES = frozenset(
    {
        UserRole.SUPERVISOR,
        UserRole.EXAMINER,
        UserRole.DEPARTMENT_MANAGER,
        UserRole.INSTITUTION_ADMIN,
    }
)

# Roles allowed to create surgical records inside an institution.
CLINICAL_CREATOR_ROLES = frozenset(
    {
        UserRole.TRAINEE,
        UserRole.SUPERVISOR,
        UserRole.EXAMINER,
        UserRole.DEPARTMENT_MANAGER,
        UserRole.INSTITUTION_ADMIN,
    }
)

# Roles allowed to review (never their own records).
REVIEWER_ROLES = frozenset(
    {UserRole.SUPERVISOR, UserRole.EXAMINER, UserRole.INSTITUTION_ADMIN}
)

# Marketplace roles must never touch clinical data at all.
MARKETPLACE_ONLY_ROLES = frozenset({UserRole.SUPPLIER, UserRole.BUYER})


# ── Role helpers ───────────────────────────────────────────────────────
def _active_roles(user) -> list[RoleAssignment]:
    if not user or not user.is_authenticated or not user.is_active:
        return []
    return list(
        RoleAssignment.objects.filter(user=user, is_active=True).select_related(
            "institution"
        )
    )


def is_marketplace_only(user) -> bool:
    """True when the user only holds supplier/buyer access (no clinical rights)."""
    roles = {assignment.role for assignment in _active_roles(user)}
    return bool(roles) and roles <= MARKETPLACE_ONLY_ROLES


def clinical_institution_ids(user) -> list:
    """Institutions whose full clinical record set this user may read."""
    if is_marketplace_only(user):
        return []
    return [
        assignment.institution_id
        for assignment in _active_roles(user)
        if assignment.role in INSTITUTION_WIDE_CLINICAL_ROLES
        and assignment.institution_id is not None
    ]


def creator_institution_ids(user) -> list:
    if is_marketplace_only(user):
        return []
    return [
        assignment.institution_id
        for assignment in _active_roles(user)
        if assignment.role in CLINICAL_CREATOR_ROLES
        and assignment.institution_id is not None
    ]


def can_create_procedure_in(user, institution) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user):
        return False
    if institution is None or not institution.is_active:
        return False
    from apps.core.permissions import has_role

    if has_role(user, UserRole.INDEPENDENT_SURGEON):
        return True
    return institution.pk in creator_institution_ids(user)


def can_view_procedure(user, procedure: SurgicalProcedure) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user):
        return False
    if procedure.author_id == user.pk:
        return True
    if procedure.participants.filter(user=user).exists():
        return True
    return procedure.institution_id in clinical_institution_ids(user)


def can_edit_procedure(user, procedure: SurgicalProcedure) -> bool:
    """Only the author may edit, and only in an editable status."""
    if not user or not user.is_authenticated:
        return False
    if not procedure.is_editable:
        return False
    if procedure.author_id != user.pk:
        return False
    if is_marketplace_only(user):
        return False
    return True


def can_submit_procedure(user, procedure: SurgicalProcedure) -> bool:
    if not user or not user.is_authenticated:
        return False
    if procedure.author_id != user.pk:
        return False
    return procedure.status in {ProcedureStatus.DRAFT, ProcedureStatus.RETURNED}


def can_review_procedure(user, procedure: SurgicalProcedure) -> bool:
    """Supervisor/examiner/admin of the institution, never the author."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_marketplace_only(user):
        return False
    if procedure.author_id == user.pk:
        return False
    roles = {
        assignment.role
        for assignment in _active_roles(user)
        if assignment.institution_id == procedure.institution_id
    }
    return bool(roles & REVIEWER_ROLES)


def can_archive_procedure(user, procedure: SurgicalProcedure) -> bool:
    if procedure.status != ProcedureStatus.APPROVED:
        return False
    return has_institution_role(user, procedure.institution_id, REVIEWER_ROLES)


def has_institution_role(user, institution_id, roles) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return RoleAssignment.objects.filter(
        user=user, institution_id=institution_id, role__in=roles, is_active=True
    ).exists()


def visible_procedures(user) -> Q:
    """Row-level visibility filter; never rely on URL secrecy alone."""
    if not user or not user.is_authenticated or not user.is_active:
        return SurgicalProcedure.objects.none()
    if is_marketplace_only(user):
        return SurgicalProcedure.objects.none()
    scope = Q(institution_id__in=clinical_institution_ids(user))
    owned = Q(author=user) | Q(participants__user=user)
    return SurgicalProcedure.objects.filter(scope | owned).distinct()


def visible_patient_references(user):
    qs = PatientReference.objects.all()
    if not user or not user.is_authenticated or not user.is_active:
        return qs.none()
    if is_marketplace_only(user):
        return qs.none()
    institution_ids = set(clinical_institution_ids(user)) | set(
        creator_institution_ids(user)
    )
    if user.has_role(UserRole.INDEPENDENT_SURGEON):
        return qs.filter(institution_id__in=institution_ids) | qs.filter(created_by=user)
    return qs.filter(institution_id__in=institution_ids)


def ensure_can_create(user, institution) -> None:
    if not can_create_procedure_in(user, institution):
        raise exceptions.PermissionDenied(
            "You are not allowed to create surgical records in this institution.",
            code="permission_denied",
        )


# ── Lifecycle transitions ──────────────────────────────────────────────
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ProcedureStatus.DRAFT: frozenset({ProcedureStatus.SUBMITTED}),
    ProcedureStatus.SUBMITTED: frozenset(
        {ProcedureStatus.UNDER_REVIEW, ProcedureStatus.APPROVED, ProcedureStatus.RETURNED}
    ),
    ProcedureStatus.UNDER_REVIEW: frozenset(
        {ProcedureStatus.APPROVED, ProcedureStatus.RETURNED}
    ),
    ProcedureStatus.RETURNED: frozenset({ProcedureStatus.SUBMITTED}),
    ProcedureStatus.APPROVED: frozenset(
        {ProcedureStatus.SUBMITTED, ProcedureStatus.ARCHIVED}
    ),
    ProcedureStatus.ARCHIVED: frozenset(),
}


def _snapshot(procedure: SurgicalProcedure) -> dict:
    return {field: getattr(procedure, field) for field in NOTE_SNAPSHOT_FIELDS}


def _create_version(
    procedure: SurgicalProcedure,
    *,
    change_kind: str,
    changed_by,
    change_summary: str = "",
) -> ProcedureNoteVersion:
    last = (
        procedure.note_versions.order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    )
    return ProcedureNoteVersion.objects.create(
        procedure=procedure,
        version=last + 1,
        change_kind=change_kind,
        snapshot=_snapshot(procedure),
        changed_by=changed_by,
        change_summary=change_summary,
    )


@transaction.atomic
def submit_procedure(procedure: SurgicalProcedure, *, actor, request=None) -> None:
    if not actor or not actor.is_authenticated or procedure.author_id != actor.pk:
        raise exceptions.PermissionDenied(
            "Only the record author can submit this record.", code="permission_denied"
        )
    target = ProcedureStatus.SUBMITTED
    if procedure.status not in {ProcedureStatus.DRAFT, ProcedureStatus.RETURNED}:
        raise exceptions.ValidationError(
            {"status": f"Cannot submit a record in status '{procedure.status}'."}
        )
    _create_version(
        procedure,
        change_kind=VersionChangeKind.SUBMITTED,
        changed_by=actor,
        change_summary="Snapshot at submission",
    )
    procedure.status = target
    procedure.submitted_at = timezone.now()
    procedure.save(update_fields=["status", "submitted_at", "updated_at"])
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.PROCEDURE_SUBMITTED,
        object_type="surgical_procedure",
        object_pk=procedure.pk,
        institution=procedure.institution,
        metadata={"reference": procedure.reference, "version": procedure.version},
    )


@transaction.atomic
def review_procedure(
    procedure: SurgicalProcedure,
    *,
    actor,
    decision: str,
    reason: str = "",
    request=None,
) -> ReviewDecision:
    if not can_review_procedure(actor, procedure):
        raise exceptions.PermissionDenied(
            "You are not an authorized reviewer for this record.",
            code="permission_denied",
        )

    if decision == "start_review":
        if procedure.status != ProcedureStatus.SUBMITTED:
            raise exceptions.ValidationError(
                {"status": "Only submitted records can be put under review."}
            )
        target = ProcedureStatus.UNDER_REVIEW
    elif decision == ReviewDecisionType.APPROVE:
        if procedure.status not in {
            ProcedureStatus.SUBMITTED,
            ProcedureStatus.UNDER_REVIEW,
        }:
            raise exceptions.ValidationError(
                {"status": f"Cannot approve a record in status '{procedure.status}'."}
            )
        target = ProcedureStatus.APPROVED
    elif decision in {
        ReviewDecisionType.REQUEST_CORRECTION,
        ReviewDecisionType.REJECT,
    }:
        if not reason.strip():
            raise exceptions.ValidationError(
                {"reason": "A reason is required when a record is not approved."}
            )
        if procedure.status not in {
            ProcedureStatus.SUBMITTED,
            ProcedureStatus.UNDER_REVIEW,
        }:
            raise exceptions.ValidationError(
                {"status": f"Cannot return a record in status '{procedure.status}'."}
            )
        target = ProcedureStatus.RETURNED
    else:
        raise exceptions.ValidationError({"decision": "Unknown review decision."})

    review_decision = ReviewDecision.objects.create(
        procedure=procedure,
        reviewer=actor,
        decision=decision,
        from_status=procedure.status,
        to_status=target,
        reason=reason.strip(),
        review_version=procedure.version,
    )

    audit_action = {
        "start_review": AuditEvent.Action.PROCEDURE_REVIEW_STARTED,
        ReviewDecisionType.APPROVE: AuditEvent.Action.PROCEDURE_APPROVED,
    }.get(decision, AuditEvent.Action.PROCEDURE_RETURNED)

    procedure.status = target
    if target == ProcedureStatus.APPROVED:
        procedure.approved_at = timezone.now()
        procedure.save(update_fields=["status", "approved_at", "updated_at"])
    else:
        procedure.save(update_fields=["status", "updated_at"])

    record_audit(
        request=request,
        actor=actor,
        action=audit_action,
        object_type="surgical_procedure",
        object_pk=procedure.pk,
        institution=procedure.institution,
        metadata={
            "reference": procedure.reference,
            "decision": decision,
            "from_status": review_decision.from_status,
            "to_status": target,
            "version": procedure.version,
        },
    )
    return review_decision


@transaction.atomic
def apply_content_edit(
    procedure: SurgicalProcedure,
    *,
    actor,
    validated_data: dict,
    request=None,
) -> SurgicalProcedure:
    """Apply an author edit, snapshotting history and forcing re-review of
    approved records instead of silently overwriting them."""
    is_author = bool(
        actor and actor.is_authenticated and procedure.author_id == actor.pk
    )
    if not can_edit_procedure(actor, procedure):
        if is_author and not procedure.is_editable:
            raise exceptions.ValidationError(
                {"status": f"Records in status '{procedure.status}' cannot be edited."}
            )
        raise exceptions.PermissionDenied(
            "Only the record author can edit this record.", code="permission_denied"
        )

    was_approved = procedure.status == ProcedureStatus.APPROVED
    changed = [
        field
        for field, value in validated_data.items()
        if getattr(procedure, field, None) != value
    ]

    if was_approved and changed:
        # Traceable correction: keep what was approved, then force re-review.
        _create_version(
            procedure,
            change_kind=VersionChangeKind.CORRECTION,
            changed_by=actor,
            change_summary="Content modified after approval",
        )
        procedure.version += 1
        procedure.status = ProcedureStatus.SUBMITTED
        procedure.submitted_at = timezone.now()
        procedure.approved_at = None
        procedure.save(update_fields=["version", "status", "submitted_at", "approved_at", "updated_at"])

    for field, value in validated_data.items():
        setattr(procedure, field, value)
    try:
        procedure.full_clean()
    except DjangoValidationError as exc:
        raise exceptions.ValidationError(
            getattr(exc, "message_dict", {"non_field_errors": list(exc.messages)})
        ) from exc
    procedure.save()

    record_audit(
        request=request,
        actor=actor,
        action=(
            AuditEvent.Action.PROCEDURE_CORRECTED
            if was_approved
            else AuditEvent.Action.PROCEDURE_UPDATED
        ),
        object_type="surgical_procedure",
        object_pk=procedure.pk,
        institution=procedure.institution,
        metadata={
            "reference": procedure.reference,
            "fields": sorted(changed),
            "version": procedure.version,
        },
    )
    return procedure


@transaction.atomic
def archive_procedure(procedure: SurgicalProcedure, *, actor, request=None) -> None:
    if not can_archive_procedure(actor, procedure):
        raise exceptions.PermissionDenied(
            "Only institution reviewers can archive approved records.",
            code="permission_denied",
        )
    if procedure.status != ProcedureStatus.APPROVED:
        raise exceptions.ValidationError(
            {"status": "Only approved records can be archived."}
        )
    procedure.status = ProcedureStatus.ARCHIVED
    procedure.archived_at = timezone.now()
    procedure.save(update_fields=["status", "archived_at", "updated_at"])
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.PROCEDURE_ARCHIVED,
        object_type="surgical_procedure",
        object_pk=procedure.pk,
        institution=procedure.institution,
        metadata={"reference": procedure.reference},
    )
