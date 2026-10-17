from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "category", "title", "is_read", "created_at"]
    list_filter = ["category", "is_read"]
    search_fields = ["recipient__email", "title"]
    readonly_fields = ["recipient", "category", "title", "body", "link", "actor", "object_type", "object_pk", "institution", "is_read", "read_at"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "in_app", "email"]
    list_filter = ["category", "in_app", "email"]
    search_fields = ["user__email"]
