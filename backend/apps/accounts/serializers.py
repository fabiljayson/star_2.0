from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from .models import (
    OPEN_REGISTRATION_ROLES,
    RoleAssignment,
    User,
    UserRole,
)


# ── Role / user representations ────────────────────────────────────────
class RoleAssignmentBriefSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "role",
            "institution",
            "institution_name",
            "department",
            "department_name",
            "is_active",
        ]
        read_only_fields = fields


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_verified",
            "is_platform_admin",
            "roles",
            "created_at",
        ]
        read_only_fields = fields

    def get_roles(self, obj) -> list[dict]:
        assignments = obj.role_assignments.select_related(
            "institution", "department"
        ).filter(is_active=True)
        return RoleAssignmentBriefSerializer(assignments, many=True).data


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_verified",
            "is_platform_admin",
            "mfa_enabled",
            "roles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "is_verified",
            "is_platform_admin",
            "mfa_enabled",
            "roles",
            "created_at",
            "updated_at",
        ]

    def get_roles(self, obj) -> list[dict]:
        assignments = obj.role_assignments.select_related(
            "institution", "department"
        ).filter(is_active=True)
        return RoleAssignmentBriefSerializer(assignments, many=True).data


# ── Registration / login ───────────────────────────────────────────────
class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=[(role, role) for role in sorted(OPEN_REGISTRATION_ROLES)],
        default=UserRole.BUYER,
    )

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data) -> User:
        user = User(
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            is_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
        )
        user.set_password(validated_data["password"])
        user.save()
        RoleAssignment.objects.create(
            user=user,
            role=validated_data["role"],
            institution=None,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")
        attrs["user"] = user
        return attrs


# ── Account recovery / verification ────────────────────────────────────
class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class PasswordForgotSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


# ── MFA ────────────────────────────────────────────────────────────────
class MFAVerifySerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    code = serializers.CharField(max_length=8)


class MFACodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8)
