from __future__ import annotations

import uuid as uuid_lib

from django.conf import settings
from django.db.models import QuerySet
from rest_framework import generics, permissions, status, throttling, views
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.audit import record_audit
from apps.core.exceptions import EmailNotVerified
from apps.core.models import AuditEvent
from apps.core.permissions import administered_institution_ids

from . import services
from .jwt import StarTokenRefreshSerializer
from .models import AuthTokenPurpose, User, UserRole
from .serializers import (
    LoginSerializer,
    MeSerializer,
    MFACodeSerializer,
    MFAVerifySerializer,
    PasswordForgotSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    UserSummarySerializer,
    VerifyEmailSerializer,
)


# ── Registration & verification ────────────────────────────────────────
class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        user = serializer.save()

        verification_token = None
        if settings.REQUIRE_EMAIL_VERIFICATION:
            verification_token = services.create_action_token(
                user, AuthTokenPurpose.EMAIL_VERIFICATION
            )
            services.send_verification_email(user, verification_token.token)

        record_audit(
            action=AuditEvent.Action.AUTH_REGISTERED,
            request=request,
            actor=user,
            object_type="user",
            object_pk=user.pk,
            metadata={"role": role},
        )
        data = {
            "message": (
                "Account created. Check your inbox to verify your email address."
                if verification_token
                else "Account created."
            ),
            "user": MeSerializer(user).data,
        }
        if verification_token and settings.DEBUG:
            data["verification_token"] = verification_token.token
        return Response(data, status=status.HTTP_201_CREATED)


class VerifyEmailView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "password"

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.consume_action_token(
            serializer.validated_data["token"], AuthTokenPurpose.EMAIL_VERIFICATION
        )
        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified", "updated_at"])
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.AUTH_EMAIL_VERIFIED,
            object_type="user",
            object_pk=user.pk,
        )
        return Response({"message": "Email address verified."})


# ── Login / refresh / logout ───────────────────────────────────────────
class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
            raise EmailNotVerified()

        if user.mfa_enabled:
            session, ttl = services.start_mfa_session(user)
            return Response(
                {
                    "mfa_required": True,
                    "mfa_token": session.token,
                    "expires_in": ttl,
                }
            )

        tokens = services.issue_token_pair(user)
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.AUTH_LOGIN,
            object_type="user",
            object_pk=user.pk,
            metadata={"mfa": False},
        )
        return Response(
            {"mfa_required": False, **tokens, "user": MeSerializer(user).data}
        )


class StarTokenRefreshView(TokenRefreshView):
    serializer_class = StarTokenRefreshSerializer


