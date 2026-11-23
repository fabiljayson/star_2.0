from __future__ import annotations

from django.conf import settings
from rest_framework import exceptions
from rest_framework.permissions import BasePermission

from apps.accounts.models import INSTITUTION_SCOPED_ROLES, UserRole


class MFARequired(exceptions.PermissionDenied):
    default_code = "mfa_required"
    default_detail = (
        "Multi-factor authentication must be enabled before performing this action."
    )


def _mfa_policy_satisfied(user) -> bool:
    if not settings.REQUIRE_MFA_FOR_PLATFORM_ADMINS:
        return True
    if not user.is_platform_admin:
        return True
    return bool(user.mfa_enabled)


def is_platform_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_platform_admin)


def has_platform_admin_access(user) -> bool:
    """Platform-admin access with the MFA policy applied.

    Returns False for a user who is not a platform administrator. Raises
    `MFARequired` for a platform administrator who has not enrolled while the
    policy is enabled, so admin-only branches cannot bypass it.
    """
    if not is_platform_admin(user):
        return False
    if not _mfa_policy_satisfied(user):
        raise MFARequired()
    return True


def has_role(user, role: str, institution=None) -> bool:
    """True when the user holds an active `role` (institution-scoped when required)."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if role == UserRole.PLATFORM_ADMIN:
        return user.is_platform_admin and _mfa_policy_satisfied(user)
    from apps.accounts.models import RoleAssignment

    qs = RoleAssignment.objects.filter(user=user, role=role, is_active=True)
    if role in INSTITUTION_SCOPED_ROLES:
        if institution is None:
            return False
        return qs.filter(institution=institution).exists()
    return qs.filter(institution__isnull=True).exists()


def administered_institution_ids(user) -> list:
    from apps.accounts.models import RoleAssignment

    if not user or not user.is_authenticated:
        return []
    if user.is_platform_admin and _mfa_policy_satisfied(user):
        from apps.organizations.models import Institution

        return list(Institution.objects.values_list("id", flat=True))
    return list(
        RoleAssignment.objects.filter(
            user=user,
            role=UserRole.INSTITUTION_ADMIN,
            is_active=True,
            institution__isnull=False,
        )
        .values_list("institution_id", flat=True)
    )


def is_institution_admin(user, institution) -> bool:
    if institution is None:
        return False
    return has_role(user, UserRole.INSTITUTION_ADMIN, institution=institution)


def require_platform_admin(user, *, enforce_mfa: bool = True) -> None:
    if not user or not user.is_authenticated or not user.is_platform_admin:
        raise exceptions.PermissionDenied(
            "Platform administrator access required.",
            code="permission_denied",
        )
    if enforce_mfa and not _mfa_policy_satisfied(user):
        raise MFARequired()


def require_institution_admin(user, institution) -> None:
    if not is_institution_admin(user, institution):
        raise exceptions.PermissionDenied(
            "You do not administer this institution.",
            code="permission_denied",
        )


def require_role(user, role: str, institution=None) -> None:
    if not has_role(user, role, institution=institution):
        raise exceptions.PermissionDenied(
            "You do not have the required role for this action.",
            code="permission_denied",
        )


class IsPlatformAdmin(BasePermission):
    """Platform administrators only, with the optional MFA policy enforced."""

    message = "Platform administrator access required."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_platform_admin:
            return False
        if not _mfa_policy_satisfied(user):
            raise MFARequired()
        return True


class IsInstitutionAdminParam(BasePermission):
    """Read access for institution administrators of `?institution=` (or platform)."""

    message = "You do not administer this institution."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_platform_admin(user):
            return _mfa_policy_satisfied(user)
        institution_id = request.query_params.get("institution")
        if not institution_id:
            return True
        from apps.organizations.models import Institution

        institution = Institution.objects.filter(pk=institution_id).first()
        if institution is None:
            raise exceptions.NotFound("Institution not found.")
        return is_institution_admin(user, institution)
