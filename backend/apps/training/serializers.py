from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from . import services
from .models import (
    Assessment,
    AssessmentStatus,
    Competency,
    CompetencyRubricVersion,
    ExaminerAssignment,
    PlacementStatus,
    TrainingPlacement,
)


def _django_validation_message(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"non_field_errors": list(exc.messages)}


# ── Placements ─────────────────────────────────────────────────────────
class ExpectedCompetencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Competency
        fields = ["id", "code", "title"]
        read_only_fields = fields


class TrainingPlacementSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=None
    )
    trainee_detail = UserSummarySerializer(source="trainee", read_only=True)
    supervisor_detail = UserSummarySerializer(source="supervisor", read_only=True)
    expected_competency_ids = serializers.PrimaryKeyRelatedField(
        source="expected_competencies",
        many=True,
        queryset=Competency.objects.filter(is_active=True),
        required=False,
        allow_empty=True,
    )
    expected_competencies = ExpectedCompetencySerializer(many=True, read_only=True)
    status = serializers.ChoiceField(choices=PlacementStatus.choices, read_only=True)

    class Meta:
        model = TrainingPlacement
        fields = [
            "id",
            "title",
            "institution",
            "institution_name",
            "department",
            "department_name",
            "trainee",
            "trainee_detail",
            "supervisor",
            "supervisor_detail",
            "start_date",
            "end_date",
            "status",
            "objectives",
            "closure_reason",
            "expected_competency_ids",
            "expected_competencies",
            "created_by",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "institution_name",
            "department_name",
            "trainee_detail",
            "supervisor_detail",
            "expected_competencies",
            "closure_reason",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            # Scope, trainee and status never change through plain updates.
            self.fields["institution"].read_only = True
            self.fields["trainee"].read_only = True

    def validate(self, attrs):
        instance = self.instance
        department = attrs.get(
            "department", instance.department if instance else None
        )
        institution = attrs.get(
            "institution", instance.institution if instance else None
        )
        if department and institution and department.institution_id != institution.pk:
            raise serializers.ValidationError(
                {"department": "Department does not belong to this institution."}
            )
        if instance is None and institution is not None and not institution.is_active:
            raise serializers.ValidationError(
                {"institution": "This institution is inactive."}
            )
        return attrs

    def create(self, validated_data):
        expected_ids = validated_data.pop("expected_competencies", None)
        expected_list = [c.pk for c in expected_ids] if expected_ids else None
        try:
            return services.create_placement(
                self.context["request"].user,
                validated_data=validated_data,
                expected_competency_ids=expected_list,
                request=self.context.get("request"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc

    def update(self, instance, validated_data):
        expected_ids = validated_data.pop("expected_competencies", None)
        expected_list = (
            [c.pk for c in expected_ids] if expected_ids is not None else None
        )
        return services.update_placement(
            instance,
            actor=self.context["request"].user,
            validated_data=validated_data,
            expected_competency_ids=expected_list,
            request=self.context.get("request"),
        )


class ExaminerAssignmentSerializer(serializers.ModelSerializer):
    examiner_detail = UserSummarySerializer(source="examiner", read_only=True)

    class Meta:
        model = ExaminerAssignment
        fields = ["id", "placement", "examiner", "examiner_detail", "assigned_by", "created_at"]
        read_only_fields = fields


class PlacementActionSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, max_length=4000
    )


# ── Competency catalog ─────────────────────────────────────────────────
class CompetencySerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    specialty_name = serializers.CharField(
        source="specialty.name", read_only=True, default=None
    )
    current_rubric = serializers.SerializerMethodField()

    class Meta:
        model = Competency
        fields = [
            "id",
            "institution",
            "institution_name",
            "code",
            "title",
            "description",
            "specialty",
            "specialty_name",
            "order",
            "is_active",
            "current_rubric",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "institution_name",
            "specialty_name",
            "current_rubric",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["institution"].read_only = True

    def get_current_rubric(self, obj):
        rubric = services.current_rubric_for(obj)
        if rubric is None:
            return None
        return CompetencyRubricVersionSerializer(rubric).data

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc


class RubricLevelSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=64)
    label = serializers.CharField(max_length=120)
    rank = serializers.IntegerField(min_value=1, required=False)


class RubricCriterionSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=64)
    label = serializers.CharField(max_length=120)


class RubricContentSerializer(serializers.Serializer):
    scale = RubricLevelSerializer(many=True, required=False)
    criteria = RubricCriterionSerializer(many=True, required=False)


class CompetencyRubricVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetencyRubricVersion
        fields = [
            "id",
            "competency",
            "version",
            "levels",
            "notes",
            "is_current",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class RubricCreateSerializer(serializers.Serializer):
    levels = RubricContentSerializer(required=False)
    notes = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, max_length=4000
    )

    def validate_levels(self, value):
        if not value:
            return value
        scale = value.get("scale") or []
        criteria = value.get("criteria") or []
        if not scale:
            raise serializers.ValidationError("A rating scale is required.")
        keys = [level["key"] for level in scale]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("Scale keys must be unique.")
        criterion_keys = [c["key"] for c in criteria]
        if len(criterion_keys) != len(set(criterion_keys)):
            raise serializers.ValidationError("Criterion keys must be unique.")
        return value


# ── Assessments ────────────────────────────────────────────────────────
class AssessmentSerializer(serializers.ModelSerializer):
    assessor_detail = UserSummarySerializer(source="assessor", read_only=True)
    decided_by_detail = UserSummarySerializer(source="decided_by", read_only=True)
    competency_code = serializers.CharField(
        source="competency.code", read_only=True
    )
    rubric_version_number = serializers.IntegerField(
        source="rubric_version.version", read_only=True
    )
    trainee_detail = UserSummarySerializer(
        source="placement.trainee", read_only=True
    )
    status = serializers.ChoiceField(choices=AssessmentStatus.choices, read_only=True)

    class Meta:
        model = Assessment
        fields = [
            "id",
            "placement",
            "trainee_detail",
            "competency",
            "competency_code",
            "rubric_version",
            "rubric_version_number",
            "procedure",
            "assessor",
            "assessor_detail",
            "status",
            "scores",
            "overall_level",
            "feedback",
            "decision_reason",
            "decided_by",
            "decided_by_detail",
            "submitted_at",
            "decided_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "rubric_version",
            "assessor",
            "assessor_detail",
            "decided_by",
            "decided_by_detail",
            "decision_reason",
            "submitted_at",
            "decided_at",
            "created_at",
            "updated_at",
            "trainee_detail",
            "competency_code",
            "rubric_version_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            # Placement/competency/rubric are frozen once created.
            for field in ("placement", "competency", "rubric_version"):
                self.fields[field].read_only = True

    def validate_competency(self, value):
        placement = self.initial_data.get("placement")
        if placement is None:
            return value
        from apps.training.models import TrainingPlacement

        try:
            placement_obj = TrainingPlacement.objects.get(pk=placement)
        except (TrainingPlacement.DoesNotExist, ValueError, TypeError):
            return value
        if value.institution_id != placement_obj.institution_id:
            raise serializers.ValidationError(
                "Competency belongs to a different institution."
            )
        return value

    def create(self, validated_data):
        placement = validated_data.pop("placement")
        competency = validated_data.pop("competency")
        rubric_version = validated_data.pop("rubric_version", None)
        try:
            return services.create_assessment(
                self.context["request"].user,
                placement=placement,
                competency=competency,
                rubric_version=rubric_version,
                validated_data=validated_data,
                request=self.context.get("request"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc

    def update(self, instance, validated_data):
        return services.update_assessment(
            instance,
            actor=self.context["request"].user,
            validated_data=validated_data,
            request=self.context.get("request"),
        )


class AssessmentDecideSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=[
            AssessmentStatus.APPROVED,
            AssessmentStatus.NEEDS_CORRECTION,
            AssessmentStatus.REJECTED,
        ]
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, max_length=4000
    )
    feedback = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, max_length=8000
    )

    def validate(self, attrs):
        decision = attrs.get("decision")
        reason = (attrs.get("reason") or "").strip()
        if decision in {AssessmentStatus.NEEDS_CORRECTION, AssessmentStatus.REJECTED} and not reason:
            raise serializers.ValidationError(
                {"reason": "A reason is required for this decision."}
            )
        attrs["reason"] = reason
        return attrs
