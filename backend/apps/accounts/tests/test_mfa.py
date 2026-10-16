import pyotp
import pytest

from .factories import DEFAULT_TEST_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def _login(client, user, password=DEFAULT_TEST_PASSWORD):
    return client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": password}
    )


class TestMFALifecycle:
    def test_setup_enable_login_and_disable(self, api, client_factory):
        user = UserFactory(email="mfa@example.test")
        client = client_factory(user)

        setup = client.post("/api/v1/auth/mfa/setup/")
        assert setup.status_code == 200, setup.data
        secret = setup.data["secret"]
        assert "otpauth" in setup.data["otpauth_url"]

        code = pyotp.TOTP(secret).now()
        enable = client.post("/api/v1/auth/mfa/enable/", {"code": code})
        assert enable.status_code == 200, enable.data
        user.refresh_from_db()
        assert user.mfa_enabled is True

        fresh = UserFactory()
        login = _login(api, fresh)
        assert login.status_code == 200
        assert login.data["mfa_required"] is False  # fresh user has no MFA

        mfa_login = _login(api, user)
        assert mfa_login.status_code == 200
        assert mfa_login.data["mfa_required"] is True
        mfa_token = mfa_login.data["mfa_token"]

        bad = api.post(
            "/api/v1/auth/mfa/verify/", {"mfa_token": mfa_token, "code": "000000"}
        )
        assert bad.status_code == 401

        good = api.post(
            "/api/v1/auth/mfa/verify/",
            {"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()},
        )
        assert good.status_code == 200, good.data
        assert "access" in good.data
        assert good.data["user"]["mfa_enabled"] is True

        # Same MFA session cannot be replayed.
        replay = api.post(
            "/api/v1/auth/mfa/verify/",
            {"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()},
        )
        assert replay.status_code == 400

        # Disable requires a valid code as well.
        disable_bad = client.post("/api/v1/auth/mfa/disable/", {"code": "000000"})
        assert disable_bad.status_code == 401
        disable = client.post(
            "/api/v1/auth/mfa/disable/", {"code": pyotp.TOTP(secret).now()}
        )
        assert disable.status_code == 200
        user.refresh_from_db()
        assert user.mfa_enabled is False
        assert user.mfa_secret == ""

    def test_enable_requires_valid_code(self, client_factory):
        user = UserFactory()
        client = client_factory(user)
        setup = client.post("/api/v1/auth/mfa/setup/")
        response = client.post("/api/v1/auth/mfa/enable/", {"code": "111111"})
        assert response.status_code == 401
        user.refresh_from_db()
        assert user.mfa_enabled is False
        assert setup.status_code == 200


class TestPlatformAdminMFAPolicy:
    def test_policy_blocks_platform_admin_without_mfa(self, client_factory, settings):
        settings.REQUIRE_MFA_FOR_PLATFORM_ADMINS = True
        admin = UserFactory(is_platform_admin=True, email="root@example.test")
        client = client_factory(admin)

        response = client.get("/api/v1/audit/")
        assert response.status_code == 403
        assert response.data["error"]["code"] == "mfa_required"

        setup = client.post("/api/v1/auth/mfa/setup/")
        secret = setup.data["secret"]
        client.post("/api/v1/auth/mfa/enable/", {"code": pyotp.TOTP(secret).now()})

        allowed = client.get("/api/v1/audit/")
        assert allowed.status_code == 200
