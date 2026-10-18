from .base import *  # noqa: F401,F403
from .base import SECRET_KEY

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("dev-only"):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Set a strong DJANGO_SECRET_KEY in the environment.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
if not ALLOWED_HOSTS:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS for production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Sandbox payments must never settle in production, regardless of environment.
PAYMENTS_ACCEPT_MOCK = False  # noqa: F405

# Operational logs never include clinical payloads; see docs/security.md.
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
