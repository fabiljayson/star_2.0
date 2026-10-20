"""Seller-subscription business logic.

Pricing and period length are decided here, server-side only: no client
value can set a price, an expiration or a payment outcome. Periods are
calendar months — a period that starts on Jan 31 ends on Feb 28/29, never
on a fictitious "Feb 31".
"""

from __future__ import annotations

import calendar
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.core.audit import record_audit
from apps.core.exceptions import SellerSubscriptionRequired
from apps.core.models import AuditEvent

from .models import (
    Payment,
    PaymentEvent,
    PaymentEventType,
    PaymentStatus,
    SellerSubscription,
    SubscriptionStatus,
)

# ── Plan configuration (server-side only) ─────────────────────────────
PLAN_MONTHLY = "monthly"
PLAN_SEMIANNUAL = "semiannual"
PLAN_ANNUAL = "annual"

# Whole CFA francs / calendar months. Named plans chosen by the user.
PLAN_PRICES: dict[str, int] = {
    PLAN_MONTHLY: 5000,
    PLAN_SEMIANNUAL: 10000,
    PLAN_ANNUAL: 12000,
}
PLAN_MONTHS: dict[str, int] = {
    PLAN_MONTHLY: 1,
    PLAN_SEMIANNUAL: 6,
    PLAN_ANNUAL: 12,
}

# Welcome price: the first month a user ever buys, on the monthly plan
# only, is charged this reduced amount.
FIRST_MONTH_PRICE = 2500

SUBSCRIPTION_CURRENCY = "XOF"
SUBSCRIPTION_ERROR_CODE = "seller_subscription_required"


def is_valid_plan(plan: str) -> bool:
    return plan in PLAN_PRICES


