from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from . import services
from .models import (
    Dispute,
    InventoryMovement,
    InventoryMovementReason,
    Order,
    OrderStatus,
    Payment,
    PaymentEvent,
    PaymentEventType,
    PaymentStatus,
    Product,
    Refund,
    RefundStatus,
)

# Header carrying the provider's HMAC over the raw JSON body.
WEBHOOK_SIGNATURE_HEADER = "X-Payment-Signature"
_SIMULATED_OUTCOMES = frozenset({"succeeded", "failed"})
# Keys never persisted in the event ledger, whatever a provider sends.
_REDACTED_KEY_MARKERS = ("card", "cvc", "cvv", "pan", "security_code", "secret", "password")


def _webhook_secret() -> bytes:
    secret = settings.PAYMENT_WEBHOOK_SECRET or settings.SECRET_KEY
    return str(secret).encode()


def sign_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_webhook_secret(), canonical, hashlib.sha256).hexdigest()


def _redact(payload: dict) -> dict:
    return {
        key: value
        for key, value in payload.items()
        if not any(marker in str(key).lower() for marker in _REDACTED_KEY_MARKERS)
    }


def log_payment_event(
    payment: Payment,
    event_type: str,
    *,
    payload: dict | None = None,
    signature_valid: bool | None = None,
) -> PaymentEvent:
    return PaymentEvent.objects.create(
        payment=payment,
        event_type=event_type,
        payload=_redact(payload or {}),
        signature_valid=signature_valid,
    )


def pending_window_expired(order: Order) -> bool:
    ttl = timedelta(hours=settings.PAYMENT_PENDING_TTL_HOURS)
    return order.placed_at + ttl <= timezone.now()


# ── Initiation ─────────────────────────────────────────────────────────
def initiate_payment(
    order: Order, *, buyer, idempotency_key: str = "", request=None
) -> tuple[Payment, bool]:
    """Start a payment attempt; returns (payment, created)."""
    if order.buyer_id != getattr(buyer, "pk", None):
        raise exceptions.NotFound()
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise exceptions.ValidationError(
            {"status": f"An order in status '{order.status}' cannot be paid."}
        )
    if pending_window_expired(order):
        expire_order(order, request=request)
        raise exceptions.ValidationError(
            {"order": "The payment window for this order has expired."}
        )
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.order_id != order.pk:
                raise exceptions.ValidationError(
                    {"Idempotency-Key": "This key was already used for another order."}
                )
            return existing, False
    existing_pending = order.payments.filter(status=PaymentStatus.PENDING).first()
    if existing_pending is not None:
        if idempotency_key and not existing_pending.idempotency_key:
            existing_pending.idempotency_key = idempotency_key[:64]
            existing_pending.save(update_fields=["idempotency_key", "updated_at"])
        return existing_pending, False

    payment = Payment.objects.create(
        order=order,
        provider=settings.PAYMENT_PROVIDER,
        amount=order.total,
        currency=order.currency,
        idempotency_key=(idempotency_key or "")[:64],
    )
    log_payment_event(payment, PaymentEventType.INITIATED)
    record_audit(
        request=request,
        actor=buyer,
        action=AuditEvent.Action.PAYMENT_INITIATED,
        object_type="payment",
        object_pk=payment.pk,
        metadata={
            "reference": order.reference,
            "amount": str(payment.amount),
            "provider": payment.provider,
        },
    )
    return payment, True


# ── Webhook (the only way money moves) ─────────────────────────────────
def _find_payment(payload: dict) -> Payment | None:
    provider_reference = str(payload.get("provider_reference") or "")
    if provider_reference:
        payment = Payment.objects.filter(provider_reference=provider_reference).first()
        if payment is not None:
            return payment
    order_reference = str(payload.get("order_reference") or "")
    if not order_reference:
        return None
    order = Order.objects.filter(reference=order_reference).first()
    if order is None:
        return None
    return (
        order.payments.order_by("-created_at")
        .filter(status=PaymentStatus.PENDING)
        .first()
        or order.payments.order_by("-created_at").first()
    )


