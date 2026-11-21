from __future__ import annotations

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import Notification, NotificationCategory, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    actor_detail = UserSummarySerializer(source="actor", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "category",
            "title",
            "body",
            "link",
            "actor",
            "actor_detail",
            "object_type",
            "object_pk",
            "institution",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    category = serializers.ChoiceField(choices=NotificationCategory.choices)

    class Meta:
        model = NotificationPreference
        fields = ["category", "in_app"]
        read_only_fields = ["category"]

    def validate(self, attrs):
        # Only advertised channels may be written; unknown keys would otherwise
        # be silently dropped by the nested serializer.
        unknown = set(self.initial_data) - {"category", "in_app"}
        if unknown:
            raise serializers.ValidationError(
                {"fields": f"Unsupported fields: {', '.join(sorted(unknown))}."}
            )
        return attrs


class NotificationPreferenceBulkSerializer(serializers.Serializer):
    preferences = NotificationPreferenceSerializer(many=True, allow_empty=False)
