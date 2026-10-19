import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


# ── Environment helpers ────────────────────────────────────────────────
def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def env_days(name: str, default: int) -> timedelta:
    return timedelta(days=env_int(name, default))


def env_minutes(name: str, default: int) -> timedelta:
    return timedelta(minutes=env_int(name, default))


# ── Core ───────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    # STAR apps
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.logbook",
    "apps.training",
    "apps.notifications",
    "apps.reports",
    "apps.marketplace",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ── Database ───────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "star"),
        "USER": os.environ.get("POSTGRES_USER", "star"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "star_dev_password"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5433"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
    }
}


# ── Auth ───────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

JWT_ACCESS_TOKEN_LIFETIME = env_minutes("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 15)
JWT_REFRESH_TOKEN_LIFETIME = env_days("JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7)
AUTH_ACTION_TOKEN_TTL = env_minutes("AUTH_TOKEN_TTL_MINUTES", 60)
MFA_SESSION_TTL = timedelta(minutes=5)
REQUIRE_MFA_FOR_PLATFORM_ADMINS = env_bool("REQUIRE_MFA_FOR_PLATFORM_ADMINS", False)
REQUIRE_EMAIL_VERIFICATION = env_bool("REQUIRE_EMAIL_VERIFICATION", True)


# ── Django REST Framework ──────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": env_int("API_PAGE_SIZE", 20),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_THROTTLE_RATES": {
        "login": os.environ.get("LOGIN_THROTTLE_RATE", "10/min"),
        "register": "5/hour",
        "password": "5/hour",
        "mfa": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": JWT_ACCESS_TOKEN_LIFETIME,
    "REFRESH_TOKEN_LIFETIME": JWT_REFRESH_TOKEN_LIFETIME,
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.jwt.StarTokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "apps.accounts.jwt.StarTokenRefreshSerializer",
}


# ── CORS (browser clients; API also reachable through the Vite proxy) ──
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174"
)
CORS_ALLOW_CREDENTIALS = False


# ── Email (development prints to the console) ──────────────────────────
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5174").rstrip("/")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "star@example.invalid")

MAILERS = {
    "default": {
        "BACKEND": os.environ.get(
            "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
        ),
        "HOST": os.environ.get("EMAIL_HOST", "localhost"),
        "PORT": env_int("EMAIL_PORT", 1025),
        "USERNAME": os.environ.get("EMAIL_HOST_USER", ""),
        "PASSWORD": os.environ.get("EMAIL_HOST_PASSWORD", ""),
        "USE_TLS": env_bool("EMAIL_USE_TLS", False),
        "TIMEOUT": env_int("EMAIL_TIMEOUT", 10),
    }
}


# ── Uploads / integrations ─────────────────────────────────────────────
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get("PRIVATE_MEDIA_ROOT") or BASE_DIR / "private_media"
)
ATTACHMENT_MAX_SIZE_MB = env_int("ATTACHMENT_MAX_SIZE_MB", 10)
ATTACHMENT_ALLOWED_EXTENSIONS = [
    ext.strip().lower()
    for ext in os.environ.get(
        "ATTACHMENT_ALLOWED_EXTENSIONS", ".jpg,.jpeg,.png,.webp,.pdf,.docx"
    ).split(",")
    if ext.strip()
]
AUDIO_RETENTION_DAYS = env_int("AUDIO_RETENTION_DAYS", 7)
PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "sandbox")
PAYMENT_WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "")
# A payment attempt stays open this long before the order auto-cancels.
PAYMENT_PENDING_TTL_HOURS = env_int("PAYMENT_PENDING_TTL_HOURS", 24)
# Sandbox outcomes (mock HMAC webhooks) are only honoured outside production;
# production.py forces this to False so mock money can never look real.
PAYMENTS_ACCEPT_MOCK = env_bool("PAYMENTS_ACCEPT_MOCK", True)
TRANSCRIPTION_PROVIDER = os.environ.get("TRANSCRIPTION_PROVIDER", "mock")
TRANSCRIPTION_MOCK_FAILURE = env_bool("TRANSCRIPTION_MOCK_FAILURE", False)
TRANSCRIPTION_LANGUAGES = [
    lang.strip().lower()
    for lang in os.environ.get("TRANSCRIPTION_LANGUAGES", "en,fr").split(",")
    if lang.strip()
]
AUDIO_MAX_SIZE_MB = env_int("AUDIO_MAX_SIZE_MB", 10)
AUDIO_ALLOWED_EXTENSIONS = [
    ext.strip().lower()
    for ext in os.environ.get(
        "AUDIO_ALLOWED_EXTENSIONS", ".wav,.ogg,.webm,.mp3,.m4a"
    ).split(",")
    if ext.strip()
]

# ── Reports / exports ──
REPORT_ARTIFACT_TTL_HOURS = env_int("REPORT_ARTIFACT_TTL_HOURS", 24)
REPORT_SYNC_ROW_LIMIT = env_int("REPORT_SYNC_ROW_LIMIT", 50000)


# ── API documentation ──────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "STAR API",
    "DESCRIPTION": (
        "STAR — Secure Surgical Tracking, Assessment & Resources platform. "
        "Versioned REST API for surgical logbook, training assessment, "
        "reporting and the surgical equipment marketplace."
    ),
    "VERSION": "v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": "apps.accounts.models.UserRole.choices",
        "ParticipantRoleEnum": "apps.logbook.models.ParticipantRole.choices",
    },
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "JWTAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Obtain an access token at `/api/v1/auth/login/` then send `Bearer <access>`.",
            }
        }
    },
    "SECURITY": [{"JWTAuth": []}],
}


# ── Logging (operational logs only — never clinical content) ──────────
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "star": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}


# ── Internationalization / time ────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
