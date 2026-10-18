from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework import status

from apps.accounts.models import RoleAssignment, UserRole
from apps.accounts.tests.factories import UserFactory
from apps.marketplace import services
from apps.marketplace.models import (
    InventoryMovement,
    InventoryMovementReason,
    Order,
    Product,
    ProductCategory,
    SupplierProfile,
)


@pytest.mark.django_db
class TestCatalogVisibility:
    def test_approved_published_product_visible_to_authenticated_user(
        self, sellable_product, client_factory, db
    ):
        client = client_factory(UserFactory())
        response = client.get("/api/v1/marketplace/products/")
        assert response.status_code == status.HTTP_200_OK
        names = [p["name"] for p in response.data["results"]]
        assert "Demo Forceps" in names

    def test_draft_product_not_visible(self, verified_profile, client_factory, db):
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        Product.objects.create(
            supplier=verified_profile,
            category=category,
            name="Secret Draft",
            sku="SECRET-1",
            unit_price=Decimal("5000"),
            available_quantity=10,
            approval_status="pending",
            is_published=True,
        )
        client = client_factory(UserFactory())
        response = client.get("/api/v1/marketplace/products/")
        names = [p["name"] for p in response.data["results"]]
        assert "Secret Draft" not in names

    def test_unpublished_product_not_visible(self, verified_profile, client_factory, db):
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        Product.objects.create(
            supplier=verified_profile,
            category=category,
            name="Hidden",
            sku="HIDDEN-1",
            unit_price=Decimal("5000"),
            available_quantity=10,
            approval_status="approved",
            is_published=False,
        )
        client = client_factory(UserFactory())
        response = client.get("/api/v1/marketplace/products/")
        names = [p["name"] for p in response.data["results"]]
        assert "Hidden" not in names

    def test_unverified_supplier_product_not_visible(self, supplier_user, db, client_factory):
        profile = SupplierProfile.objects.create(
            user=supplier_user, company_name="Pending Co", contact_email=supplier_user.email
        )
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        Product.objects.create(
            supplier=profile,
            category=category,
            name="Pending Product",
            sku="PEND-1",
            unit_price=Decimal("5000"),
            available_quantity=10,
            approval_status="approved",
            is_published=True,
        )
        client = client_factory(UserFactory())
        response = client.get("/api/v1/marketplace/products/")
        names = [p["name"] for p in response.data["results"]]
        assert "Pending Product" not in names


