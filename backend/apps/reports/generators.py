from __future__ import annotations

from datetime import date

from django.db.models import Count, Q

from apps.accounts.models import RoleAssignment, User
from apps.logbook.models import (
    ParticipantRole,
    ProcedureParticipant,
    ProcedureStatus,
    SurgicalProcedure,
)
from apps.logbook.services import visible_procedures
from apps.training.models import (
    Assessment,
    AssessmentStatus,
    PlacementStatus,
    TrainingPlacement,
)

from .models import ReportType


def _date_filters(parameters: dict) -> Q:
    filters = Q()
    date_from = parameters.get("date_from")
    date_to = parameters.get("date_to")
    if date_from:
        filters &= Q(procedure_date__gte=date.fromisoformat(str(date_from)))
    if date_to:
        filters &= Q(procedure_date__lte=date.fromisoformat(str(date_to)))
    return filters


def _specialty_name(procedure: SurgicalProcedure) -> str:
    return procedure.specialty.name if procedure.specialty_id else "Unassigned"


def _participation_roles(target: User) -> dict:
    mapping: dict = {}

    def annotate(procedure, role):
        mapping.setdefault(procedure.pk, role)

    owned = SurgicalProcedure.objects.filter(author=target)
    for procedure in owned:
        annotate(procedure, "author")
    participations = ProcedureParticipant.objects.filter(user=target).select_related(
        "procedure", "user"
    )
    for participation in participations:
        mapping.setdefault(participation.procedure_id, participation.role)
    return mapping


def build_individual_logbook(requester: User, parameters: dict, institution):
    target = User.objects.get(pk=parameters["target_user"])
    queryset = (
        visible_procedures(requester)
        .filter(institution=institution)
        .filter(_date_filters(parameters))
        .filter(Q(author=target) | Q(participants__user=target))
        .select_related("specialty", "author")
        .distinct()
        .order_by("procedure_date", "reference")
    )
    roles = _participation_roles(target)
    headers = [
        "Reference",
        "Date",
        "Procedure",
        "Category",
        "Specialty",
        "Status",
        "Participation role",
    ]
    rows = [
        [
            procedure.reference,
            procedure.procedure_date.isoformat(),
            procedure.procedure_name,
            procedure.get_category_display(),
            _specialty_name(procedure),
            procedure.get_status_display(),
            roles.get(procedure.pk, "author"),
        ]
        for procedure in queryset
    ]
    target_label = target.email
    title = f"Surgical logbook — {target_label}"
    return title, headers, rows


def build_activity_by_date(requester: User, parameters: dict, institution):
    queryset = (
        visible_procedures(requester)
        .filter(institution=institution)
        .filter(_date_filters(parameters))
    )
    pivoted: dict = {}
    for row in (
        queryset.values("procedure_date", "status")
        .annotate(count=Count("pk"))
        .order_by("procedure_date")
    ):
        pivoted.setdefault(row["procedure_date"], {"total": 0})
        pivoted[row["procedure_date"]][row["status"]] = row["count"]
        pivoted[row["procedure_date"]]["total"] += row["count"]
    status_columns = list(ProcedureStatus.values)
    headers = ["Date", "Total"] + [
        status.replace("_", " ").title() for status in status_columns
    ]
    rows = [
        [
            day.isoformat(),
            counts["total"],
            *[counts.get(status, 0) for status in status_columns],
        ]
        for day, counts in sorted(pivoted.items())
    ]
    title = "Activity by date range"
    return title, headers, rows


def build_activity_by_specialty(requester: User, parameters: dict, institution):
    queryset = (
        visible_procedures(requester)
        .filter(institution=institution)
        .filter(_date_filters(parameters))
    )
    grouped = (
        queryset.values("institution__name", "specialty__name")
        .annotate(
            total=Count("pk", distinct=True),
            approved=Count(
                "pk", filter=Q(status=ProcedureStatus.APPROVED), distinct=True
            ),
        )
        .order_by("institution__name", "specialty__name")
    )
    headers = ["Institution", "Specialty", "Total procedures", "Approved"]
    rows = [
        [
            row["institution__name"],
            row["specialty__name"] or "Unassigned",
            row["total"],
            row["approved"],
        ]
        for row in grouped
    ]
    title = "Activity by specialty and institution"
    return title, headers, rows


