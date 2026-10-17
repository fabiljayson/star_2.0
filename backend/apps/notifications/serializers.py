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
        fields = ["category", "in_app", "email"]
        read_only_fields = ["category"]


class NotificationPreferenceBulkSerializer(serializers.Serializer):
    preferences = NotificationPreferenceSerializer(many=True, allow_empty=False)