def apply_webhook(payload: dict, signature: str, *, request=None) -> Payment:
    """Verify a provider webhook and apply its outcome. Never trust the client."""
    if not isinstance(payload, dict) or not payload:
        raise exceptions.ValidationError({"payload": "Expected a JSON object."})
    payment = _find_payment(payload)
    if payment is None:
        raise exceptions.ValidationError({"payload": "Unknown payment reference."})

    expected = sign_payload(payload)
    provided = str(signature or "")
    if not provided or not hmac.compare_digest(expected, provided):
        log_payment_event(
            payment,
            PaymentEventType.WEBHOOK_REJECTED,
            payload=payload,
            signature_valid=False,
        )
        raise exceptions.ValidationError({"signature": "Invalid webhook signature."})
    if not settings.PAYMENTS_ACCEPT_MOCK:
        log_payment_event(
            payment,
            PaymentEventType.WEBHOOK_REJECTED,
            payload=payload,
            signature_valid=True,
        )
        raise exceptions.ValidationError(
            {"signature": "Mock payments are disabled in this environment."}
        )

    outcome = str(payload.get("outcome") or "")
    if outcome not in _SIMULATED_OUTCOMES:
        log_payment_event(
            payment,
            PaymentEventType.WEBHOOK_REJECTED,
            payload=payload,
            signature_valid=True,
        )
        raise exceptions.ValidationError({"outcome": "Unknown payment outcome."})

    amount = str(payload.get("amount") or "")
    currency = str(payload.get("currency") or "")
    if amount != str(payment.amount) or currency != payment.currency:
        log_payment_event(
            payment,
            PaymentEventType.WEBHOOK_REJECTED,
            payload=payload,
            signature_valid=True,
        )
        raise exceptions.ValidationError(
            {"amount": "Amount or currency does not match the expected payment."}
        )

    expected_status = (
        PaymentStatus.SUCCEEDED if outcome == "succeeded" else PaymentStatus.FAILED
    )
    if payment.status == expected_status:
        log_payment_event(
            payment,
            PaymentEventType.DUPLICATE_IGNORED,
            payload=payload,
            signature_valid=True,
        )
        return payment
    if payment.is_terminal:
        log_payment_event(
            payment,
            PaymentEventType.WEBHOOK_REJECTED,
            payload=payload,
            signature_valid=True,
        )
        raise exceptions.ValidationError(
            {"status": "This payment already reached a different final state."}
        )

    log_payment_event(
        payment, PaymentEventType.WEBHOOK_ACCEPTED, payload=payload, signature_valid=True
    )
    return _apply_outcome(payment, outcome, payload=payload, request=request)


def _consume_stock(order: Order) -> None:
    """Turn reservations into sales once money is settled."""
    for item in order.items.select_related("product"):
        if item.product is None:
            continue
        product = Product.objects.select_for_update().get(pk=item.product_id)
        product.available_quantity = max(
            product.available_quantity - item.quantity, 0
        )
        product.reserved_quantity = max(product.reserved_quantity - item.quantity, 0)
        product.save(
            update_fields=["available_quantity", "reserved_quantity", "updated_at"]
        )
        InventoryMovement.objects.create(
            product=product,
            delta=-item.quantity,
            reason=InventoryMovementReason.SOLD,
            order=order,
            note="Settled payment",
        )


def _restock_after_refund(order: Order) -> None:
    """Give refunded goods back to available stock."""
    for item in order.items.select_related("product"):
        if item.product is None:
            continue
        product = Product.objects.select_for_update().get(pk=item.product_id)
        product.available_quantity += item.quantity
        product.save(update_fields=["available_quantity", "updated_at"])
        InventoryMovement.objects.create(
            product=product,
            delta=item.quantity,
            reason=InventoryMovementReason.ADJUSTED,
            order=order,
            note="Refund restock",
        )


@transaction.atomic
def _apply_outcome(
    payment: Payment, outcome: str, *, payload: dict, request=None
) -> Payment:
    order = payment.order
    if outcome == "succeeded":
        if order.status != OrderStatus.PENDING_PAYMENT:
            log_payment_event(
                payment,
                PaymentEventType.WEBHOOK_REJECTED,
                payload=payload,
                signature_valid=True,
            )
            raise exceptions.ValidationError(
                {"status": "The order is no longer awaiting payment."}
            )
        provider_reference = str(payload.get("provider_reference") or "")[:100]
        payment.status = PaymentStatus.SUCCEEDED
        payment.provider_reference = provider_reference or f"MOCK-{uuid.uuid4().hex}"
        payment.paid_at = timezone.now()
        payment.failure_reason = ""
        payment.save(
            update_fields=[
                "status",
                "provider_reference",
                "paid_at",
                "failure_reason",
                "updated_at",
            ]
        )
        order.status = OrderStatus.PAID
        order.paid_at = payment.paid_at
        order.save(update_fields=["status", "paid_at", "updated_at"])
        _consume_stock(order)
        log_payment_event(payment, PaymentEventType.SUCCEEDED, payload=payload)
        record_audit(
            request=request,
            actor=order.buyer,
            action=AuditEvent.Action.PAYMENT_SUCCEEDED,
            object_type="payment",
            object_pk=payment.pk,
            metadata={
                "reference": order.reference,
                "amount": str(payment.amount),
                "provider_reference": payment.provider_reference,
            },
        )
        return payment

    payment.status = PaymentStatus.FAILED
    payment.failure_reason = str(payload.get("reason") or "declined by provider")[:255]
    payment.save(update_fields=["status", "failure_reason", "updated_at"])
    log_payment_event(payment, PaymentEventType.FAILED, payload=payload)
    record_audit(
        request=request,
        actor=order.buyer,
        action=AuditEvent.Action.PAYMENT_FAILED,
        object_type="payment",
        object_pk=payment.pk,
        metadata={
            "reference": order.reference,
            "reason": payment.failure_reason,
        },
    )
    return payment


