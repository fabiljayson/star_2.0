from .base import *  # noqa: F401,F403
from .base import SECRET_KEY

DEBUG = True

if not SECRET_KEY:
    SECRET_KEY = "dev-only-insecure-key-set-DJANGO_SECRET_KEY-in-.env"

# Development never waits on an SMTP server: messages print to the console.
MAILERS["default"]["BACKEND"] = "django.core.mail.backends.console.EmailBackend"  # noqa: F405

ALLOWED_HOSTS = ["*"]  # noqa: F405
