from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "STAR core"

    def ready(self):
        from . import schema_ext  # noqa: F401 registers OpenAPI extensions
