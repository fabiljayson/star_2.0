from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(read_only=True)
    institution_name = serializers.CharField(source="institution.name", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "action",
            "actor",
            "actor_email",
            "object_type",
            "object_pk",
            "institution",
            "institution_name",
            "ip_address",
            "user_agent",
            "request_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