def build_participation_roles(requester: User, parameters: dict, institution):
    queryset = (
        visible_procedures(requester)
        .filter(institution=institution)
        .filter(_date_filters(parameters))
    )
    authored = queryset.filter(author=requester).count()
    participations = (
        ProcedureParticipant.objects.filter(
            procedure__in=queryset, user=requester
        )
        .values("role")
        .annotate(count=Count("procedure_id", distinct=True))
        .order_by("role")
    )
    headers = ["Participation role", "Procedures"]
    rows = [["author", authored]]
    for row in participations:
        label = dict(ParticipantRole.choices).get(row["role"], row["role"])
        rows.append([label, row["count"]])
    title = "Procedures grouped by participation role"
    return title, headers, rows


# ── Training reports (M4b) ─────────────────────────────────────────────
def _assessment_rows(queryset) -> list[list]:
    rows = []
    for assessment in queryset:
        rows.append(
            [
                assessment.placement.trainee.email,
                assessment.competency.code,
                assessment.competency.title,
                assessment.assessor.email,
                assessment.placement.title,
                assessment.get_status_display(),
                assessment.overall_level or "—",
                assessment.submitted_at.date().isoformat()
                if assessment.submitted_at
                else "",
                assessment.decided_at.date().isoformat()
                if assessment.decided_at
                else "",
            ]
        )
    return rows


_ASSESSMENT_HEADERS = [
    "Trainee",
    "Competency code",
    "Competency",
    "Assessor",
    "Placement",
    "Status",
    "Overall level",
    "Submitted",
    "Decided",
]


def build_trainee_progress(requester: User, parameters: dict, institution):
    target = User.objects.get(pk=parameters["target_user"])
    placements = (
        TrainingPlacement.objects.filter(
            trainee=target, institution=institution
        )
        .prefetch_related("assessments", "examiner_assignments")
        .order_by("-start_date")
    )
    headers = [
        "Placement",
        "Status",
        "Start",
        "End",
        "Examiners",
        "Assessments",
        "Approved",
        "Submitted",
        "Needs correction",
    ]
    rows = []
    for placement in placements:
        status_counts = {
            row["status"]: row["count"]
            for row in placement.assessments.values("status").annotate(
                count=Count("pk")
            )
        }
        rows.append(
            [
                placement.title,
                placement.get_status_display(),
                placement.start_date.isoformat(),
                placement.end_date.isoformat() if placement.end_date else "",
                placement.examiner_assignments.count(),
                sum(status_counts.values()),
                status_counts.get(AssessmentStatus.APPROVED, 0),
                status_counts.get(AssessmentStatus.SUBMITTED, 0),
                status_counts.get(AssessmentStatus.NEEDS_CORRECTION, 0),
            ]
        )
    title = f"Trainee progress — {target.email}"
    return title, headers, rows


def build_competency_assessments(
    requester: User, parameters: dict, institution
):
    queryset = Assessment.objects.filter(placement__institution=institution)
    target_pk = parameters.get("target_user")
    if target_pk:
        queryset = queryset.filter(placement__trainee_id=target_pk)
    else:
        queryset = queryset.filter(
            Q(assessor=requester) | Q(placement__trainee=requester)
        )
    queryset = queryset.select_related(
        "placement__trainee", "competency", "assessor"
    ).order_by("-created_at")
    title = "Competency assessments"
    return title, _ASSESSMENT_HEADERS, _assessment_rows(queryset)


def build_examiner_reviews(requester: User, parameters: dict, institution):
    queryset = Assessment.objects.filter(placement__institution=institution)
    target_pk = parameters.get("target_user")
    assessor_id = target_pk or requester.pk
    queryset = (
        queryset.filter(assessor_id=assessor_id)
        .select_related("placement__trainee", "competency", "assessor")
        .order_by("-created_at")
    )
    label = (
        User.objects.filter(pk=assessor_id).values_list("email", flat=True).first()
        or "unknown"
    )
    title = f"Examiner reviews — {label}"
    return title, _ASSESSMENT_HEADERS, _assessment_rows(queryset)


