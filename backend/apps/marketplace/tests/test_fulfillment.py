from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from apps.marketplace import services
from apps.marketplace.models import (
    DisputeStatus,
    InventoryMovement,
    InventoryMovementReason,
    OrderStatus,
    PaymentStatus,
    RefundStatus,
)

EVIDENCE_URL = "/api/v1/marketplace/disputes/{pk}/evidence/"
RESOLVE_URL = "/api/v1/marketplace/disputes/{pk}/resolve/"


@pytest.mark.django_db
class TestShipping:
    def test_buyer_cannot_ship(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/ship/", {}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_ship_unpaid_order(
        self, sellable_product, buyer_user, verified_profile, client_factory
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order_id = checkout.data[0]["id"]
        supplier_client = client_factory(verified_profile.user)
        response = supplier_client.post(
            f"/api/v1/marketplace/orders/{order_id}/ship/", {}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "paid" in str(response.data)

    def test_supplier_ships_then_delivers(
        self, paid_order, supplier_user, client_factory
    ):
        client = client_factory(supplier_user)
        ship = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/ship/",
            {"tracking_number": "TRK-77"},
        )
        assert ship.status_code == status.HTTP_201_CREATED
        assert ship.data["status"] == "shipped"
        paid_order.refresh_from_db()
        assert paid_order.status == OrderStatus.SHIPPED

        deliver = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/deliver/"
        )
        assert deliver.status_code == status.HTTP_200_OK
        assert deliver.data["status"] == "delivered"
        paid_order.refresh_from_db()
        assert paid_order.status == OrderStatus.DELIVERED
        assert paid_order.shipment.tracking_number == "TRK-77"

    def test_cannot_deliver_before_shipping(
        self, paid_order, supplier_user, client_factory
    ):
        client = client_factory(supplier_user)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/deliver/"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_other_supplier_gets_404(self, paid_order, db, client_factory):
        from apps.accounts.models import RoleAssignment, UserRole
        from apps.accounts.tests.factories import UserFactory
        from apps.marketplace.models import SupplierProfile

        other = UserFactory()
        RoleAssignment.objects.create(user=other, role=UserRole.SUPPLIER)
        SupplierProfile.objects.create(
            user=other, company_name="Rival Co", contact_email=other.email
        )
        client = client_factory(other)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/ship/", {}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestRefunds:
    def test_buyer_requests_refund(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "Damaged item"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending"
        assert response.data["amount"] == "24000"

    def test_cannot_double_request(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "one"},
        )
        second = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "two"},
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_refund_pending_order(
        self, sellable_product, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        response = client.post(
            f"/api/v1/marketplace/orders/{checkout.data[0]['id']}/refund-request/",
            {"reason": "nope"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_buyer_cannot_decide(
        self, paid_order, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        refund = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "r"},
        ).data
        response = client.post(
            f"/api/v1/marketplace/refunds/{refund['id']}/decide/",
            {"approved": True},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_supplier_rejection_keeps_state(
        self, paid_order, buyer_user, supplier_user, client_factory, sellable_product
    ):
        buyer_client = client_factory(buyer_user)
        refund = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "r"},
        ).data
        supplier_client = client_factory(supplier_user)
        response = supplier_client.post(
            f"/api/v1/marketplace/refunds/{refund['id']}/decide/",
            {"approved": False, "reason": "outside window"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == RefundStatus.REJECTED
        paid_order.refresh_from_db()
        assert paid_order.status == OrderStatus.PAID

    def test_supplier_approval_settles_and_restocks(
        self, paid_order, buyer_user, supplier_user, client_factory, sellable_product
    ):
        buyer_client = client_factory(buyer_user)
        refund = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "wrong size"},
        ).data
        supplier_client = client_factory(supplier_user)
        response = supplier_client.post(
            f"/api/v1/marketplace/refunds/{refund['id']}/decide/",
            {"approved": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == RefundStatus.COMPLETED
        paid_order.refresh_from_db()
        sellable_product.refresh_from_db()
        assert paid_order.status == OrderStatus.REFUNDED
        payment = paid_order.payments.first()
        assert payment.status == PaymentStatus.REFUNDED
        # goods went back to the shelf
        assert sellable_product.available_quantity == 10
        assert InventoryMovement.objects.filter(
            product=sellable_product,
            reason=InventoryMovementReason.ADJUSTED,
            note="Refund restock",
        ).exists()

    def test_cannot_decide_twice(
        self, paid_order, buyer_user, supplier_user, client_factory
    ):
        buyer_client = client_factory(buyer_user)
        refund = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/refund-request/",
            {"reason": "r"},
        ).data
        supplier_client = client_factory(supplier_user)
        supplier_client.post(
            f"/api/v1/marketplace/refunds/{refund['id']}/decide/",
            {"approved": False},
        )
        again = supplier_client.post(
            f"/api/v1/marketplace/refunds/{refund['id']}/decide/",
            {"approved": True},
        )
        assert again.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestDisputes:
    def test_buyer_opens_dispute(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "Never arrived"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == DisputeStatus.OPEN

    def test_outsider_cannot_open(self, paid_order, db, client_factory):
        from apps.accounts.models import RoleAssignment, UserRole
        from apps.accounts.tests.factories import UserFactory

        outsider = UserFactory()
        RoleAssignment.objects.create(user=outsider, role=UserRole.BUYER)
        client = client_factory(outsider)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "not mine"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_one_dispute_only(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "first"},
        )
        second = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "second"},
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST

    def test_evidence_with_file(self, paid_order, buyer_user, client_factory):
        client = client_factory(buyer_user)
        dispute = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "broken"},
        ).data
        upload = SimpleUploadedFile("photo.png", b"\x89PNG\r\n\x1a\n fake")
        response = client.post(
            EVIDENCE_URL.format(pk=dispute["id"]),
            {"body": "see attached", "file": upload},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        # Django may append a random suffix when the name already exists
        assert response.data["file_name"].startswith("photo")
        assert response.data["file_name"].endswith(".png")
        assert response.data["body"] == "see attached"

        download = client.get(
            f"/api/v1/marketplace/disputes/{dispute['id']}/evidence/"
            f"{response.data['id']}/download/"
        )
        assert download.status_code == status.HTTP_200_OK
        assert "no-store" in download["Cache-Control"]
        assert download["Content-Disposition"].startswith("attachment")

    def test_outsider_cannot_add_evidence(
        self, paid_order, buyer_user, db, client_factory
    ):
        from apps.accounts.models import RoleAssignment, UserRole
        from apps.accounts.tests.factories import UserFactory

        buyer_client = client_factory(buyer_user)
        dispute = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "broken"},
        ).data
        outsider = UserFactory()
        RoleAssignment.objects.create(user=outsider, role=UserRole.BUYER)
        outsider_client = client_factory(outsider)
        response = outsider_client.post(
            EVIDENCE_URL.format(pk=dispute["id"]), {"body": "sneaking in"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_buyer_favored_resolution_refunds(
        self, paid_order, buyer_user, platform_admin, client_factory, sellable_product
    ):
        buyer_client = client_factory(buyer_user)
        dispute = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "never arrived"},
        ).data
        admin_client = client_factory(platform_admin)
        response = admin_client.post(
            RESOLVE_URL.format(pk=dispute["id"]),
            {"resolution": "buyer_favored", "note": "tracking shows nothing"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["resolution"] == "buyer_favored"
        paid_order.refresh_from_db()
        sellable_product.refresh_from_db()
        assert paid_order.status == OrderStatus.REFUNDED
        assert paid_order.refunds.filter(status=RefundStatus.COMPLETED).exists()
        assert sellable_product.available_quantity == 10

    def test_supplier_favored_resolution_keeps_payment(
        self, paid_order, buyer_user, platform_admin, client_factory
    ):
        buyer_client = client_factory(buyer_user)
        dispute = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "changed my mind"},
        ).data
        admin_client = client_factory(platform_admin)
        response = admin_client.post(
            RESOLVE_URL.format(pk=dispute["id"]),
            {"resolution": "supplier_favored"},
        )
        assert response.status_code == status.HTTP_200_OK
        paid_order.refresh_from_db()
        assert paid_order.status == OrderStatus.PAID
        assert not paid_order.refunds.exists()

    def test_buyer_cannot_resolve(self, paid_order, buyer_user, client_factory):
        buyer_client = client_factory(buyer_user)
        dispute = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "x"},
        ).data
        response = buyer_client.post(
            RESOLVE_URL.format(pk=dispute["id"]), {"resolution": "buyer_favored"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_evidence_closed_after_resolution(
        self, paid_order, buyer_user, platform_admin, client_factory
    ):
        buyer_client = client_factory(buyer_user)
        dispute = buyer_client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/dispute/",
            {"description": "x"},
        ).data
        admin_client = client_factory(platform_admin)
        admin_client.post(
            RESOLVE_URL.format(pk=dispute["id"]), {"resolution": "supplier_favored"}
        )
        response = buyer_client.post(
            EVIDENCE_URL.format(pk=dispute["id"]), {"body": "too late"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_dispute_list_is_admin_only(
        self, paid_order, buyer_user, platform_admin, client_factory
    ):
        buyer_client = client_factory(buyer_user)
        response = buyer_client.get("/api/v1/marketplace/disputes/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        admin_client = client_factory(platform_admin)
        response = admin_client.get("/api/v1/marketplace/disputes/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestOrderDetailEmbeds:
    def test_paid_order_shows_payments_and_state(
        self, paid_order, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        response = client.get(f"/api/v1/marketplace/orders/{paid_order.pk}/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["payments"]) == 1
        assert response.data["payments"][0]["status"] == "succeeded"
        assert response.data["payments"][0]["events"]
        assert response.data["shipment"] is None
        assert response.data["dispute"] is None

    def test_services_layer_ship_guard(self, paid_order, buyer_user):
        from rest_framework import exceptions

        with pytest.raises(exceptions.PermissionDenied):
            services.ship_order(paid_order, actor=buyer_user)
