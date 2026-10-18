from __future__ import annotations

from datetime import date

from django.db.models import Count, Q

from apps.accounts.models import User
from apps.logbook.models import (
    ParticipantRole,
    ProcedureParticipant,
    ProcedureStatus,
    SurgicalProcedure,
)
from apps.logbook.services import visible_procedures

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


def build_individual_logbook(requester: User, parameters: dict):
    target = User.objects.get(pk=parameters["target_user"])
    queryset = (
        visible_procedures(requester)
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


def build_activity_by_date(requester: User, parameters: dict):
    queryset = visible_procedures(requester).filter(_date_filters(parameters))
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


def build_activity_by_specialty(requester: User, parameters: dict):
    queryset = visible_procedures(requester).filter(_date_filters(parameters))
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


def build_participation_roles(requester: User, parameters: dict):
    queryset = visible_procedures(requester).filter(_date_filters(parameters))
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


BUILDERS = {
    ReportType.INDIVIDUAL_LOGBOOK: build_individual_logbook,
    ReportType.ACTIVITY_BY_DATE: build_activity_by_date,
    ReportType.ACTIVITY_BY_SPECIALTY: build_activity_by_specialty,
    ReportType.PARTICIPATION_ROLES: build_participation_roles,
}


def build_report(report_type: str, requester: User, parameters: dict):
    builder = BUILDERS[report_type]
    return builder(requester, parameters)
