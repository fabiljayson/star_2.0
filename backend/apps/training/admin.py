from django.contrib import admin

from .models import (
    Assessment,
    Competency,
    CompetencyRubricVersion,
    ExaminerAssignment,
    TrainingPlacement,
)


@admin.register(TrainingPlacement)
class TrainingPlacementAdmin(admin.ModelAdmin):
    list_display = ["title", "institution", "trainee", "status", "start_date"]
    list_filter = ["status", "institution"]
    search_fields = ["title", "trainee__email"]
    autocomplete_fields = ["trainee", "supervisor"]
    filter_horizontal = ["expected_competencies"]
    readonly_fields = ["created_by", "completed_at", "cancelled_at"]


@admin.register(ExaminerAssignment)
class ExaminerAssignmentAdmin(admin.ModelAdmin):
    list_display = ["placement", "examiner", "assigned_by", "created_at"]
    search_fields = ["examiner__email", "placement__title"]
    autocomplete_fields = ["examiner"]


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "institution", "is_active", "order"]
    list_filter = ["institution", "is_active"]
    search_fields = ["code", "title"]
    autocomplete_fields = ["institution"]


@admin.register(CompetencyRubricVersion)
class CompetencyRubricVersionAdmin(admin.ModelAdmin):
    list_display = ["competency", "version", "is_current", "created_at"]
    list_filter = ["is_current"]
    search_fields = ["competency__code", "competency__title"]
    readonly_fields = [
        "competency",
        "version",
        "levels",
        "notes",
        "is_current",
        "created_by",
        "created_at",
    ]

    def has_add_permission(self, request):
        # Rubric versions are created through the API workflow only.
        return False

    def has_change_permission(self, request, obj=None):
        # Historical rubric snapshots are immutable.
        return False


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ["competency", "placement", "status", "overall_level", "assessor"]
    list_filter = ["status", "placement__institution"]
    search_fields = ["competency__code", "placement__trainee__email"]
    readonly_fields = ["assessor", "decided_by", "submitted_at", "decided_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "placement", "competency", "assessor"
        )
