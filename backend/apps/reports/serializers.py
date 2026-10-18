from __future__ import annotations

from datetime import date

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.organizations.models import Institution

from .models import ReportFormat, ReportJob, ReportType


class ReportJobSerializer(serializers.ModelSerializer):
    requester_detail = UserSummarySerializer(source="requester", read_only=True)
    institution_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportJob
        fields = [
            "id",
            "requester",
            "requester_detail",
            "institution",
            "institution_name",
            "report_type",
            "format",
            "parameters",
            "status",
            "error",
            "row_count",
            "artifact_name",
            "completed_at",
            "expires_at",
            "download_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_institution_name(self, obj) -> str | None:
        return obj.institution.name if obj.institution_id else None

    def get_download_url(self, obj) -> str | None:
        if obj.artifact_name:
            return f"/api/v1/reports/{obj.pk}/download/"
        return None


class ReportRequestSerializer(serializers.Serializer):
    institution = serializers.PrimaryKeyRelatedField(
        queryset=Institution.objects.all(), required=False, allow_null=True
    )
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    format = serializers.ChoiceField(choices=ReportFormat.choices)
    parameters = serializers.DictField(required=False, default=dict)

    def validate_parameters(self, value):
        allowed = {"date_from", "date_to", "target_user", "target_supplier"}
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(
                f"Unsupported parameters: {', '.join(sorted(unknown))}."
            )
        dates = {}
        for field in ("date_from", "date_to"):
            raw = value.get(field)
            if raw in (None, ""):
                continue
            try:
                dates[field] = date.fromisoformat(str(raw))
            except ValueError:
                raise serializers.ValidationError(
                    {field: "Expected an ISO date (YYYY-MM-DD)."}
                ) from None
        if len(dates) == 2 and dates["date_from"] > dates["date_to"]:
            raise serializers.ValidationError(
                {"date_from": "date_from must not be after date_to."}
            )
        return value

    def validate(self, attrs):
        from .services import MARKETPLACE_REPORT_TYPES

        if attrs["report_type"] in MARKETPLACE_REPORT_TYPES:
            attrs["institution"] = None
        elif attrs.get("institution") is None:
            raise serializers.ValidationError(
                {"institution": "This report requires an institution."}
            )
        return attrs
