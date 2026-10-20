from django.contrib import admin

from .models import Policy, PolicyConsent, PolicyVersion, PrivacyRequest


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "category")
    search_fields = ("title", "slug", "summary")


@admin.register(PolicyVersion)
class PolicyVersionAdmin(admin.ModelAdmin):
    list_display = (
        "policy",
        "language",
        "version",
        "status",
        "effective_date",
        "published_at",
    )
    list_filter = ("status", "language", "policy")
    search_fields = ("title", "version")
    extra = 0


@admin.register(PolicyConsent)
class PolicyConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "policy", "policy_version", "context", "created_at")
    list_filter = ("policy", "context")
    search_fields = ("user__email", "policy__slug")

    def get_readonly_fields(self, request, obj=None):
        return ("user", "policy", "policy_version", "context")


@admin.register(PrivacyRequest)
class PrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "status", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("user__email", "message")
