import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


# ── Roles ──────────────────────────────────────────────────────────────
class UserRole(models.TextChoices):
    INDEPENDENT_SURGEON = "independent_surgeon", "Independent surgeon"
    TRAINEE = "trainee", "Trainee / resident"
    SUPERVISOR = "supervisor", "Supervising surgeon"
    EXAMINER = "examiner", "Examiner"
    DEPARTMENT_MANAGER = "department_manager", "Department / service manager"
    INSTITUTION_ADMIN = "institution_admin", "Institution administrator"
    SUPPLIER = "supplier", "Verified equipment supplier"
    BUYER = "buyer", "Authorized equipment buyer"
    PLATFORM_ADMIN = "platform_admin", "Platform administrator"


INSTITUTION_SCOPED_ROLES = frozenset(
    {
        UserRole.TRAINEE,
        UserRole.SUPERVISOR,
        UserRole.EXAMINER,
        UserRole.DEPARTMENT_MANAGER,
        UserRole.INSTITUTION_ADMIN,
    }
)

PLATFORM_SCOPED_ROLES = frozenset(
    {
        UserRole.INDEPENDENT_SURGEON,
        UserRole.SUPPLIER,
        UserRole.BUYER,
        UserRole.PLATFORM_ADMIN,
    }
)

# Self-registration may only request these roles; institutional roles are
# granted by invitation or by an institution administrator.
OPEN_REGISTRATION_ROLES = frozenset(
    {UserRole.INDEPENDENT_SURGEON, UserRole.BUYER, UserRole.SUPPLIER}
)


# ── User ───────────────────────────────────────────────────────────────
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_active", True)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_active", True)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_platform_admin", True)
        return self._create_user(email, password, **extra)


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_platform_admin = models.BooleanField(default=False)
    auth_version = models.PositiveIntegerField(
        default=1,
        help_text="Bumped to revoke every outstanding token of this user.",
    )
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        indexes = [models.Index(fields=["is_platform_admin"], name="user_platform_admin")]

    def __str__(self):
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        original_active = None
        if self.pk:
            original_active = (
                User.objects.filter(pk=self.pk).values_list("is_active", flat=True).first()
            )
        if original_active is True and not self.is_active:
            self.auth_version += 1
        if self.is_platform_admin:
            self.is_staff = True
        super().save(*args, **kwargs)

    def bump_auth_version(self) -> None:
        self.auth_version += 1
        self.save(update_fields=["auth_version", "updated_at"])

    def has_role(self, role: str, institution=None) -> bool:
        from apps.core.permissions import has_role

        return has_role(self, role, institution=institution)


# ── Role assignments (institution memberships + platform roles) ────────
class RoleAssignment(UUIDModel, TimeStampedModel):
    """A role grant for a user.

    Institution-scoped roles carry the institution they belong to (this is
    also the user's membership in that institution); platform-scoped roles
    keep institution NULL. Platform administration itself is represented by
    `User.is_platform_admin`, not by a row here.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.CharField(max_length=40, choices=UserRole.choices, db_index=True)
    institution = models.ForeignKey(
        "organizations.Institution",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    department = models.ForeignKey(
        "organizations.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="role_assignments",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="granted_role_assignments",
    )

    class Meta:
        verbose_name = "role assignment"
        verbose_name_plural = "role assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "institution"],
                name="uniq_user_role_institution",
            ),
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=Q(institution__isnull=True),
                name="uniq_user_platform_role",
            ),
        ]
        indexes = [
            models.Index(fields=["institution", "role", "is_active"], name="role_inst_scope"),
            models.Index(fields=["user", "is_active"], name="role_user_active"),
        ]

    def clean(self):
        if self.role == UserRole.PLATFORM_ADMIN:
            raise ValidationError(
                {"role": "Platform administration is granted via the user flag."}
            )
        if self.role in INSTITUTION_SCOPED_ROLES and self.institution_id is None:
            raise ValidationError({"institution": "This role requires an institution."})
        if self.role in PLATFORM_SCOPED_ROLES and self.institution_id is not None:
            raise ValidationError({"institution": "This role must not carry an institution."})
        if self.department_id and self.institution_id:
            if self.department.institution_id != self.institution_id:
                raise ValidationError(
                    {"department": "Department does not belong to this institution."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope = self.institution.name if self.institution_id else "platform"
        return f"{self.user.email} · {self.role} · {scope}"


# ── Single-use authentication tokens ───────────────────────────────────
class AuthTokenPurpose(models.TextChoices):
    EMAIL_VERIFICATION = "email_verification", "Email verification"
    PASSWORD_RESET = "password_reset", "Password reset"


def _default_action_token() -> str:
    return secrets.token_urlsafe(32)


class AuthActionToken(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_action_tokens",
    )
    purpose = models.CharField(max_length=32, choices=AuthTokenPurpose.choices)
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_default_action_token,
        editable=False,
    )
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "auth action token"
        verbose_name_plural = "auth action tokens"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at", "updated_at"])

    def __str__(self):
        return f"{self.purpose} for {self.user.email}"


# ── MFA login session (password OK, second factor pending) ─────────────
class MFASession(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mfa_sessions",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_default_action_token,
        editable=False,
    )
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "MFA session"
        verbose_name_plural = "MFA sessions"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at", "updated_at"])
