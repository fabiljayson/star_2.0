import re

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import DEFAULT_TEST_PASSWORD


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def client_factory():
    """Build an APIClient, optionally authenticated as a given user."""

    def _make(user=None, password: str | None = None) -> APIClient:
        client = APIClient()
        if user is not None:
            response = client.post(
                "/api/v1/auth/login/",
                {"email": user.email, "password": password or DEFAULT_TEST_PASSWORD},
            )
            assert response.status_code == 200, response.data
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return client

    return _make


@pytest.fixture
def token_from_email():
    """Extract the single action token from the latest captured email."""

    def _extract(mail_body: str) -> str:
        match = re.search(r"token=([A-Za-z0-9_\-]+)", mail_body)
        assert match, f"No token found in mail body: {mail_body}"
        return match.group(1)

    return _extract
