import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import RoleAssignment, User, UserRole

from .factories import DEFAULT_TEST_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"


def _register(client, **overrides):
    payload = {
        "email": "New.Surgeon@Example.test",
        "password": DEFAULT_TEST_PASSWORD,
        "first_name": "New",
        "last_name": "Surgeon",
        "role": "independent_surgeon",
    }
    payload.update(overrides)
    return client.post(REGISTER_URL, payload)


class TestRegistration:
    def test_register_creates_account_and_platform_role(self, api):
        response = _register(api)
        assert response.status_code == 201, response.data

        user = User.objects.get(email="new.surgeon@example.test")
        assert user.is_verified is False  # verification required by default
        assert user.first_name == "New"
        assignment = RoleAssignment.objects.get(user=user)
        assert assignment.role == UserRole.INDEPENDENT_SURGEON
        assert assignment.institution is None
        assert len(mail.outbox) == 1
        assert "confirm your email" in mail.outbox[0].subject.lower()

    def test_register_rejects_reserved_roles(self, api):
        for role in ("platform_admin", "institution_admin", "examiner"):
            response = _register(api, email=f"reserved-{role}@example.test", role=role)
            assert response.status_code == 400, (role, response.data)

    def test_register_rejects_duplicate_email(self, api):
        _register(api)
        response = _register(api)
        assert response.status_code == 400
        assert "email" in str(response.data).lower()

    @override_settings(REQUIRE_EMAIL_VERIFICATION=False)
    def test_register_without_verification_requirement_is_verified(self, api):
        response = _register(api)
        assert response.status_code == 201
        user = User.objects.get(email="new.surgeon@example.test")
        assert user.is_verified is True
        assert len(mail.outbox) == 0

    def test_email_verification_flow(self, api, token_from_email):
        _register(api)
        token = token_from_email(mail.outbox[0].body)
        response = api.post("/api/v1/auth/verify/", {"token": token})
        assert response.status_code == 200, response.data
        user = User.objects.get(email="new.surgeon@example.test")
        assert user.is_verified is True

        reused = api.post("/api/v1/auth/verify/", {"token": token})
        assert reused.status_code == 400


class TestLogin:
    def test_login_returns_tokens_and_profile(self, api):
        user = UserFactory(email="login@example.test")
        response = api.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        assert response.status_code == 200, response.data
        assert response.data["mfa_required"] is False
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == "login@example.test"

    def test_login_with_wrong_password_is_401(self, api):
        user = UserFactory()
        response = api.post(LOGIN_URL, {"email": user.email, "password": "wrong-password"})
        assert response.status_code == 401
        assert response.data["error"]["code"] == "authentication_failed"

    def test_login_with_unknown_email_is_401(self, api):
        response = api.post(LOGIN_URL, {"email": "ghost@example.test", "password": "x"})
        assert response.status_code == 401

    def test_login_as_disabled_user_is_401(self, api):
        user = UserFactory(is_active=False)
        response = api.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        assert response.status_code == 401

    def test_me_endpoint_requires_authentication(self, api):
        response = api.get("/api/v1/users/me/")
        assert response.status_code == 401
        assert response.data["error"]["code"] == "not_authenticated"

    def test_me_endpoint_returns_profile(self, client_factory):
        user = UserFactory(first_name="Ada", last_name="Lovelace")
        client = client_factory(user)
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert response.data["full_name"] == "Ada Lovelace"
        assert response.data["mfa_enabled"] is False

    def test_me_patch_updates_own_profile(self, client_factory):
        user = UserFactory(first_name="Old")
        client = client_factory(user)
        response = client.patch("/api/v1/users/me/", {"first_name": "New"})
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "New"
        assert user.email == user.email  # email is not writable


class TestEmailVerificationGate:
    def test_unverified_user_cannot_log_in_when_required(self, api):
        user = UserFactory(is_verified=False)
        response = api.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        assert response.status_code == 403
        assert response.data["error"]["code"] == "email_not_verified"

    @override_settings(REQUIRE_EMAIL_VERIFICATION=False)
    def test_unverified_user_can_log_in_when_requirement_is_off(self, api):
        user = UserFactory(is_verified=False)
        response = api.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        assert response.status_code == 200
        assert "access" in response.data


