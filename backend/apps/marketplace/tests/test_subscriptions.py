from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import exceptions, status

from apps.accounts.tests.factories import UserFactory
from apps.marketplace import payments, subscriptions
from apps.marketplace.models import (
    PaymentEventType,
    ProductCategory,
    SellerSubscription,
    SubscriptionStatus,
)


# ── Helpers ────────────────────────────────────────────────────────────
def _checkout(client, plan):
    return client.post(
        "/api/v1/marketplace/subscription/checkout/", {"plan": plan}
    )


def _activate(payment):
    return payments.simulate_payment(payment, outcome="succeeded")


def _error_code(response) -> str:
    return response.data.get("error", {}).get("code", "")


def _category(name: str) -> ProductCategory:
    return ProductCategory.objects.create(name=name, slug=name.lower().replace(" ", "-"))


@pytest.fixture
def supplier_with_subscription(verified_profile):
    return verified_profile.user


# ── Permission to publish ─────────────────────────────────────────────
@pytest.mark.django_db
class TestPublicationPermission:
    def test_supplier_without_subscription_cannot_create_product(
        self, supplier_user, verified_profile, client_factory, db
    ):
        SellerSubscription.objects.filter(user=supplier_user).delete()
        client = client_factory(supplier_user)
        category = _category("No Sub Cat")
        response = client.post(
            "/api/v1/marketplace/supplier/products/",
            {
                "category": str(category.pk),
                "name": "Forceps",
                "sku": "NS-1",
                "unit_price": "5000",
                "available_quantity": 3,
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert _error_code(response) == "seller_subscription_required"

    def test_supplier_with_subscription_can_create_product(
        self, supplier_with_subscription, client_factory, db
    ):
        client = client_factory(supplier_with_subscription)
        category = _category("Sub Cat")
        response = client.post(
            "/api/v1/marketplace/supplier/products/",
            {
                "category": str(category.pk),
                "name": "Forceps",
                "sku": "WS-1",
                "unit_price": "5000",
                "available_quantity": 3,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_expired_subscription_blocks_republishing(
        self, verified_profile, client_factory, db
    ):
        category = _category("Expired Cat")
        product = verified_profile.products.create(
            category=category,
            name="Forceps",
            sku="EXP-1",
            unit_price=Decimal("5000"),
            available_quantity=3,
        )
        SellerSubscription.objects.filter(
            user=verified_profile.user
        ).update(
            status=SubscriptionStatus.EXPIRED,
            expires_at=timezone.now() - timedelta(days=1),
        )
        client = client_factory(verified_profile.user)
        response = client.patch(
            f"/api/v1/marketplace/supplier/products/{product.pk}/",
            {"is_published": True},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        product.refresh_from_db()
        assert not product.is_published

    def test_cannot_view_public_product_of_expired_supplier(
        self, sellable_product, client_factory, db
    ):
        product_pk = sellable_product.pk
        SellerSubscription.objects.filter(
            user=sellable_product.supplier.user
        ).update(
            status=SubscriptionStatus.EXPIRED,
            expires_at=timezone.now() - timedelta(days=1),
        )
        client = client_factory(UserFactory())
        assert (
            client.get(f"/api/v1/marketplace/products/{product_pk}/").status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert client.get("/api/v1/marketplace/products/").data["count"] == 0
        # The owner still sees it in their private catalog.
        owner = client_factory(sellable_product.supplier.user)
        own = owner.get("/api/v1/marketplace/supplier/products/")
        assert own.status_code == status.HTTP_200_OK
        assert own.data["count"] == 1

    def test_renewal_restores_catalog_visibility(
        self, sellable_product, client_factory, db
    ):
        supplier_user = sellable_product.supplier.user
        SellerSubscription.objects.filter(user=supplier_user).update(
            status=SubscriptionStatus.EXPIRED,
            expires_at=timezone.now() - timedelta(days=1),
        )

        def anon():
            return client_factory(UserFactory())

        assert (
            anon().get(f"/api/v1/marketplace/products/{sellable_product.pk}/").status_code
            == status.HTTP_404_NOT_FOUND
        )
        client = client_factory(supplier_user)
        response = _checkout(client, "monthly")
        assert response.status_code == status.HTTP_201_CREATED, response.data
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        assert (
            anon().get(f"/api/v1/marketplace/products/{sellable_product.pk}/").status_code
            == status.HTTP_200_OK
        )


# ── Checkout pricing ──────────────────────────────────────────────────
@pytest.mark.django_db
class TestCheckoutPricing:
    def test_first_month_price_applies_once(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        first = _checkout(client, "monthly")
        assert first.status_code == status.HTTP_201_CREATED, first.data
        assert first.data["amount"] == "2500"
        payments.simulate_payment(
            SellerSubscription.objects.latest("created_at").payments.first(),
            outcome="succeeded",
        )
        second = _checkout(client, "monthly")
        # Renewing while still active: full price, no second welcome offer.
        assert second.data["amount"] == "5000"

    def test_welcome_price_never_applies_to_longer_plans(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        response = _checkout(client, "annual")
        assert response.data["amount"] == "12000"

    def test_unknown_plan_rejected(self, supplier_user, client_factory, db):
        client = client_factory(supplier_user)
        response = client.post(
            "/api/v1/marketplace/subscription/checkout/",
            {"plan": "yearly"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_cannot_override_amount(self, supplier_user, client_factory, db):
        client = client_factory(supplier_user)
        response = client.post(
            "/api/v1/marketplace/subscription/checkout/",
            {"plan": "monthly", "amount": "1", "expires_at": "1999-01-01T00:00:00Z"},
        )
        if response.status_code == status.HTTP_201_CREATED:
            # Even after retrying a second attempt, the price is server-set.
            assert response.data["amount"] == "2500"
        else:
            # Unknown fields are rejected outright.
            assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── Lifecycle ─────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestLifecycle:
    def test_pending_grants_no_publish_rights(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        payload = client.get("/api/v1/marketplace/subscription/").data
        assert payload["status"] == "pending"
        assert payload["can_publish"] is False
        assert payload["remaining_seconds"] == 0

    def test_verified_payment_activates_one_calendar_month(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        payload = client.get("/api/v1/marketplace/subscription/").data
        assert payload["status"] == "active"
        assert payload["can_publish"] is True
        assert 2_400_000 < payload["remaining_seconds"] <= 2_700_000

    def test_failed_payment_grants_nothing(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        payments.simulate_payment(
            SellerSubscription.objects.latest("created_at").payments.first(),
            outcome="failed",
        )
        payload = client.get("/api/v1/marketplace/subscription/").data
        assert payload["status"] == "failed"
        assert payload["renewal_available"] is True

    def test_renewal_while_active_preserves_remaining_time(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        first = SellerSubscription.objects.filter(
            user=supplier_user, status=SubscriptionStatus.ACTIVE
        ).order_by("-expires_at").first()
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        first.refresh_from_db()
        renewed = SellerSubscription.objects.filter(
            user=supplier_user, status=SubscriptionStatus.ACTIVE
        ).order_by("-expires_at").first()
        assert renewed.pk != first.pk
        assert first.status == SubscriptionStatus.RENEWED
        expected = subscriptions.add_calendar_months(first.expires_at, 1)
        assert renewed.expires_at == expected

    def test_renewal_after_expiry_starts_now(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        expired_at = timezone.now() - timedelta(days=2)
        SellerSubscription.objects.filter(user=supplier_user).update(
            status=SubscriptionStatus.EXPIRED, expires_at=expired_at
        )
        before = timezone.now()
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        latest = SellerSubscription.objects.latest("created_at")
        assert latest.status == SubscriptionStatus.ACTIVE
        assert latest.starts_at >= before
        expected = subscriptions.add_calendar_months(latest.starts_at, 1)
        assert latest.expires_at == expected

    def test_duplicate_webhook_activates_only_once(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        payment = SellerSubscription.objects.latest("created_at").payments.first()
        payments.simulate_payment(payment, outcome="succeeded")
        # Replaying the verified webhook by reference, signed properly.
        payload = {
            "provider_reference": payment.provider_reference,
            "subscription_reference": payment.subscription.reference,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "outcome": "succeeded",
        }
        payments.apply_webhook(payload, payments.sign_payload(payload), request=None)
        event_types = list(payment.events.values_list("event_type", flat=True))
        assert event_types.count(PaymentEventType.DUPLICATE_IGNORED) == 1
        assert event_types.count(PaymentEventType.SUCCEEDED) == 1
        assert (
            SellerSubscription.objects.filter(
                user=supplier_user, status=SubscriptionStatus.ACTIVE
            ).count()
            == 1
        )

    def test_active_row_with_lapsed_timestamp_grants_nothing(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        SellerSubscription.objects.filter(user=supplier_user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        payload = client.get("/api/v1/marketplace/subscription/").data
        assert payload["can_publish"] is False
        assert payload["status"] == "expired"

    def test_command_expires_and_cancels(self, supplier_user, client_factory, db):
        from django.core.management import call_command

        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        _activate(SellerSubscription.objects.latest("created_at").payments.first())
        SellerSubscription.objects.filter(user=supplier_user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        call_command("expire_marketplace_subscriptions")
        row = SellerSubscription.objects.latest("created_at")
        assert row.status == SubscriptionStatus.EXPIRED

        _checkout(client, "monthly")
        stale = SellerSubscription.objects.filter(
            user=supplier_user, status=SubscriptionStatus.PENDING
        ).latest("created_at")
        SellerSubscription.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        call_command("expire_marketplace_subscriptions")
        stale.refresh_from_db()
        assert stale.status == SubscriptionStatus.CANCELLED

    def test_calendar_month_clamps_short_months(self, db):
        from datetime import datetime as dt
        from zoneinfo import ZoneInfo

        start = dt(2027, 1, 31, 12, 0, tzinfo=ZoneInfo("UTC"))
        assert subscriptions.add_calendar_months(start, 1).month == 2
        assert subscriptions.add_calendar_months(start, 1).day == 28


# ── Security & ownership ──────────────────────────────────────────────
@pytest.mark.django_db
class TestSubscriptionSecurity:
    def test_other_user_cannot_see_subscription_payment(
        self, supplier_user, buyer_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        payment_pk = SellerSubscription.objects.latest("created_at").payments.first().pk
        intruder = client_factory(buyer_user)
        assert (
            intruder.get(
                f"/api/v1/marketplace/subscription/payments/{payment_pk}/"
            ).status_code
            == status.HTTP_404_NOT_FOUND
        )

    def test_invalid_webhook_signature_rejected(
        self, supplier_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        payment = SellerSubscription.objects.latest("created_at").payments.first()
        payload = {
            "provider_reference": "MOCK-x",
            "subscription_reference": payment.subscription.reference,
            "amount": "2500",
            "currency": "XOF",
            "outcome": "succeeded",
        }
        with pytest.raises(exceptions.ValidationError):
            payments.apply_webhook(payload, "deadbeef", request=None)

    def test_amount_mismatch_rejected(self, supplier_user, client_factory, db):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        payment = SellerSubscription.objects.latest("created_at").payments.first()
        payload = {
            "provider_reference": "MOCK-y",
            "subscription_reference": payment.subscription.reference,
            "amount": "100",
            "currency": "XOF",
            "outcome": "succeeded",
        }
        with pytest.raises(exceptions.ValidationError):
            payments.apply_webhook(payload, payments.sign_payload(payload))

    def test_subscription_history_scoped_to_owner(
        self, supplier_user, buyer_user, client_factory, db
    ):
        client = client_factory(supplier_user)
        _checkout(client, "monthly")
        stranger = client_factory(buyer_user)
        assert stranger.get("/api/v1/marketplace/subscription/history/").data == []
        history = client.get("/api/v1/marketplace/subscription/history/").data
        assert len(history) == 1
