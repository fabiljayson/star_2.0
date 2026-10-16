from __future__ import annotations

import uuid as uuid_lib

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import exceptions, generics, permissions, status, throttling, views
from rest_framework.response import Response

from apps.accounts.models import (
    PLATFORM_SCOPED_ROLES,
    RoleAssignment,
    User,
)
from apps.accounts.serializers import MeSerializer
from apps.core.audit import record_audit
from apps.core.models import AuditEvent
from apps.core.permissions import (
    administered_institution_ids,
    is_institution_admin,
    is_platform_admin,
    require_institution_admin,
    require_platform_admin,
)

from .models import Department, Institution, Invitation, Specialty
from .serializers import (
    DepartmentSerializer,
    InstitutionSerializer,
    InvitationAcceptSerializer,
    InvitationSerializer,
    MembershipSerializer,
    SpecialtySerializer,
)


def _parse_uuid(param: str, field: str):
    try:
        return uuid_lib.UUID(param)
    except ValueError:
        raise exceptions.ValidationError({field: "Invalid id."}) from None


# ── Institutions ───────────────────────────────────────────────────────
class InstitutionListCreateView(generics.ListCreateAPIView):
    serializer_class = InstitutionSerializer
    search_fields = ["name", "city", "country"]
    ordering_fields = ["name", "created_at", "institution_type"]
    ordering = ["name"]
    filterset_fields = ["institution_type", "country", "is_active"]

    def get_queryset(self) -> QuerySet[Institution]:
        qs = Institution.objects.all()
        if not is_platform_admin(self.request.user):
            qs = qs.filter(is_active=True)
        return qs

    def create(self, request, *args, **kwargs):
        require_platform_admin(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        record_audit(
            request=request,
            action=AuditEvent.Action.INSTITUTION_CREATED,
            object_type="institution",
            object_pk=instance.pk,
            institution=instance,
            metadata={"name": instance.name},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class InstitutionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = InstitutionSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Institution]:
        return Institution.objects.all()

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        if not is_platform_admin(user) and not is_institution_admin(user, obj):
            if not obj.is_active:
                raise exceptions.NotFound()
        return obj

    def perform_update(self, serializer):
        user = self.request.user
        institution = serializer.instance
        if not is_platform_admin(user):
            require_institution_admin(user, institution)
        instance = serializer.save()
        record_audit(
            request=self.request,
            action=AuditEvent.Action.INSTITUTION_UPDATED,
            object_type="institution",
            object_pk=instance.pk,
            institution=instance,
            metadata={"fields": sorted(serializer.validated_data.keys())},
        )


# ── Departments ────────────────────────────────────────────────────────
class DepartmentListCreateView(generics.ListCreateAPIView):
    serializer_class = DepartmentSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    filterset_fields = ["institution", "is_active"]

    def get_queryset(self) -> QuerySet[Department]:
        qs = Department.objects.select_related("institution")
        if not is_platform_admin(self.request.user):
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        institution = serializer.validated_data["institution"]
        user = self.request.user
        if is_platform_admin(user):
            require_platform_admin(user)
        else:
            require_institution_admin(user, institution)
        instance = serializer.save()
        record_audit(
            request=self.request,
            action=AuditEvent.Action.DEPARTMENT_CREATED,
            object_type="department",
            object_pk=instance.pk,
            institution=institution,
            metadata={"name": instance.name},
        )


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DepartmentSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[Department]:
        qs = Department.objects.select_related("institution")
        if not is_platform_admin(self.request.user):
            qs = qs.filter(is_active=True)
        return qs

    def _require_admin(self):
        user = self.request.user
        institution = self.get_object().institution
        if is_platform_admin(user):
            require_platform_admin(user)
        else:
            require_institution_admin(user, institution)

    def perform_update(self, serializer):
        self._require_admin()
        instance = serializer.save()
        record_audit(
            request=self.request,
            action=AuditEvent.Action.DEPARTMENT_UPDATED,
            object_type="department",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"fields": sorted(serializer.validated_data.keys())},
        )

    def perform_destroy(self, instance):
        self._require_admin()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        record_audit(
            request=self.request,
            action=AuditEvent.Action.DEPARTMENT_DELETED,
            object_type="department",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"name": instance.name},
        )