class TestTokensAndRevocation:
    def test_refresh_rotates_refresh_token(self, client_factory):
        user = UserFactory()
        client = APIClient()
        login = client.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        refresh = login.data["refresh"]

        first = client.post("/api/v1/auth/token/refresh/", {"refresh": refresh})
        assert first.status_code == 200
        assert first.data["refresh"] != refresh

        reused = client.post("/api/v1/auth/token/refresh/", {"refresh": refresh})
        assert reused.status_code == 401

    def test_logout_all_revokes_access_and_refresh(self, client_factory):
        user = UserFactory()
        client = APIClient()
        login = client.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        access = login.data["access"]
        refresh = login.data["refresh"]

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me = client.get("/api/v1/users/me/")
        assert me.status_code == 200

        logout = client.post("/api/v1/auth/logout-all/")
        assert logout.status_code == 204

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        assert client.get("/api/v1/users/me/").status_code == 401
        assert (
            client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}).status_code
            == 401
        )

    def test_logout_blacklists_provided_refresh_token(self, client_factory):
        user = UserFactory()
        client = APIClient()
        login = client.post(
            LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
        )
        access, refresh = login.data["access"], login.data["refresh"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = client.post("/api/v1/auth/logout/", {"refresh": refresh})
        assert response.status_code == 204
        assert (
            client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}).status_code
            == 401
        )

    def test_disabling_account_revokes_existing_tokens(self, client_factory):
        user = UserFactory()
        client = client_factory(user)
        assert client.get("/api/v1/users/me/").status_code == 200

        user.is_active = False
        user.save(update_fields=["is_active"])
        assert client.get("/api/v1/users/me/").status_code == 401


class TestPasswordRecovery:
    def test_full_reset_flow(self, api, token_from_email):
        user = UserFactory(email="reset@example.test")
        response = api.post("/api/v1/auth/password/forgot/", {"email": user.email})
        assert response.status_code == 202
        assert len(mail.outbox) == 1

        token = token_from_email(mail.outbox[0].body)
        reset = api.post(
            "/api/v1/auth/password/reset/",
            {"token": token, "password": "BrandNew!Passw0rd"},
        )
        assert reset.status_code == 200, reset.data

        old = api.post(LOGIN_URL, {"email": user.email, "password": DEFAULT_TEST_PASSWORD})
        assert old.status_code == 401
        new = api.post(LOGIN_URL, {"email": user.email, "password": "BrandNew!Passw0rd"})
        assert new.status_code == 200

        reused = api.post(
            "/api/v1/auth/password/reset/",
            {"token": token, "password": "Another!Passw0rd"},
        )
        assert reused.status_code == 400

    def test_forgot_password_never_reveals_account_existence(self, api):
        response = api.post("/api/v1/auth/password/forgot/", {"email": "ghost@example.test"})
        assert response.status_code == 202
        assert len(mail.outbox) == 0
        known = UserFactory()
        response = api.post("/api/v1/auth/password/forgot/", {"email": known.email})
        assert response.status_code == 202
        assert response.data["message"] == (
            "If an account exists for this address, a reset link was sent."
        )


class TestLoginThrottling:
    def test_login_endpoint_throttles_after_rate_limit(self, api, monkeypatch):
        from django.core.cache import cache
        from rest_framework.throttling import ScopedRateThrottle

        with override_settings(
            CACHES={
                "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
            }
        ):
            monkeypatch.setattr(
                ScopedRateThrottle, "THROTTLE_RATES", {"login": "3/min"}, raising=False
            )
            cache.clear()
            user = UserFactory()
            payload = {"email": user.email, "password": DEFAULT_TEST_PASSWORD}
            statuses = [api.post(LOGIN_URL, payload).status_code for _ in range(4)]
            cache.clear()
        assert statuses[:3] == [200, 200, 200]
        assert statuses[3] == 429
