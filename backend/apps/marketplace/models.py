from __future__ import annotations

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel
from apps.logbook.uploads import private_storage

# Monetary amounts are whole francs (XOF has no minor unit).
MONEY_MAX_DIGITS = 12
CURRENCIES = [("XOF", "West African CFA franc")]


def _new_order_reference() -> str:
    return f"ORD-{timezone.now().year}-{secrets.token_hex(3).upper()}"


# ── Suppliers ──────────────────────────────────────────────────────────
class SupplierVerificationStatus(models.TextChoices):
    PENDING = "pending", "Pending verification"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class SupplierProfile(UUIDModel, TimeStampedModel):
    """Commercial profile of one supplier account."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supplier_profile",
    )
    company_name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    commercial_notes = models.TextField(blank=True)
    verification_status = models.CharField(
        max_length=16,
        choices=SupplierVerificationStatus.choices,
        default=SupplierVerificationStatus.PENDING,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="suppliers_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["company_name"]
        verbose_name = "supplier profile"
        verbose_name_plural = "supplier profiles"

    def __str__(self) -> str:
        return f"{self.company_name} ({self.verification_status})"

    @property
    def is_verified(self) -> bool:
        return self.verification_status == SupplierVerificationStatus.VERIFIED


# ── Catalog ────────────────────────────────────────────────────────────
class ProductCategory(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "product category"
        verbose_name_plural = "product categories"

    def __str__(self) -> str:
        return self.name


class ProductApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Product(UUIDModel, TimeStampedModel):
    supplier = models.ForeignKey(
        SupplierProfile, on_delete=models.CASCADE, related_name="products"
    )
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=0
    )
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="XOF")
    available_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False, db_index=True)
    approval_status = models.CharField(
        max_length=16,
        choices=ProductApprovalStatus.choices,
        default=ProductApprovalStatus.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    regulatory_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "product"
        verbose_name_plural = "products"
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "sku"], name="uniq_supplier_sku"
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__lte=models.F("available_quantity")),
                name="product_reserved_lte_available",
            ),
        ]
        indexes = [
            models.Index(fields=["approval_status", "is_published"], name="product_public"),
            models.Index(fields=["supplier", "is_active"], name="product_supplier_active"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"

    def clean(self):
        super().clean()
        if self.reserved_quantity > self.available_quantity:
            raise ValidationError(
                {"reserved_quantity": "Reserved quantity cannot exceed stock."}
            )

    @property
    def free_quantity(self) -> int:
        return max(self.available_quantity - self.reserved_quantity, 0)

    @property
    def is_sellable(self) -> bool:
        return (
            self.is_active
            and self.is_published
            and self.approval_status == ProductApprovalStatus.APPROVED
            and self.supplier.is_verified
        )


class InventoryMovementReason(models.TextChoices):
    RESERVED = "reserved", "Stock reserved for an order"
    RELEASED = "released", "Reservation released"
    SOLD = "sold", "Sold"
    RESTOCKED = "restocked", "Stock restocked"
    ADJUSTED = "adjusted", "Manual adjustment"


class InventoryMovement(UUIDModel, TimeStampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="movements"
    )
    delta = models.IntegerField()
    reason = models.CharField(max_length=16, choices=InventoryMovementReason.choices)
    order = models.ForeignKey(
        "Order", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="inventory_movements",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_movements",
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reason} {self.delta:+d} · {self.product.sku}"


# ── Cart ───────────────────────────────────────────────────────────────
class Cart(UUIDModel, TimeStampedModel):
    buyer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart"
    )

    class Meta:
        verbose_name = "shopping cart"

    def __str__(self) -> str:
        return f"Cart of {self.buyer.email}"


class CartItem(UUIDModel, TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "cart item"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_cart_product")
        ]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product.sku}"

    @property
    def line_total(self):
        return self.quantity * self.product.unit_price


# ── Orders ─────────────────────────────────────────────────────────────
class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "Pending payment"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    REFUNDED = "refunded", "Refunded"


class Order(UUIDModel, TimeStampedModel):
    """One order per supplier; item prices are frozen snapshots."""

    reference = models.CharField(
        max_length=32, unique=True, default=_new_order_reference, editable=False,
        db_index=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders_placed"
    )
    supplier = models.ForeignKey(
        SupplierProfile, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
        db_index=True,
    )
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="XOF")
    subtotal = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=0)
    total = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=0)
    shipping_name = models.CharField(max_length=200, blank=True)
    shipping_address = models.TextField(blank=True)
    shipping_phone = models.CharField(max_length=40, blank=True)
    placed_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-placed_at"]
        verbose_name = "order"
        verbose_name_plural = "orders"
        indexes = [
            models.Index(fields=["buyer", "-placed_at"], name="order_buyer_time"),
            models.Index(fields=["supplier", "-placed_at"], name="order_supplier_time"),
            models.Index(fields=["status"], name="order_status"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.status})"

    @property
    def is_cancellable(self) -> bool:
        return self.status == OrderStatus.PENDING_PAYMENT


class OrderItem(UUIDModel, TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=64)
    product_description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=0)
    line_total = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=0)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "order item"

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product_name}"


# ── Payments (sandbox provider) ────────────────────────────────────────
class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUNDED = "refunded", "Refunded"


class Payment(UUIDModel, TimeStampedModel):
    """One payment attempt for an order; webhook outcomes are verified server-side."""

    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="payments"
    )
    provider = models.CharField(max_length=32, default="sandbox")
    status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=0)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="XOF")
    idempotency_key = models.CharField(max_length=64, blank=True, default="")
    provider_reference = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    failure_reason = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "payment"
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_payment_idempotency_key",
            )
        ]
        indexes = [
            models.Index(fields=["order", "-created_at"], name="payment_order_time"),
        ]

    def __str__(self) -> str:
        return f"{self.order.reference} · {self.status}"

    @property
    def is_terminal(self) -> bool:
        return self.status != PaymentStatus.PENDING


class PaymentEventType(models.TextChoices):
    INITIATED = "initiated", "Payment initiated"
    WEBHOOK_ACCEPTED = "webhook_accepted", "Webhook accepted"
    WEBHOOK_REJECTED = "webhook_rejected", "Webhook rejected"
    DUPLICATE_IGNORED = "duplicate_ignored", "Duplicate webhook ignored"
    SUCCEEDED = "succeeded", "Payment succeeded"
    FAILED = "failed", "Payment failed"
    EXPIRED = "expired", "Payment window expired"
    REFUND_REQUESTED = "refund_requested", "Refund requested"
    REFUND_COMPLETED = "refund_completed", "Refund completed"
    REFUND_REJECTED = "refund_rejected", "Refund rejected"


class PaymentEvent(UUIDModel, TimeStampedModel):
    """Append-only ledger of everything that happened to a payment."""

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=24, choices=PaymentEventType.choices)
    payload = models.JSONField(default=dict, blank=True)
    signature_valid = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "payment event"

    def __str__(self) -> str:
        return f"{self.payment.order.reference} · {self.event_type}"


# ── Shipping ───────────────────────────────────────────────────────────
class ShipmentStatus(models.TextChoices):
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"


class Shipment(UUIDModel, TimeStampedModel):
    order = models.OneToOneField(
        Order, on_delete=models.PROTECT, related_name="shipment"
    )
    status = models.CharField(
        max_length=16, choices=ShipmentStatus.choices, default=ShipmentStatus.SHIPPED
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    shipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shipments_sent",
    )

    class Meta:
        ordering = ["-shipped_at"]
        verbose_name = "shipment"

    def __str__(self) -> str:
        return f"{self.order.reference} · {self.status}"


# ── Refunds ────────────────────────────────────────────────────────────
class RefundStatus(models.TextChoices):
    PENDING = "pending", "Pending supplier decision"
    REJECTED = "rejected", "Rejected"
    COMPLETED = "completed", "Completed"


class Refund(UUIDModel, TimeStampedModel):
    """Buyer-requested refund; the supplier decides, completion settles the payment."""

    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="refunds"
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="refunds"
    )
    status = models.CharField(
        max_length=16, choices=RefundStatus.choices, default=RefundStatus.PENDING,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=0)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="XOF")
    reason = models.TextField(blank=True)
    decision_reason = models.CharField(max_length=255, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refunds_requested",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="refunds_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "refund"
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status="pending"),
                name="uniq_pending_refund_per_order",
            )
        ]

    def __str__(self) -> str:
        return f"{self.order.reference} · {self.status}"


# ── Disputes ───────────────────────────────────────────────────────────
class DisputeStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"


class DisputeResolution(models.TextChoices):
    BUYER_FAVORED = "buyer_favored", "Resolved for the buyer"
    SUPPLIER_FAVORED = "supplier_favored", "Resolved for the supplier"


class Dispute(UUIDModel, TimeStampedModel):
    """One dispute per order, with text/file evidence from both parties."""

    order = models.OneToOneField(
        Order, on_delete=models.PROTECT, related_name="dispute"
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="disputes_opened",
    )
    status = models.CharField(
        max_length=16, choices=DisputeStatus.choices, default=DisputeStatus.OPEN,
        db_index=True,
    )
    description = models.TextField()
    resolution = models.CharField(
        max_length=24, choices=DisputeResolution.choices, blank=True
    )
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="disputes_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "dispute"

    def __str__(self) -> str:
        return f"{self.order.reference} · {self.status}"


class DisputeEvidence(UUIDModel, TimeStampedModel):
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, related_name="evidence_entries"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dispute_evidence",
    )
    body = models.TextField(blank=True)
    file = models.FileField(
        upload_to="disputes/%Y/%m/", storage=private_storage, blank=True
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "dispute evidence"

    def __str__(self) -> str:
        return f"{self.dispute.order.reference} · evidence"