# ── Specialties ────────────────────────────────────────────────────────
class SpecialtyListCreateView(generics.ListCreateAPIView):
    serializer_class = SpecialtySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]
    filterset_fields = ["is_active"]

    def get_queryset(self) -> QuerySet[Specialty]:
        qs = Specialty.objects.all()
        if not is_platform_admin(self.request.user):
            qs = qs.filter(is_active=True)
        return qs

    def create(self, request, *args, **kwargs):
        require_platform_admin(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        record_audit(
            request=request,
            action=AuditEvent.Action.SPECIALTY_CREATED,
            object_type="specialty",
            object_pk=instance.pk,
            metadata={"name": instance.name},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Memberships ────────────────────────────────────────────────────────
class MembershipListCreateView(generics.ListCreateAPIView):
    serializer_class = MembershipSerializer
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    filterset_fields = ["institution", "role", "is_active", "user"]
    ordering_fields = ["created_at", "role"]
    ordering = ["-created_at"]

    def get_queryset(self) -> QuerySet[RoleAssignment]:
        user = self.request.user
        institution_param = self.request.query_params.get("institution")
        if is_platform_admin(user):
            qs = RoleAssignment.objects.all()
        elif institution_param:
            institution_id = _parse_uuid(institution_param, "institution")
            institution = Institution.objects.filter(pk=institution_id).first()
            if institution is None:
                raise exceptions.NotFound()
            require_institution_admin(user, institution)
            qs = RoleAssignment.objects.filter(institution_id=institution_id)
        else:
            qs = RoleAssignment.objects.filter(user=user)
        return qs.select_related("user", "institution", "department", "granted_by")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        institution = serializer.validated_data.get("institution")
        if role in PLATFORM_SCOPED_ROLES or is_platform_admin(request.user):
            require_platform_admin(request.user)
        else:
            require_institution_admin(request.user, institution)
        instance = serializer.save()
        record_audit(
            request=request,
            action=AuditEvent.Action.ROLE_GRANTED,
            object_type="role_assignment",
            object_pk=instance.pk,
            institution=institution,
            metadata={"role": role, "user": instance.user.email},
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class MembershipDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MembershipSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[RoleAssignment]:
        user = self.request.user
        if is_platform_admin(user):
            qs = RoleAssignment.objects.all()
        else:
            administered = administered_institution_ids(user)
            qs = RoleAssignment.objects.filter(
                institution_id__in=administered
            ) | RoleAssignment.objects.filter(user=user)
        return qs.select_related("user", "institution", "department", "granted_by")

    def _require_admin_for(self, instance):
        user = self.request.user
        if instance.institution_id is None:
            require_platform_admin(user)
        elif is_platform_admin(user):
            require_platform_admin(user)
        else:
            require_institution_admin(user, instance.institution)

    def perform_update(self, serializer):
        instance = serializer.instance
        self._require_admin_for(instance)
        updated = serializer.save()
        action = (
            AuditEvent.Action.ROLE_REVOKED
            if not updated.is_active
            else AuditEvent.Action.ROLE_UPDATED
        )
        record_audit(
            request=self.request,
            action=action,
            object_type="role_assignment",
            object_pk=updated.pk,
            institution=updated.institution,
            metadata={"fields": sorted(serializer.validated_data.keys())},
        )

    def perform_destroy(self, instance):
        self._require_admin_for(instance)
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        record_audit(
            request=self.request,
            action=AuditEvent.Action.ROLE_REVOKED,
            object_type="role_assignment",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"role": instance.role, "user": instance.user.email},
        )


# ── Invitations ────────────────────────────────────────────────────────
class InvitationListCreateView(generics.ListCreateAPIView):
    serializer_class = InvitationSerializer
    filterset_fields = ["institution", "role", "email"]
    ordering_fields = ["created_at", "expires_at"]
    ordering = ["-created_at"]

    def get_queryset(self) -> QuerySet[Invitation]:
        user = self.request.user
        if is_platform_admin(user):
            qs = Invitation.objects.all()
        else:
            administered = administered_institution_ids(user)
            if not administered:
                raise exceptions.PermissionDenied(
                    "Invitation access requires an institutional administrator role."
                )
            qs = Invitation.objects.filter(institution_id__in=administered)
        return qs.select_related("institution", "department", "invited_by")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        institution = serializer.validated_data["institution"]
        if is_platform_admin(request.user):
            require_platform_admin(request.user)
        else:
            require_institution_admin(request.user, institution)
        instance = serializer.save(invited_by=request.user)
        record_audit(
            request=request,
            action=AuditEvent.Action.INVITATION_SENT,
            object_type="invitation",
            object_pk=instance.pk,
            institution=institution,
            metadata={"role": instance.role, "email": instance.email},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InvitationAcceptView(views.APIView):
    """Public: an invitation token proves control of the invited mailbox."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "password"

    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation: Invitation = serializer.context["invitation"]
        password = serializer.validated_data.get("password") or ""

        user = User.objects.filter(email=invitation.email).first()
        created = False
        if user is None:
            if not password:
                raise exceptions.ValidationError(
                    {"password": "A password is required to create the account."}
                )
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password)
            except DjangoValidationError as exc:
                raise exceptions.ValidationError(list(exc.messages)) from exc
            user = User(
                email=invitation.email,
                first_name=serializer.validated_data.get("first_name", ""),
                last_name=serializer.validated_data.get("last_name", ""),
                is_verified=True,
            )
            user.set_password(password)
            user.save()
            created = True

        try:
            RoleAssignment.objects.create(
                user=user,
                role=invitation.role,
                institution=invitation.institution,
                department=invitation.department,
            )
        except DjangoValidationError as exc:
            raise exceptions.ValidationError(
                getattr(exc, "message_dict", {"non_field_errors": list(exc.messages)})
            ) from exc

        invitation.accepted_at = timezone.now()
        invitation.accepted_by = user
        invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])

        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.INVITATION_ACCEPTED,
            object_type="invitation",
            object_pk=invitation.pk,
            institution=invitation.institution,
            metadata={"role": invitation.role, "new_account": created},
        )
        return Response(
            {
                "message": "Invitation accepted. You can now sign in.",
                "user": MeSerializer(user).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class InvitationRevokeView(views.APIView):
    def post(self, request, pk):
        invitation = (
            Invitation.objects.select_related("institution").filter(pk=pk).first()
        )
        if invitation is None:
            raise exceptions.NotFound()
        user = request.user
        if is_platform_admin(user):
            require_platform_admin(user)
        else:
            require_institution_admin(user, invitation.institution)
        if invitation.accepted_at is not None:
            raise exceptions.ValidationError(
                {"invitation": "This invitation was already accepted."}
            )
        if invitation.revoked_at is None:
            invitation.revoked_at = timezone.now()
            invitation.save(update_fields=["revoked_at", "updated_at"])
            record_audit(
                request=request,
                action=AuditEvent.Action.INVITATION_REVOKED,
                object_type="invitation",
                object_pk=invitation.pk,
                institution=invitation.institution,
                metadata={"email": invitation.email},
            )
        return Response({"message": "Invitation revoked."})
