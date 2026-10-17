from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import (
    Attachment,
    ParticipantRole,
    PatientReference,
    ProcedureNoteVersion,
    ProcedureParticipant,
    ProcedureStatus,
    ReviewDecision,
    SurgicalProcedure,
)


def _django_validation_message(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"non_field_errors": list(exc.messages)}


# ── Patient references ─────────────────────────────────────────────────
class PatientReferenceSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    created_by_email = serializers.EmailField(
        source="created_by.email", read_only=True, default=""
    )

    class Meta:
        model = PatientReference
        fields = [
            "id",
            "institution",
            "institution_name",
            "code",
            "label",
            "created_by",
            "created_by_email",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_by", "created_at", "updated_at"]


# ── Participants ───────────────────────────────────────────────────────
class ProcedureParticipantSerializer(serializers.ModelSerializer):
    user_detail = UserSummarySerializer(source="user", read_only=True)
    role = serializers.ChoiceField(choices=ParticipantRole.choices)

    class Meta:
        model = ProcedureParticipant
        fields = ["id", "user", "user_detail", "role", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_user(self, value):
        procedure = self.context.get("procedure")
        if procedure is None:
            return value
        if value.pk == procedure.author_id:
            raise serializers.ValidationError(
                "The record author is tracked separately and is not a participant."
            )
        if not value.is_active:
            raise serializers.ValidationError("This account is inactive.")
        return value


# ── Attachments ────────────────────────────────────────────────────────
class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_detail = UserSummarySerializer(source="uploaded_by", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id",
            "original_name",
            "declared_content_type",
            "detected_kind",
            "size_bytes",
            "sha256",
            "uploaded_by",
            "uploaded_by_detail",
            "download_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_download_url(self, obj) -> str:
        request = self.context.get("request")
        path = f"/api/v1/procedures/{obj.procedure_id}/attachments/{obj.pk}/download/"
        if request:
            return request.build_absolute_uri(path)
        return path


# ── Reviews / versions ─────────────────────────────────────────────────
class ReviewDecisionSerializer(serializers.ModelSerializer):
    reviewer_detail = UserSummarySerializer(source="reviewer", read_only=True)

    class Meta:
        model = ReviewDecision
        fields = [
            "id",
            "decision",
            "reason",
            "from_status",
            "to_status",
            "review_version",
            "reviewer",
            "reviewer_detail",
            "created_at",
        ]
        read_only_fields = fields


class NoteVersionSerializer(serializers.ModelSerializer):
    changed_by_detail = UserSummarySerializer(source="changed_by", read_only=True)

    class Meta:
        model = ProcedureNoteVersion
        fields = [
            "id",
            "version",
            "change_kind",
            "snapshot",
            "changed_by",
            "changed_by_detail",
            "change_summary",
            "created_at",
        ]
        read_only_fields = fields


class ReviewActionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=["start_review", "approve", "request_correction", "reject"]
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, max_length=4000
    )

    def validate(self, attrs):
        decision = attrs.get("decision")
        reason = (attrs.get("reason") or "").strip()
        if decision in {"request_correction", "reject"} and not reason:
            raise serializers.ValidationError(
                {"reason": "A reason is required when a record is not approved."}
            )
        attrs["reason"] = reason
        return attrs


# ── Surgical procedure ─────────────────────────────────────────────────
class SurgicalProcedureSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=ProcedureStatus.choices, read_only=True)
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=None
    )
    specialty_name = serializers.CharField(
        source="specialty.name", read_only=True, default=None
    )
    patient_reference_code = serializers.CharField(
        source="patient_reference.code", read_only=True, default=None
    )
    author_detail = UserSummarySerializer(source="author", read_only=True)
    participants = ProcedureParticipantSerializer(many=True, read_only=True)
    version = serializers.IntegerField(read_only=True)

    class Meta:
        model = SurgicalProcedure
        fields = [
            "id",
            "reference",
            "status",
            "institution",
            "institution_name",
            "department",
            "department_name",
            "specialty",
            "specialty_name",
            "patient_reference",
            "patient_reference_code",
            "procedure_date",
            "category",
            "procedure_name",
            "indication",
            "summary",
            "complications",
            "postoperative",
            "training_objectives",
            "author",
            "author_detail",
            "participants",
            "version",
            "submitted_at",
            "approved_at",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "status",
            "author",
            "author_detail",
            "participants",
            "version",
            "submitted_at",
            "approved_at",
            "archived_at",
            "created_at",
            "updated_at",
            "institution_name",
            "department_name",
            "specialty_name",
            "patient_reference_code",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            # The institution scope of a record never changes after creation.
            self.fields["institution"].read_only = True

    def validate_patient_reference(self, value):
        if value is None:
            return value
        institution = value.institution
        request = self.context.get("request")
        if request and self.instance and self.instance.institution_id != institution.pk:
            raise serializers.ValidationError(
                "Patient reference belongs to a different institution."
            )
        return value

    def validate(self, attrs):
        instance = self.instance
        institution = attrs.get(
            "institution", instance.institution if instance else None
        )
        department = attrs.get(
            "department", instance.department if instance else None
        )
        if department and institution and department.institution_id != institution.pk:
            raise serializers.ValidationError(
                {"department": "Department does not belong to this institution."}
            )
        patient_reference = attrs.get(
            "patient_reference",
            instance.patient_reference if instance else None,
        )
        if patient_reference and institution:
            if patient_reference.institution_id != institution.pk:
                raise serializers.ValidationError(
                    {
                        "patient_reference": (
                            "Patient reference belongs to a different institution."
                        )
                    }
                )
        if instance is None and institution is not None:
            if not institution.is_active:
                raise serializers.ValidationError(
                    {"institution": "This institution is inactive."}
                )
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc
