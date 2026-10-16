from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import (
    INSTITUTION_SCOPED_ROLES,
    PLATFORM_SCOPED_ROLES,
    RoleAssignment,
    User,
    UserRole,
)
from apps.accounts.serializers import UserSummarySerializer

from .models import Department, Institution, Invitation, Specialty


def _django_validation_message(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"non_field_errors": list(exc.messages)}


# ── Institutions / departments / specialties ───────────────────────────
class InstitutionSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(read_only=True)

    class Meta:
        model = Institution
        fields = [
            "id",
            "name",
            "slug",
            "institution_type",
            "country",
            "city",
            "address",
            "website",
            "contact_email",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not (user.is_authenticated and user.is_platform_admin):
            self.fields["is_active"].read_only = True

    def validate_name(self, value: str) -> str:
        qs = Institution.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An institution with this name already exists."
            )
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "institution",
            "institution_name",
            "name",
            "code",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "institution_name", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        institution = self.initial_data.get("institution") or (
            self.instance.institution_id if self.instance else None
        )
        if institution:
            qs = Department.objects.filter(institution=institution, name__iexact=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A department with this name already exists in this institution."
                )
        return value

    def create(self, validated_data) -> Department:
        instance = Department(**validated_data)
        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc
        return instance


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name", "code", "description", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_code(self, value: str) -> str:
        return value.strip().lower()


# ── Memberships (role assignments) ─────────────────────────────────────
class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    user_detail = UserSummarySerializer(source="user", read_only=True)
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "user_detail",
            "role",
            "institution",
            "institution_name",
            "department",
            "department_name",
            "is_active",
            "granted_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "granted_by", "created_at", "updated_at"]

    def validate_role(self, value: str) -> str:
        if value == UserRole.PLATFORM_ADMIN:
            raise serializers.ValidationError(
                "Platform administration is granted on the user account, not here."
            )
        return value

    def validate(self, attrs):
        role = attrs.get("role", self.instance.role if self.instance else None)
        institution = attrs.get(
            "institution", self.instance.institution if self.instance else None
        )
        user = attrs.get("user", self.instance.user if self.instance else None)
        department = attrs.get(
            "department", self.instance.department if self.instance else None
        )
        if role in INSTITUTION_SCOPED_ROLES and institution is None:
            raise serializers.ValidationError(
                {"institution": "This role requires an institution."}
            )
        if role in PLATFORM_SCOPED_ROLES and institution is not None:
            raise serializers.ValidationError(
                {"institution": "This role must not carry an institution."}
            )
        if department and institution and department.institution_id != institution.pk:
            raise serializers.ValidationError(
                {"department": "Department does not belong to this institution."}
            )
        if self.instance is None and role and user:
            duplicate_qs = RoleAssignment.objects.filter(user=user, role=role)
            duplicate_qs = (
                duplicate_qs.filter(institution=institution)
                if institution
                else duplicate_qs.filter(institution__isnull=True)
            )
            if duplicate_qs.exists():
                raise serializers.ValidationError(
                    {"role": "This user already holds this role in this scope."}
                )
        return attrs

    def create(self, validated_data) -> RoleAssignment:
        request = self.context.get("request")
        validated_data["granted_by"] = getattr(request, "user", None)
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc


# ── Invitations ────────────────────────────────────────────────────────
class InvitationSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "institution",
            "institution_name",
            "email",
            "role",
            "department",
            "invited_by",
            "invited_by_email",
            "token",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "invited_by",
            "invited_by_email",
            "token",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "created_at",
        ]

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_role(self, value: str) -> str:
        if value not in INSTITUTION_SCOPED_ROLES:
            raise serializers.ValidationError("Only institutional roles can be invited.")
        return value

    def validate(self, attrs):
        department = attrs.get("department")
        institution = attrs.get("institution")
        if department and institution and department.institution_id != institution.pk:
            raise serializers.ValidationError(
                {"department": "Department does not belong to this institution."}
            )
        return attrs

    def create(self, validated_data) -> Invitation:
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(_django_validation_message(exc)) from exc


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, required=False, allow_blank=True
    )
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_token(self, value):
        invitation = (
            Invitation.objects.filter(token=value)
            .select_related("institution", "department")
            .first()
        )
        if invitation is None:
            raise serializers.ValidationError("This invitation is invalid or unknown.")
        if invitation.revoked_at is not None:
            raise serializers.ValidationError("This invitation was revoked.")
        if invitation.accepted_at is not None:
            raise serializers.ValidationError("This invitation was already used.")
        if invitation.expires_at <= timezone.now():
            raise serializers.ValidationError("This invitation has expired.")
        self.context["invitation"] = invitation
        return value
