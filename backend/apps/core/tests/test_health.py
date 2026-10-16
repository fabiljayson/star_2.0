import pytest

pytestmark = pytest.mark.django_db


def test_health_reports_database_status(api):
    response = api.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["checks"]["database"] == "ok"


def test_openapi_schema_is_served(api):
    response = api.get("/api/v1/schema/")
    assert response.status_code == 200
    assert b"openapi" in response.content or b"swagger" in response.content


def test_swagger_ui_is_served(api):
    response = api.get("/api/v1/docs/")
    assert response.status_code == 200