class LogoutView(views.APIView):
    def post(self, request):
        raw_refresh = request.data.get("refresh")
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except (TokenError, AttributeError):
                pass
        record_audit(
            request=request,
            action=AuditEvent.Action.AUTH_LOGOUT,
            object_type="user",
            object_pk=request.user.pk,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(views.APIView):
    """Revoke every outstanding access and refresh token of the user."""

    def post(self, request):
        request.user.bump_auth_version()
        record_audit(
            request=request,
            action=AuditEvent.Action.AUTH_LOGOUT_ALL,
            object_type="user",
            object_pk=request.user.pk,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Password recovery ──────────────────────────────────────────────────
class PasswordForgotView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "password"

    def post(self, request):
        serializer = PasswordForgotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user is not None:
            token = services.create_action_token(user, AuthTokenPurpose.PASSWORD_RESET)
            services.send_password_reset_email(user, token.token)
            record_audit(
                request=request,
                actor=user,
                action=AuditEvent.Action.AUTH_PASSWORD_RESET_REQUESTED,
                object_type="user",
                object_pk=user.pk,
            )
        # Same response either way: never reveal whether the account exists.
        return Response(
            {"message": "If an account exists for this address, a reset link was sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "password"

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.consume_action_token(
            serializer.validated_data["token"], AuthTokenPurpose.PASSWORD_RESET
        )
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password", "updated_at"])
        user.bump_auth_version()
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.AUTH_PASSWORD_RESET,
            object_type="user",
            object_pk=user.pk,
        )
        return Response({"message": "Password updated. Please sign in again."})


# ── MFA ────────────────────────────────────────────────────────────────
class MFASetupView(views.APIView):
    def post(self, request):
        user = request.user
        if user.mfa_enabled:
            raise ValidationError({"mfa": "Multi-factor authentication is already enabled."})
        secret = services.generate_mfa_secret()
        user.mfa_secret = secret
        user.save(update_fields=["mfa_secret", "updated_at"])
        return Response(
            {
                "secret": secret,
                "otpauth_url": services.mfa_provisioning_uri(user, secret),
                "next_step": "Confirm with a code at /api/v1/auth/mfa/enable/.",
            }
        )


class MFAEnableView(views.APIView):
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MFACodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not services.verify_totp(user.mfa_secret, serializer.validated_data["code"]):
            raise AuthenticationFailed("Invalid verification code.")
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled", "updated_at"])
        record_audit(
            request=request,
            action=AuditEvent.Action.AUTH_MFA_ENABLED,
            object_type="user",
            object_pk=user.pk,
        )
        return Response({"message": "Multi-factor authentication enabled."})


class MFADisableView(views.APIView):
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MFACodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.mfa_enabled:
            raise ValidationError({"mfa": "Multi-factor authentication is not enabled."})
        if not services.verify_totp(user.mfa_secret, serializer.validated_data["code"]):
            raise AuthenticationFailed("Invalid verification code.")
        user.mfa_enabled = False
        user.mfa_secret = ""
        user.save(update_fields=["mfa_enabled", "mfa_secret", "updated_at"])
        record_audit(
            request=request,
            action=AuditEvent.Action.AUTH_MFA_DISABLED,
            object_type="user",
            object_pk=user.pk,
        )
        return Response({"message": "Multi-factor authentication disabled."})


class MFAVerifyView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.consume_mfa_session(
            serializer.validated_data["mfa_token"], serializer.validated_data["code"]
        )
        tokens = services.issue_token_pair(user)
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.AUTH_LOGIN,
            object_type="user",
            object_pk=user.pk,
            metadata={"mfa": True},
        )
        return Response(
            {"mfa_required": False, **tokens, "user": MeSerializer(user).data}
        )


# ── Current user ───────────────────────────────────────────────────────
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer

    def get_object(self) -> User:
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            del instance._prefetched_objects_cache
        record_audit(
            request=request,
            action=AuditEvent.Action.USER_UPDATED,
            object_type="user",
            object_pk=instance.pk,
            metadata={"fields": sorted(serializer.validated_data.keys())},
        )
        return Response(serializer.data)


# ── User directory (institution-scoped) ────────────────────────────────
class UserListView(generics.ListAPIView):
    serializer_class = UserSummarySerializer
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["created_at", "email", "last_name"]
    ordering = ["created_at"]

    def get_queryset(self) -> QuerySet[User]:
        user = self.request.user
        params = self.request.query_params
        institution_param = params.get("institution")
        role_param = params.get("role")

        if role_param and role_param not in UserRole.values:
            raise ValidationError({"role": "Unknown role."})

        allowed: list | None = None
        if not user.is_platform_admin:
            allowed = administered_institution_ids(user)
            if not allowed:
                raise PermissionDenied(
                    "User directory access requires an institutional administrator role."
                )

        if institution_param:
            try:
                institution_uuid = uuid_lib.UUID(institution_param)
            except ValueError:
                raise ValidationError({"institution": "Invalid institution id."}) from None
            if allowed is not None and institution_uuid not in allowed:
                raise PermissionDenied("You do not administer this institution.")
            qs = User.objects.filter(
                role_assignments__institution_id=institution_uuid,
                role_assignments__is_active=True,
            )
        elif allowed is not None:
            qs = User.objects.filter(
                role_assignments__institution_id__in=allowed,
                role_assignments__is_active=True,
            )
        else:
            qs = User.objects.all()

        if role_param:
            qs = qs.filter(role_assignments__role=role_param, role_assignments__is_active=True)
        return qs.distinct().order_by("created_at")
