from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import AuthActionToken, MFASession, RoleAssignment, User


class UserCreationFormWithEmail(UserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = [
        "email",
        "first_name",
        "last_name",
        "is_verified",
        "is_platform_admin",
        "is_active",
        "mfa_enabled",
    ]
    search_fields = ["email", "first_name", "last_name"]
    list_filter = ["is_active", "is_verified", "is_platform_admin", "mfa_enabled"]
    add_form = UserCreationFormWithEmail
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_platform_admin",
                    "is_verified",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Security",
            {"fields": ("auth_version", "mfa_enabled", "mfa_secret")},
        ),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_active",
                    "is_platform_admin",
                ),
            },
        ),
    )
    filter_horizontal = ["groups", "user_permissions"]
    readonly_fields = ["auth_version", "created_at", "updated_at"]


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ["user_email", "role", "institution", "department", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__email", "institution__name"]
    autocomplete_fields = ["user"]

    @admin.display(description="User")
    def user_email(self, obj):
        return obj.user.email


@admin.register(AuthActionToken)
class AuthActionTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "purpose", "expires_at", "used_at"]
    search_fields = ["user__email"]
    readonly_fields = [field.name for field in AuthActionToken._meta.fields]


@admin.register(MFASession)
class MFASessionAdmin(admin.ModelAdmin):
    list_display = ["user", "expires_at", "used_at"]
    search_fields = ["user__email"]
    readonly_fields = [field.name for field in MFASession._meta.fields]
