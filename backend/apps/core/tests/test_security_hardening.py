"""Regression tests for the security guarantees documented in README.md.

Most guarantees are behavioural and already covered by per-app suites
(throttling, magic bytes, 404 isolation, webhook signatures). This module
locks the *configuration invariants*: a settings change that silently
weakens a documented guarantee must fail CI before it can reach prod.
"""

import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.logbook.uploads import private_storage as logbook_storage


def _load_production():
    sys.modules.pop("config.settings.production", None)
    return importlib.import_module("config.settings.production")


# ── Settings invariants ────────────────────────────────────────────────
class TestSettingsInvariants:
    def test_jwt_tokens_rotate_and_blacklist(self):
        from config.settings import base

        jwt = base.SIMPLE_JWT
        assert jwt["ROTATE_REFRESH_TOKENS"] is True
        assert jwt["BLACKLIST_AFTER_ROTATION"] is True
        assert jwt["ACCESS_TOKEN_LIFETIME"].total_seconds() <= 900
        assert "rest_framework_simplejwt.token_blacklist" in list(base.INSTALLED_APPS)

    def test_every_sensitive_auth_endpoint_is_rate_limited(self):
        from config.settings import base

        rates = base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        for scope in ("login", "register", "password", "mfa"):
            assert rates.get(scope), f"Missing throttle rate for scope '{scope}'"

        from apps.accounts import views as accounts_views

        declared = {
            getattr(cls, "throttle_scope", None)
            for cls in vars(accounts_views).values()
            if isinstance(cls, type) and getattr(cls, "throttle_classes", None)
        }
        assert {"login", "register", "password", "mfa"} <= declared

    def test_production_lockdown_cannot_be_disabled(self, monkeypatch):
        from config.settings import base as base_module

        monkeypatch.setenv("DJANGO_SECRET_KEY", "ci-scenario-strong-secret-key-1f2e3d4c")
        monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "star.example.com")
        importlib.reload(base_module)
        try:
            production = _load_production()
        finally:
            importlib.reload(base_module)

        assert production.DEBUG is False
        assert production.PAYMENTS_ACCEPT_MOCK is False
        assert production.SECURE_SSL_REDIRECT is True
        assert production.SESSION_COOKIE_SECURE is True
        assert production.CSRF_COOKIE_SECURE is True
        assert production.SECURE_HSTS_SECONDS >= 31536000
        assert production.SECURE_HSTS_PRELOAD is True
        assert production.SECURE_CONTENT_TYPE_NOSNIFF is True
        assert production.X_FRAME_OPTIONS == "DENY"
        assert production.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        assert production.ALLOWED_HOSTS == ["star.example.com"]

    def test_production_rejects_weak_or_missing_secret(self, monkeypatch):
        from config.settings import base as base_module

        monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "star.example.com")
        monkeypatch.setenv("DJANGO_SECRET_KEY", "")
        importlib.reload(base_module)
        try:
            with pytest.raises(ImproperlyConfigured):
                _load_production()

            monkeypatch.setenv("DJANGO_SECRET_KEY", "dev-only-insecure-key")
            importlib.reload(base_module)
            with pytest.raises(ImproperlyConfigured):
                _load_production()
        finally:
            monkeypatch.setenv("DJANGO_SECRET_KEY", "star-test-secret-key-not-for-production-use")
            importlib.reload(base_module)


# ── Private media storage ───────────────────────────────────────────────
class TestPrivateStorage:
    def test_clinical_files_have_no_public_url(self):
        with pytest.raises(ValueError):
            logbook_storage.url("procedures/abc.pdf")

    def test_dispute_evidence_uses_private_storage(self):
        from apps.marketplace.models import DisputeEvidence

        storage = DisputeEvidence._meta.get_field("file").storage
        assert storage is logbook_storage

    def test_storage_lives_outside_any_served_media_root(self, tmp_path, settings):
        settings.PRIVATE_MEDIA_ROOT = tmp_path
        assert logbook_storage.base_location == str(tmp_path)
        served = {str(settings.MEDIA_ROOT or "")} - {""}
        assert str(tmp_path) not in served
