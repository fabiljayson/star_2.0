from __future__ import annotations

import csv
import io

import pytest
from rest_framework import status

REPORTS_URL = "/api/v1/reports/"


@pytest.mark.django_db
class TestMarketplaceReports:
    def test_supplier_sales_report(self, paid_order, supplier_user, client_factory):
        client = client_factory(supplier_user)
        response = client.post(
            REPORTS_URL,
            {"report_type": "supplier_sales", "format": "csv", "parameters": {}},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "succeeded"
        assert response.data["institution"] is None
        assert response.data["row_count"] >= 1
        assert response.data["artifact_name"].startswith("supplier_sales-")

        download = client.get(f"/api/v1/reports/{response.data['id']}/download/")
        assert download.status_code == status.HTTP_200_OK
        content = b"".join(download.streaming_content).decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(content)))
        assert any(paid_order.reference in cell for row in rows for cell in row)

    def test_supplier_sales_scoped_to_own_profile(
        self, paid_order, supplier_user, platform_admin, db, client_factory
    ):
        from apps.accounts.models import RoleAssignment, UserRole
        from apps.accounts.tests.factories import UserFactory
        from apps.marketplace.models import SupplierProfile

        rival = UserFactory()
        RoleAssignment.objects.create(user=rival, role=UserRole.SUPPLIER)
        rival_profile = SupplierProfile.objects.create(
            user=rival, company_name="Rival Co", contact_email=rival.email
        )
        client = client_factory(supplier_user)
        response = client.post(
            REPORTS_URL,
            {
                "report_type": "supplier_sales",
                "format": "csv",
                "parameters": {"target_supplier": str(rival_profile.pk)},
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        admin_client = client_factory(platform_admin)
        response = admin_client.post(
            REPORTS_URL,
            {
                "report_type": "supplier_sales",
                "format": "csv",
                "parameters": {"target_supplier": str(paid_order.supplier_id)},
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["row_count"] >= 1

    def test_buyer_orders_report(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            REPORTS_URL,
            {"report_type": "buyer_orders", "format": "pdf", "parameters": {}},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "succeeded"
        assert response.data["row_count"] >= 1

        download = client.get(f"/api/v1/reports/{response.data['id']}/download/")
        assert download.status_code == status.HTTP_200_OK
        assert download["Content-Type"] == "application/pdf"
        assert b"%PDF" in next(download.streaming_content)[:8]

    def test_marketplace_summary_admin_only(
        self, paid_order, platform_admin, buyer_user, client_factory
    ):
        buyer_client = client_factory(buyer_user)
        denied = buyer_client.post(
            REPORTS_URL,
            {"report_type": "marketplace_summary", "format": "csv"},
        )
        assert denied.status_code == status.HTTP_403_FORBIDDEN

        admin_client = client_factory(platform_admin)
        response = admin_client.post(
            REPORTS_URL, {"report_type": "marketplace_summary", "format": "csv"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["row_count"] >= 1

    def test_supplier_cannot_request_buyer_orders(
        self, paid_order, supplier_user, client_factory
    ):
        client = client_factory(supplier_user)
        response = client.post(
            REPORTS_URL,
            {"report_type": "buyer_orders", "format": "csv"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_clinical_report_still_requires_institution(
        self, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        response = client.post(
            REPORTS_URL,
            {"report_type": "activity_by_date", "format": "csv", "parameters": {}},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "institution" in str(response.data)

    def test_marketplace_report_ignores_institution(
        self, paid_order, supplier_user, db, client_factory
    ):
        from apps.organizations.models import Institution

        institution = Institution.objects.create(name="Some Hospital")
        client = client_factory(supplier_user)
        response = client.post(
            REPORTS_URL,
            {
                "report_type": "supplier_sales",
                "format": "csv",
                "institution": str(institution.pk),
            },
        )
        # marketplace reports never attach to an institution
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["institution"] is None
