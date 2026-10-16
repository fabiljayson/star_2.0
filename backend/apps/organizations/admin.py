from django.contrib import admin

from .models import Department, Institution, Invitation, Specialty


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["name", "institution_type", "country", "city", "is_active"]
    list_filter = ["institution_type", "is_active"]
    search_fields = ["name", "city", "country"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "institution", "is_active"]
    list_filter = ["is_active", "institution"]
    search_fields = ["name", "code", "institution__name"]


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "role", "institution", "expires_at", "accepted_at", "revoked_at"]
    list_filter = ["role", "institution"]
    search_fields = ["email"]
    readonly_fields = [field.name for field in Invitation._meta.fields]
