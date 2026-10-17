from __future__ import annotations

import uuid as uuid_lib

from django.db.models import QuerySet
from rest_framework import exceptions, generics, status, views
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from . import services
from .models import (
    Assessment,
    Competency,
    TrainingPlacement,
)
from .serializers import (
    AssessmentDecideSerializer,
    AssessmentSerializer,
    CompetencyRubricVersionSerializer,
    CompetencySerializer,
    ExaminerAssignmentSerializer,
    PlacementActionSerializer,
    RubricCreateSerializer,
    TrainingPlacementSerializer,
)


def _parse_uuid(param: str, field: str):
    try:
        return uuid_lib.UUID(str(param))
    except ValueError:
        raise exceptions.ValidationError({field: "Invalid id."}) from None


def _get_visible_placement(request, pk) -> TrainingPlacement:
    placement = (
        services.visible_placements(request.user)
        .filter(pk=pk)
        .select_related("institution", "department", "trainee", "supervisor")
        .prefetch_related("expected_competencies", "examiner_assignments__examiner")
        .first()
    )
    if placement is None:
        raise exceptions.NotFound()
    return placement


def _get_visible_assessment(request, pk) -> Assessment:
    assessment = (
        services.visible_assessments(request.user)
        .filter(pk=pk)
        .select_related(
            "placement",
            "placement__institution",
            "placement__trainee",
            "competency",
            "rubric_version",
            "assessor",
        )
        .first()
    )
    if assessment is None:
        raise exceptions.NotFound()
    return assessment


# ── Training placements ────────────────────────────────────────────────
class PlacementListCreateView(generics.ListCreateAPIView):
    serializer_class = TrainingPlacementSerializer
    search_fields = ["title", "objectives"]
    ordering_fields = ["start_date", "end_date", "created_at", "status", "title"]
    ordering = ["-start_date", "-created_at"]
    filterset_fields = ["institution", "department", "trainee", "supervisor", "status"]

    def get_queryset(self) -> QuerySet[TrainingPlacement]:
        return services.visible_placements(self.request.user).select_related(
            "institution", "department", "trainee", "supervisor"
        ).prefetch_related("expected_competencies")


class PlacementDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TrainingPlacementSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> TrainingPlacement:
        return _get_visible_placement(self.request, self.kwargs["pk"])


class PlacementExaminersView(views.APIView):
    def get(self, request, pk):
        placement = _get_visible_placement(request, pk)
        serializer = ExaminerAssignmentSerializer(
            placement.examiner_assignments.select_related("examiner"), many=True
        )
        return Response(serializer.data)

    def post(self, request, pk):
        placement = _get_visible_placement(request, pk)
        examiner_id = request.data.get("examiner")
        if not examiner_id:
            raise exceptions.ValidationError({"examiner": "This field is required."})
        _parse_uuid(examiner_id, "examiner")
        examiner = User.objects.filter(pk=examiner_id).first()
        if examiner is None:
            raise exceptions.ValidationError(
                {"examiner": "This user does not exist."}
            )
        assignment = services.assign_examiner(
            placement, actor=request.user, examiner=examiner, request=request
        )
        serializer = ExaminerAssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PlacementExaminerDetailView(views.APIView):
    def delete(self, request, pk, assignment_id):
        placement = _get_visible_placement(request, pk)
        assignment = (
            placement.examiner_assignments.filter(pk=assignment_id)
            .select_related("examiner")
            .first()
        )
        if assignment is None:
            raise exceptions.NotFound()
        services.revoke_examiner(
            placement, assignment, actor=request.user, request=request
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlacementCompleteView(views.APIView):
    def post(self, request, pk):
        placement = _get_visible_placement(request, pk)
        placement = services.complete_placement(
            placement, actor=request.user, request=request
        )
        return Response(TrainingPlacementSerializer(placement).data)


class PlacementCancelView(views.APIView):
    def post(self, request, pk):
        placement = _get_visible_placement(request, pk)
        serializer = PlacementActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        placement = services.cancel_placement(
            placement,
            actor=request.user,
            reason=serializer.validated_data.get("reason", ""),
            request=request,
        )
        return Response(TrainingPlacementSerializer(placement).data)


class PlacementProgressView(views.APIView):
    def get(self, request, pk):
        placement = _get_visible_placement(request, pk)
        return Response(services.placement_progress(placement))


# ── Competency catalog ─────────────────────────────────────────────────
def _get_visible_competency(request, pk) -> Competency:
    competency = (
        services.visible_competencies(request.user)
        .filter(pk=pk)
        .select_related("institution")
        .first()
    )
    if competency is None:
        raise exceptions.NotFound()
    return competency

class CompetencyListCreateView(generics.ListCreateAPIView):
    serializer_class = CompetencySerializer
    search_fields = ["code", "title", "description"]
    ordering_fields = ["order", "code", "title", "created_at"]
    ordering = ["order", "code"]
    filterset_fields = ["institution", "specialty", "is_active"]

    def get_queryset(self) -> QuerySet[Competency]:
        return services.visible_competencies(self.request.user).select_related(
            "institution", "specialty"
        ).prefetch_related("rubric_versions")

    def perform_create(self, serializer):
        institution = serializer.validated_data["institution"]
        services.ensure_can_create_competency(self.request.user, institution)
        instance = serializer.save()
        record_audit(
            request=self.request,
            action=AuditEvent.Action.COMPETENCY_CREATED,
            object_type="competency",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"code": instance.code, "title": instance.title},
        )


class CompetencyDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CompetencySerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> Competency:
        competency = (
            services.visible_competencies(self.request.user)
            .filter(pk=self.kwargs["pk"])
            .select_related("institution", "specialty")
            .prefetch_related("rubric_versions")
            .first()
        )
        if competency is None:
            raise exceptions.NotFound()
        return competency

    def perform_update(self, serializer):
        instance = serializer.instance
        if not services.can_manage_competency(self.request.user, instance):
            raise exceptions.PermissionDenied(
                "Only competency managers can edit the catalog.",
                code="permission_denied",
            )
        instance = serializer.save()
        record_audit(
            request=self.request,
            action=AuditEvent.Action.COMPETENCY_UPDATED,
            object_type="competency",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"code": instance.code},
        )


class CompetencyRubricVersionsView(views.APIView):
    def get(self, request, pk):
        competency = _get_visible_competency(request, pk)
        serializer = CompetencyRubricVersionSerializer(
            competency.rubric_versions.all(), many=True
        )
        return Response(serializer.data)

    def post(self, request, pk):
        competency = _get_visible_competency(request, pk)
        serializer = RubricCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rubric = services.create_rubric_version(
            competency,
            actor=request.user,
            levels=serializer.validated_data.get("levels"),
            notes=serializer.validated_data.get("notes", ""),
            request=request,
        )
        return Response(
            CompetencyRubricVersionSerializer(rubric).data,
            status=status.HTTP_201_CREATED,
        )


class CompetencyRubricVersionDetailView(views.APIView):
    def get(self, request, pk, version_id):
        competency = _get_visible_competency(request, pk)
        rubric = (
            competency.rubric_versions.filter(pk=version_id).first()
        )
        if rubric is None:
            raise exceptions.NotFound()
        return Response(CompetencyRubricVersionSerializer(rubric).data)


# ── Assessments ────────────────────────────────────────────────────────
class AssessmentListCreateView(generics.ListCreateAPIView):
    serializer_class = AssessmentSerializer
    ordering_fields = ["created_at", "status", "submitted_at", "decided_at"]
    ordering = ["-created_at"]
    filterset_fields = [
        "placement",
        "competency",
        "status",
        "assessor",
        "procedure",
        "placement__trainee",
    ]

    def get_queryset(self) -> QuerySet[Assessment]:
        return services.visible_assessments(self.request.user).select_related(
            "placement",
            "placement__institution",
            "placement__trainee",
            "competency",
            "rubric_version",
            "assessor",
        )

class AssessmentDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AssessmentSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> Assessment:
        return _get_visible_assessment(self.request, self.kwargs["pk"])


class AssessmentSubmitView(views.APIView):
    def post(self, request, pk):
        assessment = _get_visible_assessment(request, pk)
        assessment = services.submit_assessment(
            assessment, actor=request.user, request=request
        )
        return Response(AssessmentSerializer(assessment).data)


class AssessmentDecideView(views.APIView):
    def post(self, request, pk):
        assessment = _get_visible_assessment(request, pk)
        serializer = AssessmentDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assessment = services.decide_assessment(
            assessment,
            actor=request.user,
            decision=serializer.validated_data["decision"],
            reason=serializer.validated_data.get("reason", ""),
            feedback=serializer.validated_data.get("feedback", ""),
            request=request,
        )
        return Response(AssessmentSerializer(assessment).data)