def build_placement_completion(requester: User, parameters: dict, institution):
    queryset = TrainingPlacement.objects.filter(institution=institution)
    target_pk = parameters.get("target_user")
    is_manager = RoleAssignment.objects.filter(
        user=requester,
        institution=institution,
        role__in=["supervisor", "department_manager", "institution_admin"],
        is_active=True,
    ).exists()
    if target_pk:
        queryset = queryset.filter(trainee_id=target_pk)
    elif not is_manager:
        queryset = queryset.filter(Q(trainee=requester) | Q(supervisor=requester))
    queryset = queryset.select_related("trainee", "supervisor").prefetch_related(
        "assessments"
    )
    headers = [
        "Placement",
        "Trainee",
        "Supervisor",
        "Status",
        "Start",
        "End",
        "Examiners",
        "Assessments",
        "Approved",
        "Completion",
    ]
    rows = []
    for placement in queryset.order_by("-start_date"):
        status_counts = {
            row["status"]: row["count"]
            for row in placement.assessments.values("status").annotate(
                count=Count("pk")
            )
        }
        total = sum(status_counts.values())
        approved = status_counts.get(AssessmentStatus.APPROVED, 0)
        completion = "n/a" if total == 0 else f"{round(100 * approved / total)}%"
        rows.append(
            [
                placement.title,
                placement.trainee.email,
                placement.supervisor.email if placement.supervisor else "",
                placement.get_status_display(),
                placement.start_date.isoformat(),
                placement.end_date.isoformat() if placement.end_date else "",
                placement.examiner_assignments.count(),
                total,
                approved,
                completion,
            ]
        )
    title = "Placement completion"
    return title, headers, rows


def build_institution_summary(requester: User, parameters: dict, institution):
    members = RoleAssignment.objects.filter(
        institution=institution, is_active=True
    ).count()
    procedures = {
        row["status"]: row["count"]
        for row in SurgicalProcedure.objects.filter(institution=institution)
        .values("status")
        .annotate(count=Count("pk"))
    }
    placements = {
        row["status"]: row["count"]
        for row in TrainingPlacement.objects.filter(institution=institution)
        .values("status")
        .annotate(count=Count("pk"))
    }
    assessments = {
        row["status"]: row["count"]
        for row in Assessment.objects.filter(placement__institution=institution)
        .values("status")
        .annotate(count=Count("pk"))
    }
    headers = ["Metric", "Value"]
    rows = [["Active members", members]]
    for status in ProcedureStatus.values:
        rows.append(
            [
                f"Procedures {status.replace('_', ' ')}",
                procedures.get(status, 0),
            ]
        )
    for status in PlacementStatus.values:
        rows.append(
            [
                f"Placements {status.replace('_', ' ')}",
                placements.get(status, 0),
            ]
        )
    for status in AssessmentStatus.values:
        rows.append(
            [
                f"Assessments {status.replace('_', ' ')}",
                assessments.get(status, 0),
            ]
        )
    title = f"Institution summary — {institution.name}"
    return title, headers, rows


BUILDERS = {
    ReportType.INDIVIDUAL_LOGBOOK: build_individual_logbook,
    ReportType.ACTIVITY_BY_DATE: build_activity_by_date,
    ReportType.ACTIVITY_BY_SPECIALTY: build_activity_by_specialty,
    ReportType.PARTICIPATION_ROLES: build_participation_roles,
    ReportType.TRAINEE_PROGRESS: build_trainee_progress,
    ReportType.COMPETENCY_ASSESSMENTS: build_competency_assessments,
    ReportType.EXAMINER_REVIEWS: build_examiner_reviews,
    ReportType.PLACEMENT_COMPLETION: build_placement_completion,
    ReportType.INSTITUTION_SUMMARY: build_institution_summary,
}


def build_report(report_type: str, requester: User, parameters: dict, institution):
    builder = BUILDERS[report_type]
    return builder(requester, parameters, institution)

