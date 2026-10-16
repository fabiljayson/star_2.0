from django.utils.dateparse import parse_datetime
from rest_framework import exceptions, generics
from rest_framework.permissions import BasePermission

from apps.accounts.models import RoleAssignment, UserRole

from .models import AuditEvent
from .permissions import IsPlatformAdmin, administered_institution_ids
from .serializers import AuditEventSerializer


class InstitutionAdminAuditAccess(BasePermission):
    """Institution administrators (active role) may read their institution's audit."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or user.is_platform_admin:
            return False
        return RoleAssignment.objects.filter(
            user=user, role=UserRole.INSTITUTION_ADMIN, is_active=True
        ).exists()


class AuditEventListView(generics.ListAPIView):
    """Audit viewer: platform administrators see everything (metadata only);
    institution administrators see events scoped to their institutions."""

    serializer_class = AuditEventSerializer
    permission_classes = [IsPlatformAdmin | InstitutionAdminAuditAccess]
    filterset_fields = ["action", "institution", "actor", "object_type"]
    ordering_fields = ["created_at", "action"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_platform_admin:
            qs = AuditEvent.objects.all()
        else:
            allowed = administered_institution_ids(user)
            if not allowed:
                raise exceptions.PermissionDenied(
                    "Audit access requires an institutional administrator role."
                )
            qs = AuditEvent.objects.filter(institution_id__in=allowed)
        params = self.request.query_params
        after = params.get("created_after")
        before = params.get("created_before")
        if after:
            dt = parse_datetime(after)
            if dt is None:
                raise exceptions.ValidationError({"created_after": "Invalid datetime."})
            qs = qs.filter(created_at__gte=dt)
        if before:
            dt = parse_datetime(before)
            if dt is None:
                raise exceptions.ValidationError({"created_before": "Invalid datetime."})
            qs = qs.filter(created_at__lte=dt)
        return qs