@pytest.mark.django_db
class TestSupplierProfile:
    def test_register_profile(self, supplier_user, client_factory):
        client = client_factory(supplier_user)
        response = client.post(
            "/api/v1/marketplace/supplier/profile/",
            {"company_name": "Acme", "contact_email": "a@b.test"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["verification_status"] == "pending"

    def test_cannot_register_profile_as_buyer(self, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            "/api/v1/marketplace/supplier/profile/",
            {"company_name": "Nope"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_profile(self, verified_profile, client_factory):
        client = client_factory(verified_profile.user)
        response = client.patch(
            "/api/v1/marketplace/supplier/profile/",
            {"contact_phone": "+22990000000"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["contact_phone"] == "+22990000000"


@pytest.mark.django_db
class TestSupplierCatalog:
    def test_supplier_can_create_product_pending_approval(self, verified_profile, client_factory):
        client = client_factory(verified_profile.user)
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        response = client.post(
            "/api/v1/marketplace/supplier/products/",
            {
                "category": str(category.pk),
                "name": "New Tube",
                "sku": "NEW-1",
                "unit_price": "3000",
                "available_quantity": 5,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["approval_status"] == "pending"

    def test_non_supplier_cannot_create_product(self, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            "/api/v1/marketplace/supplier/products/",
            {"name": "X", "sku": "X", "unit_price": "1000", "available_quantity": 1},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_restock_increases_stock_and_logs_movement(
        self, verified_profile, client_factory
    ):
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        product = Product.objects.create(
            supplier=verified_profile,
            category=category,
            name="Tube",
            sku="REST-1",
            unit_price=Decimal("1000"),
            available_quantity=5,
            approval_status="approved",
            is_published=True,
        )
        client = client_factory(verified_profile.user)
        response = client.post(
            f"/api/v1/marketplace/supplier/products/{product.pk}/restock/",
            {"quantity": 20},
        )
        assert response.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.available_quantity == 25
        assert InventoryMovement.objects.filter(
            product=product, reason=InventoryMovementReason.RESTOCKED, delta=20
        ).exists()


@pytest.mark.django_db
class TestAdminVerification:
    def test_admin_can_verify_supplier(
        self, supplier_user, platform_admin, client_factory
    ):
        profile = SupplierProfile.objects.create(
            user=supplier_user, company_name="Pending", contact_email=supplier_user.email
        )
        client = client_factory(platform_admin)
        response = client.post(f"/api/v1/marketplace/admin/suppliers/{profile.pk}/verify/")
        assert response.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_verified

    def test_buyer_cannot_verify_supplier(
        self, supplier_user, buyer_user, client_factory
    ):
        profile = SupplierProfile.objects.create(
            user=supplier_user, company_name="Pending", contact_email=supplier_user.email
        )
        client = client_factory(buyer_user)
        response = client.post(f"/api/v1/marketplace/admin/suppliers/{profile.pk}/verify/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_approve_product(
        self, verified_profile, platform_admin, client_factory
    ):
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        product = Product.objects.create(
            supplier=verified_profile,
            category=category,
            name="Draft",
            sku="APPR-1",
            unit_price=Decimal("1000"),
            available_quantity=5,
            approval_status="draft",
        )
        client = client_factory(platform_admin)
        response = client.post(
            f"/api/v1/marketplace/admin/products/{product.pk}/approve/"
        )
        assert response.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.approval_status == "approved"


@pytest.mark.django_db
class TestCartCheckout:
    def test_buyer_can_add_to_cart_and_checkout(
        self, sellable_product, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        response = client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 3},
        )
        assert response.status_code == status.HTTP_201_CREATED
        response = client.post(
            "/api/v1/marketplace/checkout/",
            {"shipping": {"name": "HQ", "address": "Cotonou"}},
        )
        assert response.status_code == status.HTTP_201_CREATED
        order = response.data[0]
        assert order["status"] == "pending_payment"
        assert order["subtotal"] == "36000"
        assert order["total"] == "36000"
        sellable_product.refresh_from_db()
        assert sellable_product.reserved_quantity == 3
        assert sellable_product.free_quantity == 7
        assert InventoryMovement.objects.filter(
            product=sellable_product,
            reason=InventoryMovementReason.RESERVED,
            delta=3,
        ).exists()

    def test_supplier_cannot_checkout(self, sellable_product, supplier_user, client_factory):
        client = client_factory(supplier_user)
        response = client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_oversell_is_rejected(self, sellable_product, buyer_user, client_factory):
        client = client_factory(buyer_user)
        response = client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 50},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_order_item_snapshots_product(
        self, sellable_product, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        response = client.post("/api/v1/marketplace/checkout/", {})
        order_id = response.data[0]["id"]
        sellable_product.name = "Renamed after order"
        sellable_product.unit_price = Decimal("99999")
        sellable_product.save()
        detail = client.get(f"/api/v1/marketplace/orders/{order_id}/")
        item = detail.data["items"][0]
        assert item["product_name"] == "Demo Forceps"
        assert item["unit_price"] == "12000"

    def test_multi_supplier_checkout_creates_multiple_orders(
        self, sellable_product, verified_profile, db, buyer_user, client_factory
    ):
        category = ProductCategory.objects.create(name="Tubes", slug="tubes")
        other_profile = SupplierProfile.objects.create(
            user=UserFactory(email="other.supplier@example.test"),
            company_name="Other Co",
            contact_email="other.supplier@example.test",
        )
        services.verify_supplier(
            UserFactory(is_platform_admin=True), other_profile, approve=True
        )
        other_product = Product.objects.create(
            supplier=other_profile,
            category=category,
            name="Other Tube",
            sku="OT-1",
            unit_price=Decimal("2000"),
            available_quantity=5,
            approval_status="approved",
            is_published=True,
        )
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(other_product.pk), "quantity": 2},
        )
        response = client.post("/api/v1/marketplace/checkout/", {})
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2
        assert Order.objects.filter(buyer=buyer_user).count() == 2

    def test_cancel_order_releases_reservation(
        self, sellable_product, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 2},
        )
        response = client.post("/api/v1/marketplace/checkout/", {})
        order_id = response.data[0]["id"]
        sellable_product.refresh_from_db()
        assert sellable_product.reserved_quantity == 2

        response = client.post(
            f"/api/v1/marketplace/orders/{order_id}/cancel/", {"reason": "changed mind"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "cancelled"
        sellable_product.refresh_from_db()
        assert sellable_product.reserved_quantity == 0
        assert InventoryMovement.objects.filter(
            product=sellable_product,
            reason=InventoryMovementReason.RELEASED,
            delta=-2,
        ).exists()

    def test_buyer_sees_own_orders_only(self, sellable_product, buyer_user, db, client_factory):
        other_buyer = UserFactory(email="other.buyer@example.test")
        RoleAssignment.objects.create(user=other_buyer, role=UserRole.BUYER)
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        client.post("/api/v1/marketplace/checkout/", {})

        other_client = client_factory(other_buyer)
        response = other_client.get("/api/v1/marketplace/orders/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
