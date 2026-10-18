from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from apps.marketplace import payments, services
from apps.marketplace.models import (
    InventoryMovement,
    InventoryMovementReason,
    Payment,
    PaymentEvent,
    PaymentEventType,
    PaymentStatus,
)

WEBHOOK_URL = "/api/v1/marketplace/payments/webhook/"


def _sign(payload: dict) -> str:
    return payments.sign_payload(payload)


def _payload(order, payment, *, outcome="succeeded", amount=None, provider_ref=None):
    return {
        "provider_reference": provider_ref or f"MOCK-{'a' * 32}",
        "order_reference": order.reference,
        "amount": str(amount if amount is not None else payment.amount),
        "currency": payment.currency,
        "outcome": outcome,
        "timestamp": "2026-10-18T00:00:00+00:00",
    }


@pytest.mark.django_db
class TestInitiation:
    def test_buyer_initiates_payment(
        self, sellable_product, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order_id = checkout.data[0]["id"]
        response = client.post(
            f"/api/v1/marketplace/orders/{order_id}/pay/",
            {},
            headers={"Idempotency-Key": "key-123"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending"
        assert response.data["amount"] == "12000"
        assert response.data["idempotency_key"] == "key-123"

    def test_cannot_pay_settled_order(
        self, paid_order, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        first = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/pay/",
            {},
            headers={"Idempotency-Key": "same-key"},
        )
        # paid_order already settled → a new attempt is not allowed at all
        assert first.status_code == status.HTTP_400_BAD_REQUEST

    def test_pending_payment_is_reused_without_key(
        self, sellable_product, buyer_user, client_factory
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order_id = checkout.data[0]["id"]
        first = client.post(f"/api/v1/marketplace/orders/{order_id}/pay/", {})
        second = client.post(f"/api/v1/marketplace/orders/{order_id}/pay/", {})
        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_200_OK
        assert first.data["id"] == second.data["id"]
        assert Payment.objects.filter(order_id=order_id).count() == 1

    def test_supplier_cannot_pay(self, paid_order, supplier_user, client_factory):
        client = client_factory(supplier_user)
        response = client.post(
            f"/api/v1/marketplace/orders/{paid_order.pk}/pay/", {}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_stale_order_auto_expires_and_releases_stock(
        self, sellable_product, buyer_user, client_factory, db
    ):
        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 4},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order_id = checkout.data[0]["id"]

        from apps.marketplace.models import Order

        order = Order.objects.get(pk=order_id)
        order.placed_at = timezone.now() - timedelta(hours=25)
        order.save(update_fields=["placed_at"])

        response = client.post(f"/api/v1/marketplace/orders/{order_id}/pay/", {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        order.refresh_from_db()
        sellable_product.refresh_from_db()
        assert order.status == "cancelled"
        assert order.cancel_reason == "Payment window expired"
        assert sellable_product.reserved_quantity == 0
        assert InventoryMovement.objects.filter(
            product=sellable_product, reason=InventoryMovementReason.RELEASED
        ).exists()


@pytest.mark.django_db
class TestWebhook:
    def test_invalid_signature_rejected(self, pending_payment_order, api):
        payment = pending_payment_order.payments.first()
        payload = _payload(pending_payment_order, payment)
        response = api.post(
            WEBHOOK_URL, payload, format="json", HTTP_X_PAYMENT_SIGNATURE="deadbeef"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PENDING
        assert PaymentEvent.objects.filter(
            payment=payment,
            event_type=PaymentEventType.WEBHOOK_REJECTED,
            signature_valid=False,
        ).exists()

    def test_amount_mismatch_rejected(self, pending_payment_order, api):
        payment = pending_payment_order.payments.first()
        payload = _payload(pending_payment_order, payment, amount=1)
        response = api.post(
            WEBHOOK_URL, payload, format="json", HTTP_X_PAYMENT_SIGNATURE=_sign(payload)
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PENDING

    def test_success_marks_order_paid(self, sellable_product, buyer_user, client_factory):
        from apps.marketplace.models import Order

        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 3},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order = Order.objects.get(pk=checkout.data[0]["id"])
        payment, _ = payments.initiate_payment(order, buyer=buyer_user)

        payload = _payload(order, payment, provider_ref="MOCK-" + "b" * 32)
        response = client.post(
            WEBHOOK_URL, payload, format="json", HTTP_X_PAYMENT_SIGNATURE=_sign(payload)
        )
        assert response.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        order.refresh_from_db()
        sellable_product.refresh_from_db()
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.provider_reference == "MOCK-" + "b" * 32
        assert order.status == "paid"
        assert order.paid_at is not None
        # reservations became sales: stock left the shelf
        assert sellable_product.reserved_quantity == 0
        assert sellable_product.available_quantity == 7
        assert InventoryMovement.objects.filter(
            product=sellable_product, reason=InventoryMovementReason.SOLD, delta=-3
        ).exists()

    def test_duplicate_webhook_is_idempotent(
        self, sellable_product, buyer_user, client_factory
    ):
        from apps.marketplace.models import Order

        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order = Order.objects.get(pk=checkout.data[0]["id"])
        payment, _ = payments.initiate_payment(order, buyer=buyer_user)
        payload = _payload(order, payment, provider_ref="MOCK-" + "c" * 32)
        headers = {"HTTP_X_PAYMENT_SIGNATURE": _sign(payload)}
        first = client.post(WEBHOOK_URL, payload, format="json", **headers)
        second = client.post(WEBHOOK_URL, payload, format="json", **headers)
        assert first.status_code == 200
        assert second.status_code == 200
        sellable_product.refresh_from_db()
        assert sellable_product.available_quantity == 9  # consumed once, not twice
        assert PaymentEvent.objects.filter(
            payment=payment, event_type=PaymentEventType.DUPLICATE_IGNORED
        ).exists()

    def test_failed_outcome_keeps_order_payable(
        self, sellable_product, buyer_user, client_factory
    ):
        from apps.marketplace.models import Order

        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order = Order.objects.get(pk=checkout.data[0]["id"])
        payment, _ = payments.initiate_payment(order, buyer=buyer_user)
        payload = _payload(order, payment, outcome="failed")
        response = client.post(
            WEBHOOK_URL, payload, format="json", HTTP_X_PAYMENT_SIGNATURE=_sign(payload)
        )
        assert response.status_code == 200
        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED
        assert order.status == "pending_payment"
        # a fresh attempt can start afterwards
        again, created = payments.initiate_payment(order, buyer=buyer_user)
        assert created is True
        assert again.pk != payment.pk

    def test_conflicting_terminal_state_rejected(
        self, sellable_product, buyer_user, client_factory
    ):
        from apps.marketplace.models import Order

        client = client_factory(buyer_user)
        client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = client.post("/api/v1/marketplace/checkout/", {})
        order = Order.objects.get(pk=checkout.data[0]["id"])
        payment, _ = payments.initiate_payment(order, buyer=buyer_user)
        payload = _payload(order, payment, outcome="failed")
        client.post(
            WEBHOOK_URL, payload, format="json", HTTP_X_PAYMENT_SIGNATURE=_sign(payload)
        )
        # a later "succeeded" for the same failed payment must not flip the state
        late = _payload(order, payment, outcome="succeeded", provider_ref="MOCK-" + "d" * 32)
        response = client.post(
            WEBHOOK_URL, late, format="json", HTTP_X_PAYMENT_SIGNATURE=_sign(late)
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED

    @override_settings(PAYMENTS_ACCEPT_MOCK=False)
    def test_mock_disabled_in_this_environment(self, pending_payment_order, api):
        payment = pending_payment_order.payments.first()
        payload = _payload(pending_payment_order, payment)
        response = api.post(
            WEBHOOK_URL, payload, format="json", HTTP_X_PAYMENT_SIGNATURE=_sign(payload)
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PENDING


@pytest.mark.django_db
class TestSimulateEndpoint:
    def test_buyer_cannot_trigger_outcomes(
        self, paid_order, buyer_user, client_factory
    ):
        payment = paid_order.payments.first()
        client = client_factory(buyer_user)
        response = client.post(
            f"/api/v1/marketplace/payments/{payment.pk}/simulate/",
            {"outcome": "succeeded"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_simulates_failure(
        self, sellable_product, buyer_user, platform_admin, client_factory
    ):
        from apps.marketplace.models import Order

        buyer_client = client_factory(buyer_user)
        buyer_client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = buyer_client.post("/api/v1/marketplace/checkout/", {})
        order = Order.objects.get(pk=checkout.data[0]["id"])
        payment, _ = payments.initiate_payment(order, buyer=buyer_user)

        admin_client = client_factory(platform_admin)
        response = admin_client.post(
            f"/api/v1/marketplace/payments/{payment.pk}/simulate/",
            {"outcome": "failed"},
        )
        assert response.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED
        assert payment.events.filter(
            event_type=PaymentEventType.WEBHOOK_ACCEPTED
        ).exists()

    def test_invalid_outcome_rejected(
        self, sellable_product, buyer_user, platform_admin, client_factory
    ):
        from apps.marketplace.models import Order

        buyer_client = client_factory(buyer_user)
        buyer_client.post(
            "/api/v1/marketplace/cart/items/",
            {"product": str(sellable_product.pk), "quantity": 1},
        )
        checkout = buyer_client.post("/api/v1/marketplace/checkout/", {})
        order = Order.objects.get(pk=checkout.data[0]["id"])
        payment, _ = payments.initiate_payment(order, buyer=buyer_user)
        admin_client = client_factory(platform_admin)
        response = admin_client.post(
            f"/api/v1/marketplace/payments/{payment.pk}/simulate/",
            {"outcome": "exploded"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestExpiryCommand:
    def test_command_cancels_stale_orders(self, sellable_product, buyer_user, db):
        from django.core.management import call_command


        services.add_to_cart(buyer_user, product=sellable_product, quantity=2)
        order = services.checkout(buyer_user, shipping={})[0]
        payments.initiate_payment(order, buyer=buyer_user)
        order.placed_at = timezone.now() - timedelta(hours=30)
        order.save(update_fields=["placed_at"])

        call_command("expire_marketplace_orders")
        order.refresh_from_db()
        sellable_product.refresh_from_db()
        assert order.status == "cancelled"
        assert sellable_product.reserved_quantity == 0
        assert Payment.objects.filter(
            order=order, status=PaymentStatus.CANCELLED
        ).exists()
