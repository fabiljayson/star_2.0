from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import RoleAssignment, UserRole
from apps.accounts.tests.factories import PlatformAdminFactory, UserFactory
from apps.marketplace import services
from apps.marketplace.models import (
    Order,
    Product,
    ProductCategory,
    SellerSubscription,
    SubscriptionStatus,
    SupplierProfile,
)


@pytest.fixture
def supplier_user(db):
    user = UserFactory()
    RoleAssignment.objects.create(user=user, role=UserRole.SUPPLIER)
    return user


@pytest.fixture
def buyer_user(db):
    user = UserFactory()
    RoleAssignment.objects.create(user=user, role=UserRole.BUYER)
    return user


@pytest.fixture
def platform_admin(db):
    return PlatformAdminFactory()


@pytest.fixture
def supplier_subscription(supplier_user, db):
    """An active monthly subscription for the supplier user."""
    return SellerSubscription.objects.create(
        user=supplier_user,
        plan="monthly",
        status=SubscriptionStatus.ACTIVE,
        amount=Decimal("5000"),
        currency="XOF",
        starts_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=29),
    )


@pytest.fixture
def verified_profile(supplier_user, platform_admin, supplier_subscription):
    profile = SupplierProfile.objects.create(
        user=supplier_user,
        company_name="Acme Surgical",
        contact_email=supplier_user.email,
    )
    services.verify_supplier(platform_admin, profile, approve=True)
    return profile


@pytest.fixture
def sellable_product(verified_profile):
    category = ProductCategory.objects.create(name="Forceps", slug="forceps")
    product = Product.objects.create(
        supplier=verified_profile,
        category=category,
        name="Demo Forceps",
        description="Test product",
        sku="TEST-FP-001",
        unit_price=Decimal("12000"),
        available_quantity=10,
        approval_status="approved",
        is_published=True,
    )
    return product


@pytest.fixture
def paid_order(sellable_product, buyer_user, client_factory):
    """A checkout that went through a successful sandbox payment."""
    from apps.marketplace import payments

    client = client_factory(buyer_user)
    client.post(
        "/api/v1/marketplace/cart/items/",
        {"product": str(sellable_product.pk), "quantity": 2},
    )
    response = client.post("/api/v1/marketplace/checkout/", {})
    assert response.status_code == 201, response.data
    order = Order.objects.get(pk=response.data[0]["id"])
    payment, _ = payments.initiate_payment(order, buyer=buyer_user)
    payments.simulate_payment(payment, outcome="succeeded")
    order.refresh_from_db()
    assert order.status == "paid"
    return order


@pytest.fixture
def pending_payment_order(sellable_product, buyer_user, client_factory):
    """A checkout whose payment attempt is open but not settled yet."""
    from apps.marketplace import payments as marketplace_payments

    client = client_factory(buyer_user)
    client.post(
        "/api/v1/marketplace/cart/items/",
        {"product": str(sellable_product.pk), "quantity": 2},
    )
    response = client.post("/api/v1/marketplace/checkout/", {})
    assert response.status_code == 201, response.data
    order = Order.objects.get(pk=response.data[0]["id"])
    payment, _ = marketplace_payments.initiate_payment(order, buyer=buyer_user)
    assert payment.status == "pending"
    return order