# ── Calendar-month arithmetic ─────────────────────────────────────────
def add_calendar_months(start: datetime, months: int) -> datetime:
    """Calendar months with day clamping (Jan 31 + 1 month -> Feb 28/29)."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


# ── Effective status (the server clock decides) ───────────────────────
def effective_subscription(user) -> SellerSubscription | None:
    """The subscription granting seller rights right now, or None.

    Dynamic by design: a cron job bumping the status field must not be the
    reason access stops — comparing expires_at with the server time is.
    """
    if not user or not user.is_authenticated:
        return None
    now = timezone.now()
    row = (
        SellerSubscription.objects.select_related("user")
        .filter(
            user=user,
            status=SubscriptionStatus.ACTIVE,
            expires_at__gt=now,
        )
        .first()
    )
    if row is None:
        return None
    if row.starts_at is not None and row.starts_at > now:
        # The period was bought while the previous one was still running:
        # it only becomes effective once it starts.
        return None
    return row


def latest_subscription(user) -> SellerSubscription | None:
    if not user or not user.is_authenticated:
        return None
    return SellerSubscription.objects.filter(user=user).first()


def had_any_subscription(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return SellerSubscription.objects.filter(user=user).exists()


def can_publish(user) -> bool:
    return effective_subscription(user) is not None


def require_active_subscription(user) -> SellerSubscription:
    subscription = effective_subscription(user)
    if subscription is None:
        raise SellerSubscriptionRequired()
    return subscription


def price_for(user, plan: str) -> int:
    if plan not in PLAN_PRICES:
        raise exceptions.ValidationError({"plan": "Unknown subscription plan."})
    if plan == PLAN_MONTHLY and not had_any_subscription(user):
        return FIRST_MONTH_PRICE
    return PLAN_PRICES[plan]


def status_payload(user) -> dict:
    """Server-computed subscription status, ready for the API serializer."""
    now = timezone.now()
    row = latest_subscription(user)
    active = effective_subscription(user)
    if active is None:
        if row is not None and row.status == SubscriptionStatus.ACTIVE:
            # Status field stale (row lapsed in the DB without a cron pass).
            row_status = SubscriptionStatus.EXPIRED
        elif row is not None and row.status in {
            SubscriptionStatus.PENDING,
            SubscriptionStatus.FAILED,
            SubscriptionStatus.CANCELLED,
        }:
            row_status = row.status
        else:
            row_status = "none"
        return {
            "status": row_status,
            "plan": row.plan if row is not None else None,
            "amount_fcfa": (
                int(row.amount) if row is not None else price_for(user, PLAN_MONTHLY)
            ),
            "currency": row.currency if row is not None else SUBSCRIPTION_CURRENCY,
            "starts_at": row.starts_at if row is not None else None,
            "expires_at": row.expires_at if row is not None else None,
            "server_now": now,
            "can_publish": False,
            "remaining_seconds": 0,
            "renewal_available": True,
            "visibility_policy": "hidden_while_inactive",
        }
    remaining = active.expires_at - (
        active.starts_at if active.starts_at and active.starts_at > now else now
    )
    return {
        "status": SubscriptionStatus.ACTIVE,
        "plan": active.plan,
        "amount_fcfa": int(active.amount),
        "currency": active.currency,
        "starts_at": active.starts_at,
        "expires_at": active.expires_at,
        "server_now": now,
        "can_publish": True,
        "remaining_seconds": int(remaining.total_seconds()),
        "renewal_available": True,
        "visibility_policy": "visible_while_active",
    }


# ── Checkout ──────────────────────────────────────────────────────────
@transaction.atomic
def start_checkout(user, *, plan: str, idempotency_key: str = "", request=None):
    """Create (or reuse) a pending subscription and its payment attempt.

    Returns (subscription, payment, created).
    """
    untrusted_plan = plan
    if untrusted_plan not in PLAN_PRICES:
        raise exceptions.ValidationError({"plan": "Unknown subscription plan."})
    amount = price_for(user, untrusted_plan)
    idempotency_key = (idempotency_key or "")[:64]

    if idempotency_key:
        existing = Payment.objects.filter(
            idempotency_key=idempotency_key, subscription__isnull=False
        ).first()
        if existing is not None:
            if existing.subscription_id is None or existing.subscription.user_id != user.pk:
                raise exceptions.ValidationError(
                    {"Idempotency-Key": "This key was already used for another user."}
                )
            return existing.subscription, existing, False

    pending = (
        SellerSubscription.objects.filter(
            user=user, status=SubscriptionStatus.PENDING
        )
        .order_by("-created_at")
        .first()
    )
    if pending is None:
        pending = SellerSubscription.objects.create(
            user=user,
            plan=untrusted_plan,
            amount=amount,
            currency=SUBSCRIPTION_CURRENCY,
        )
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.SUBSCRIPTION_STARTED,
            object_type="subscription",
            object_pk=pending.pk,
            metadata={"plan": untrusted_plan, "amount": str(amount)},
        )
    else:
        if pending.plan != untrusted_plan or pending.amount != amount:
            pending.plan = untrusted_plan
            pending.amount = amount
            pending.save(update_fields=["plan", "amount", "updated_at"])
        pending.payments.filter(status=PaymentStatus.PENDING).update(
            status=PaymentStatus.CANCELLED
        )

    payment = Payment.objects.create(
        subscription=pending,
        provider=settings.PAYMENT_PROVIDER,
        amount=pending.amount,
        currency=pending.currency,
        idempotency_key=idempotency_key,
    )
    PaymentEvent.objects.create(
        payment=payment, event_type=PaymentEventType.INITIATED
    )
    record_audit(
        request=request,
        actor=user,
        action=AuditEvent.Action.PAYMENT_INITIATED,
        object_type="payment",
        object_pk=payment.pk,
        metadata={
            "reference": pending.reference,
            "amount": str(payment.amount),
            "provider": payment.provider,
        },
    )
    return pending, payment, True


# ── Outcome application (only verified webhooks reach this) ───────────
@transaction.atomic
def apply_outcome(payment: Payment, outcome: str, *, payload: dict, request=None):
    """Turn a verified webhook outcome into a subscription lifecycle move."""
    subscription = SellerSubscription.objects.select_for_update().get(
        pk=payment.subscription_id
    )
    if subscription.status not in (SubscriptionStatus.PENDING, SubscriptionStatus.EXPIRED):
        raise exceptions.ValidationError(
            {"status": "This subscription already reached a different final state."}
        )

    if outcome != "succeeded":
        return _fail(payment, subscription, payload, request=request)

    # Renewal while a period is still running keeps the remaining paid time:
    # the new period starts where the old one ends.
    superseded = _supersede_current(subscription.user, now=timezone.now())
    now = timezone.now()
    base = superseded.expires_at if superseded is not None else now
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.starts_at = base
    subscription.expires_at = add_calendar_months(
        base, PLAN_MONTHS[subscription.plan]
    )
    subscription.save(
        update_fields=["status", "starts_at", "expires_at", "updated_at"]
    )
    provider_reference = str(payload.get("provider_reference") or "")[:100]
    payment.status = PaymentStatus.SUCCEEDED
    payment.paid_at = now
    payment.failure_reason = ""
    payment.provider_reference = provider_reference or f"MOCK-{uuid.uuid4().hex}"
    payment.save(
        update_fields=[
            "status",
            "paid_at",
            "failure_reason",
            "provider_reference",
            "updated_at",
        ]
    )
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEventType.SUCCEEDED,
        payload=_safe_payload(payload),
    )
    record_audit(
        request=request,
        actor=subscription.user,
        action=AuditEvent.Action.SUBSCRIPTION_ACTIVATED,
        object_type="subscription",
        object_pk=subscription.pk,
        metadata={
            "reference": subscription.reference,
            "plan": subscription.plan,
            "renewal": superseded is not None,
            "expires_at": subscription.expires_at.isoformat(),
        },
    )
    return subscription


def _fail(payment: Payment, subscription: SellerSubscription, payload: dict, *, request=None):
    reason = str(payload.get("reason") or "declined by provider")[:255]
    payment.status = PaymentStatus.FAILED
    payment.failure_reason = reason
    payment.save(update_fields=["status", "failure_reason", "updated_at"])
    PaymentEvent.objects.create(
        payment=payment,
        event_type=PaymentEventType.FAILED,
        payload=_safe_payload(payload),
    )
    if subscription.status == SubscriptionStatus.PENDING:
        subscription.status = SubscriptionStatus.FAILED
        subscription.save(update_fields=["status", "updated_at"])
    record_audit(
        request=request,
        actor=subscription.user,
        action=AuditEvent.Action.SUBSCRIPTION_FAILED,
        object_type="subscription",
        object_pk=subscription.pk,
        metadata={"reference": subscription.reference, "reason": reason},
    )
    return subscription


def _supersede_current(user, *, now) -> SellerSubscription | None:
    """Close the current ACTIVE row so the renewed one can become ACTIVE.

    Returns the superseded row when its period still had time left (the
    renewed period starts at its expires_at), else None.
    """
    current = (
        SellerSubscription.objects.select_for_update()
        .filter(user=user, status=SubscriptionStatus.ACTIVE)
        .first()
    )
    if current is None:
        return None
    if current.expires_at is not None and current.expires_at > now:
        current.status = SubscriptionStatus.RENEWED
        current.save(update_fields=["status", "updated_at"])
        return current
    current.status = SubscriptionStatus.EXPIRED
    current.save(update_fields=["status", "updated_at"])
    return None


def _safe_payload(payload: dict) -> dict:
    from .payments import _REDACTED_KEY_MARKERS

    return {
        key: value
        for key, value in payload.items()
        if not any(marker in str(key).lower() for marker in _REDACTED_KEY_MARKERS)
    }


# ── Housekeeping ──────────────────────────────────────────────────────
@transaction.atomic
def expire_stale_subscriptions(*, request=None) -> int:
    """SERVER-side lockstep with the clock: flip lapsed ACTIVE rows, and
    cancel pending checkouts that never paid within the payment window."""
    changed = 0
    now = timezone.now()
    lapsed = SellerSubscription.objects.filter(
        status=SubscriptionStatus.ACTIVE, expires_at__lte=now
    )
    for row in lapsed:
        row.status = SubscriptionStatus.EXPIRED
        row.save(update_fields=["status", "updated_at"])
        record_audit(
            request=request,
            actor=row.user,
            action=AuditEvent.Action.SUBSCRIPTION_EXPIRED,
            object_type="subscription",
            object_pk=row.pk,
            metadata={"reference": row.reference},
        )
        changed += 1

    ttl_hours = getattr(settings, "PAYMENT_PENDING_TTL_HOURS", 24)
    window = now - timedelta(hours=ttl_hours)
    stale = SellerSubscription.objects.filter(
        status=SubscriptionStatus.PENDING, created_at__lte=window
    )
    for row in stale:
        row.status = SubscriptionStatus.CANCELLED
        row.cancelled_at = now
        row.cancel_reason = "Payment window expired"
        row.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancel_reason",
                "updated_at",
            ]
        )
        row.payments.filter(status=PaymentStatus.PENDING).update(
            status=PaymentStatus.CANCELLED
        )
        record_audit(
            request=request,
            actor=row.user,
            action=AuditEvent.Action.SUBSCRIPTION_PENDING_CANCELLED,
            object_type="subscription",
            object_pk=row.pk,
            metadata={"reference": row.reference},
        )
        changed += 1
    return changed