# ── Sandbox simulation (development & tests only) ──────────────────────
def simulate_payment(payment: Payment, *, outcome: str, request=None) -> Payment:
    """Act as the sandbox provider: build a signed webhook and deliver it."""
    if not settings.PAYMENTS_ACCEPT_MOCK or settings.PAYMENT_PROVIDER != "sandbox":
        raise exceptions.NotFound()
    if outcome not in _SIMULATED_OUTCOMES:
        raise exceptions.ValidationError(
            {"outcome": "Expected 'succeeded' or 'failed'."}
        )
    payload = {
        "provider_reference": f"MOCK-{uuid.uuid4().hex}",
        "order_reference": payment.order.reference,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "outcome": outcome,
        "timestamp": timezone.now().isoformat(),
    }
    return apply_webhook(payload, sign_payload(payload), request=request)


# ── Refund settlement ──────────────────────────────────────────────────
@transaction.atomic
def settle_refund(refund: Refund, *, actor, request=None) -> None:
    """Mark the payment and order as refunded after a supplier approval."""
    payment = Payment.objects.select_for_update().get(pk=refund.payment_id)
    order = Order.objects.select_for_update().get(pk=refund.order_id)
    if payment.status != PaymentStatus.SUCCEEDED:
        raise exceptions.ValidationError(
            {"payment": "Only a settled payment can be refunded."}
        )
    if order.status == OrderStatus.REFUNDED:
        return
    payment.status = PaymentStatus.REFUNDED
    payment.save(update_fields=["status", "updated_at"])
    order.status = OrderStatus.REFUNDED
    order.save(update_fields=["status", "updated_at"])
    _restock_after_refund(order)
    log_payment_event(
        payment,
        PaymentEventType.REFUND_COMPLETED,
        payload={"refund_id": str(refund.pk), "amount": str(refund.amount)},
    )
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.REFUND_COMPLETED,
        object_type="refund",
        object_pk=refund.pk,
        metadata={
            "reference": order.reference,
            "amount": str(refund.amount),
        },
    )


@transaction.atomic
def refund_for_dispute(dispute: Dispute, *, actor, request=None) -> Refund | None:
    """Platform-admin resolution for the buyer: settle a full refund, once."""
    order = Order.objects.select_for_update().get(pk=dispute.order_id)
    payment = order.payments.filter(status=PaymentStatus.SUCCEEDED).first()
    if payment is None:
        return None
    if order.status == OrderStatus.REFUNDED:
        return None
    refund = Refund.objects.create(
        order=order,
        payment=payment,
        amount=payment.amount,
        currency=payment.currency,
        reason=(dispute.description or "Dispute resolved for the buyer.")[:4000],
        requested_by=dispute.opened_by,
        decided_by=actor,
        decided_at=timezone.now(),
        status=RefundStatus.COMPLETED,
    )
    settle_refund(refund, actor=actor, request=request)
    return refund


# ── Expiry ─────────────────────────────────────────────────────────────
@transaction.atomic
def expire_order(order: Order, *, request=None) -> Order:
    """Cancel a stale pending_payment order and release its stock."""
    if order.status != OrderStatus.PENDING_PAYMENT:
        return order
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = "Payment window expired"
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    services.release_stock(order, actor=None)
    pending = order.payments.filter(status=PaymentStatus.PENDING).first()
    if pending is not None:
        pending.status = PaymentStatus.CANCELLED
        pending.save(update_fields=["status", "updated_at"])
        log_payment_event(pending, PaymentEventType.EXPIRED)
        record_audit(
            request=request,
            actor=order.buyer,
            action=AuditEvent.Action.PAYMENT_EXPIRED,
            object_type="payment",
            object_pk=pending.pk,
            metadata={"reference": order.reference},
        )
    record_audit(
        request=request,
        actor=order.buyer,
        action=AuditEvent.Action.ORDER_CANCELLED,
        object_type="order",
        object_pk=order.pk,
        metadata={"reference": order.reference, "reason": "payment_window_expired"},
    )
    return order


def expire_stale_orders(*, request=None) -> int:
    """Cancel every order whose payment window has elapsed. Returns the count."""
    ttl = timedelta(hours=settings.PAYMENT_PENDING_TTL_HOURS)
    stale = list(
        Order.objects.filter(
            status=OrderStatus.PENDING_PAYMENT, placed_at__lte=timezone.now() - ttl
        ).select_related("buyer")
    )
    for order in stale:
        expire_order(order, request=request)
    return len(stale)
