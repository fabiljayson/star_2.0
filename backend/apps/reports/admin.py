from django.contrib import admin

from .models import ReportJob


@admin.register(ReportJob)
class ReportJobAdmin(admin.ModelAdmin):
    list_display = ("report_type", "format", "status", "requester", "created_at")
    list_filter = ("report_type", "format", "status")
    search_fields = ("requester__email", "artifact_name")
    readonly_fields = ("created_at", "updated_at")
