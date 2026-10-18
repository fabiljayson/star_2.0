from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError

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





# ── Marketplace reports (M5b; no institution scope) ────────────────────
def _marketplace_date_filters(parameters: dict) -> Q:
    filters = Q()
    date_from = parameters.get("date_from")
    date_to = parameters.get("date_to")
    if date_from:
        filters &= Q(order__placed_at__gte=date.fromisoformat(str(date_from)))
    if date_to:
        next_day = date.fromisoformat(str(date_to)) + timedelta(days=1)
        filters &= Q(order__placed_at__lt=next_day)
    return filters


def _order_date_filters(parameters: dict) -> Q:
    filters = Q()
    date_from = parameters.get("date_from")
    date_to = parameters.get("date_to")
    if date_from:
        filters &= Q(placed_at__gte=date.fromisoformat(str(date_from)))
    if date_to:
        next_day = date.fromisoformat(str(date_to)) + timedelta(days=1)
        filters &= Q(placed_at__lt=next_day)
    return filters


def _resolve_supplier_profile(requester: User, parameters: dict):
    from apps.marketplace.models import SupplierProfile

    target_supplier = parameters.get("target_supplier")
    if target_supplier:
        if not requester.is_platform_admin:
            raise ValidationError(
                {"target_supplier": "Only platform administrators may target another supplier."}
            )
        profile = SupplierProfile.objects.filter(pk=target_supplier).first()
        if profile is None:
            raise ValidationError(
                {"target_supplier": "No supplier profile with that id."}
            )
        return profile
    profile = SupplierProfile.objects.filter(user=requester).first()
    if profile is None:
        raise ValidationError({"parameters": "This report needs a supplier profile."})
    return profile


def build_supplier_sales(requester: User, parameters: dict, institution):
    from apps.marketplace.models import OrderItem

    profile = _resolve_supplier_profile(requester, parameters)
    queryset = (
        OrderItem.objects.filter(order__supplier=profile)
        .filter(_marketplace_date_filters(parameters))
        .select_related("order", "order__buyer")
        .order_by("-order__placed_at")
    )
    headers = [
        "Order",
        "Placed at",
        "Buyer",
        "SKU",
        "Product",
        "Qty",
        "Unit price (XOF)",
        "Line total (XOF)",
        "Order status",
    ]
    rows = [
        [
            item.order.reference,
            item.order.placed_at.date().isoformat(),
            item.order.buyer.email,
            item.product_sku,
            item.product_name,
            item.quantity,
            str(item.unit_price),
            str(item.line_total),
            item.order.get_status_display(),
        ]
        for item in queryset
    ]
    title = f"Supplier sales — {profile.company_name}"
    return title, headers, rows


def build_buyer_orders(requester: User, parameters: dict, institution):
    from apps.marketplace.models import Order

    queryset = (
        Order.objects.filter(buyer=requester)
        .filter(_order_date_filters(parameters))
        .prefetch_related("items")
        .order_by("-placed_at")
    )
    headers = [
        "Order",
        "Placed at",
        "Supplier",
        "Items",
        "Total (XOF)",
        "Status",
    ]
    rows = [
        [
            order.reference,
            order.placed_at.date().isoformat(),
            order.supplier.company_name,
            sum(item.quantity for item in order.items.all()),
            str(order.total),
            order.get_status_display(),
        ]
        for order in queryset
    ]
    title = f"My orders — {requester.email}"
    return title, headers, rows


def build_marketplace_summary(requester: User, parameters: dict, institution):
    from django.db.models import Sum

    from apps.marketplace.models import Dispute, DisputeStatus, Order, OrderStatus

    if not requester.is_platform_admin:
        raise ValidationError(
            {"detail": "Only platform administrators can request this report."}
        )
    paid_statuses = [
        OrderStatus.PAID,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
    ]
    aggregated = {
        row["supplier_id"]: row
        for row in Order.objects.values("supplier_id", "supplier__company_name")
        .annotate(
            orders=Count("id"),
            paid_orders=Count("id", filter=Q(status__in=paid_statuses)),
            revenue=Sum(
                "total", filter=Q(status__in=paid_statuses)
            ),
            refunds=Count("id", filter=Q(status=OrderStatus.REFUNDED)),
        )
    }
    open_disputes = {
        row["order__supplier_id"]: row["count"]
        for row in Dispute.objects.filter(status=DisputeStatus.OPEN)
        .values("order__supplier_id")
        .annotate(count=Count("id"))
    }
    headers = [
        "Supplier",
        "Orders",
        "Paid orders",
        "Revenue (XOF)",
        "Refunded orders",
        "Open disputes",
    ]
    rows = [
        [
            data["supplier__company_name"],
            data["orders"],
            data["paid_orders"],
            str(data["revenue"] or 0),
            data["refunds"],
            open_disputes.get(supplier_id, 0),
        ]
        for supplier_id, data in sorted(
            aggregated.items(), key=lambda pair: str(pair[1]["supplier__company_name"])
        )
    ]
    title = "Marketplace sales summary"
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
    ReportType.SUPPLIER_SALES: build_supplier_sales,
    ReportType.BUYER_ORDERS: build_buyer_orders,
    ReportType.MARKETPLACE_SUMMARY: build_marketplace_summary,
}


def build_report(report_type: str, requester: User, parameters: dict, institution):
    builder = BUILDERS[report_type]
    return builder(requester, parameters, institution)
