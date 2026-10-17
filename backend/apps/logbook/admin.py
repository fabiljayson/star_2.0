from django.contrib import admin

from .models import (
    Attachment,
    PatientReference,
    ProcedureNoteVersion,
    ProcedureParticipant,
    ReviewDecision,
    SurgicalProcedure,
)


@admin.register(SurgicalProcedure)
class SurgicalProcedureAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "procedure_name",
        "institution",
        "status",
        "procedure_date",
    )
    list_filter = ("status", "category", "institution")
    search_fields = ("reference", "procedure_name")
    ordering = ("-procedure_date",)
    readonly_fields = ("reference", "version", "author", "created_at", "updated_at")


@admin.register(PatientReference)
class PatientReferenceAdmin(admin.ModelAdmin):
    list_display = ("code", "institution", "is_active", "created_at")
    list_filter = ("is_active", "institution")
    search_fields = ("code",)
    readonly_fields = ("code", "created_by", "created_at", "updated_at")


@admin.register(ProcedureParticipant)
class ProcedureParticipantAdmin(admin.ModelAdmin):
    list_display = ("procedure", "user", "role")
    search_fields = ("user__email", "procedure__reference")


@admin.register(ReviewDecision)
class ReviewDecisionAdmin(admin.ModelAdmin):
    list_display = ("procedure", "decision", "reviewer", "created_at")
    list_filter = ("decision",)
    search_fields = ("procedure__reference",)


@admin.register(ProcedureNoteVersion)
class ProcedureNoteVersionAdmin(admin.ModelAdmin):
    list_display = ("procedure", "version", "change_kind", "created_at")
    search_fields = ("procedure__reference",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "procedure", "size_bytes", "uploaded_by", "created_at")
    search_fields = ("original_name", "procedure__reference")
