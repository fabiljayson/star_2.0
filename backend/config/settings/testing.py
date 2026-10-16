from .base import *  # noqa: F401,F403

DEBUG = False

# Test-only key; production must set DJANGO_SECRET_KEY in the environment.
SECRET_KEY = "star-test-secret-key-not-for-production-use"  # noqa: S105

# Fast hashing is acceptable only inside automated tests.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
}

# Dummy cache: throttles stay deterministic per test unless a test opts in
# to a real cache via override_settings.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Tests run against the local PostgreSQL (pytest-django creates test_star).
