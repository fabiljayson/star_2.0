from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import RoleAssignment, UserRole
from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from . import subscriptions
from .models import (
    Cart,
    CartItem,
    Dispute,
    DisputeEvidence,
    DisputeResolution,
    DisputeStatus,
    InventoryMovement,
    InventoryMovementReason,
    Order,
    OrderItem,
    OrderStatus,
    PaymentEventType,
    PaymentStatus,
    Product,
    ProductApprovalStatus,
    Refund,
    RefundStatus,
    Shipment,
    ShipmentStatus,
    SubscriptionStatus,
    SupplierProfile,
    SupplierVerificationStatus,
)


def is_platform_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_platform_admin)


def has_role(user, role) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return RoleAssignment.objects.filter(user=user, role=role, is_active=True).exists()


def get_supplier_profile(user) -> SupplierProfile | None:
    if not user or not user.is_authenticated:
        return None
    return SupplierProfile.objects.filter(user=user).first()


def require_supplier(user) -> SupplierProfile:
    if not has_role(user, UserRole.SUPPLIER):
        raise exceptions.PermissionDenied(
            "Only supplier accounts can manage a catalog.", code="permission_denied"
        )
    profile = get_supplier_profile(user)
    if profile is None:
        raise exceptions.ValidationError(
            {"profile": "Register a supplier profile first."}
        )
    if profile.verification_status == SupplierVerificationStatus.SUSPENDED:
        raise exceptions.PermissionDenied(
            "This supplier account is suspended.", code="permission_denied"
        )
    return profile


def require_buyer(user) -> None:
    if not has_role(user, UserRole.BUYER):
        raise exceptions.PermissionDenied(
            "Only authorized buyers can shop in the marketplace.",
            code="permission_denied",
        )


# ── Supplier profile ───────────────────────────────────────────────────
@transaction.atomic
def register_or_update_profile(user, *, data: dict, request=None) -> SupplierProfile:
    if not has_role(user, UserRole.SUPPLIER):
        raise exceptions.PermissionDenied(
            "Only supplier accounts can register a profile.", code="permission_denied"
        )
    profile = get_supplier_profile(user)
    created = profile is None
    if created:
        profile = SupplierProfile.objects.create(user=user, **data)
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.SUPPLIER_REGISTERED,
            object_type="supplier_profile",
            object_pk=profile.pk,
            metadata={"company_name": profile.company_name},
        )
    else:
        for field, value in data.items():
            setattr(profile, field, value)
        profile.save()
    return profile


# ── Catalog ────────────────────────────────────────────────────────────
def visible_products(user):
    """Public catalog: approved + published products of verified suppliers
    whose seller subscription is currently active (server clock decides)."""
    return Product.objects.filter(
        is_active=True,
        is_published=True,
        approval_status=ProductApprovalStatus.APPROVED,
        supplier__verification_status=SupplierVerificationStatus.VERIFIED,
        supplier__user__seller_subscriptions__status=SubscriptionStatus.ACTIVE,
        supplier__user__seller_subscriptions__expires_at__gt=timezone.now(),
    ).select_related("category", "supplier")


def create_product(profile: SupplierProfile, *, data: dict, request=None) -> Product:
    subscriptions.require_active_subscription(profile.user)
    product = Product.objects.create(supplier=profile, **data)
    record_audit(
        request=request,
        actor=profile.user,
        action=AuditEvent.Action.PRODUCT_LISTED,
        object_type="product",
        object_pk=product.pk,
        metadata={"sku": product.sku, "name": product.name},
    )
    return product


def update_product(profile: SupplierProfile, product: Product, *, data: dict) -> Product:
    if product.supplier_id != profile.pk:
        raise exceptions.NotFound()
    if (
        data.get("is_published")
        and not product.is_published
    ):
        subscriptions.require_active_subscription(profile.user)
    for field, value in data.items():
        setattr(product, field, value)
    product.save()
    return product


def restock(product: Product, quantity: int, *, actor=None, request=None) -> None:
    if quantity <= 0:
        raise exceptions.ValidationError({"quantity": "Use a positive quantity."})
    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product.pk)
        locked.available_quantity += quantity
        locked.save(update_fields=["available_quantity", "updated_at"])
        InventoryMovement.objects.create(
            product=locked,
            delta=quantity,
            reason=InventoryMovementReason.RESTOCKED,
            actor=actor,
        )


# ── Admin verification & approvals ─────────────────────────────────────
@transaction.atomic
def verify_supplier(admin, profile: SupplierProfile, *, approve: bool, request=None):
    if not is_platform_admin(admin):
        raise exceptions.PermissionDenied(
            "Only platform administrators verify suppliers.",
            code="permission_denied",
        )
    profile.verification_status = (
        SupplierVerificationStatus.VERIFIED
        if approve
        else SupplierVerificationStatus.REJECTED
    )
    profile.verified_by = admin
    profile.verified_at = timezone.now()
    profile.save(
        update_fields=[
            "verification_status",
            "verified_by",
            "verified_at",
            "updated_at",
        ]
    )
    record_audit(
        request=request,
        actor=admin,
        action=AuditEvent.Action.SUPPLIER_VERIFIED,
        object_type="supplier_profile",
        object_pk=profile.pk,
        metadata={"approved": approve},
    )
    return profile


def suspend_supplier(admin, profile: SupplierProfile, *, reason: str, request=None):
    if not is_platform_admin(admin):
        raise exceptions.PermissionDenied(
            "Only platform administrators suspend suppliers.",
            code="permission_denied",
        )
    profile.verification_status = SupplierVerificationStatus.SUSPENDED
    profile.suspension_reason = reason
    profile.save(update_fields=["verification_status", "suspension_reason", "updated_at"])
    record_audit(
        request=request,
        actor=admin,
        action=AuditEvent.Action.SUPPLIER_SUSPENDED,
        object_type="supplier_profile",
        object_pk=profile.pk,
        metadata={"reason_provided": bool(reason.strip())},
    )
    return profile


@transaction.atomic
def decide_product(admin, product: Product, *, approve: bool, request=None) -> Product:
    if not is_platform_admin(admin):
        raise exceptions.PermissionDenied(
            "Only platform administrators approve products.",
            code="permission_denied",
        )
    product.approval_status = (
        ProductApprovalStatus.APPROVED
        if approve
        else ProductApprovalStatus.REJECTED
    )
    product.approved_by = admin
    product.approved_at = timezone.now()
    product.save(
        update_fields=["approval_status", "approved_by", "approved_at", "updated_at"]
    )
    record_audit(
        request=request,
        actor=admin,
        action=(
            AuditEvent.Action.PRODUCT_APPROVED
            if approve
            else AuditEvent.Action.PRODUCT_REJECTED
        ),
        object_type="product",
        object_pk=product.pk,
        metadata={"sku": product.sku},
    )
    return product


# ── Cart ───────────────────────────────────────────────────────────────
def get_or_create_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(buyer=user)
    return cart


def add_to_cart(user, *, product: Product, quantity: int, request=None) -> CartItem:
    require_buyer(user)
    if quantity <= 0:
        raise exceptions.ValidationError({"quantity": "Use a positive quantity."})
    if not product.is_sellable:
        raise exceptions.ValidationError(
            {"product": "This product is not available for sale."}
        )
    if quantity > product.free_quantity:
        raise exceptions.ValidationError(
            {"quantity": f"Only {product.free_quantity} unit(s) available."}
        )
    cart = get_or_create_cart(user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])
    return item


def update_cart_item(user, item: CartItem, *, quantity: int) -> CartItem:
    require_buyer(user)
    if item.cart.buyer_id != user.pk:
        raise exceptions.NotFound()
    if quantity <= 0:
        raise exceptions.ValidationError({"quantity": "Use a positive quantity."})
    if not item.product.is_sellable or quantity > item.product.free_quantity:
        raise exceptions.ValidationError(
            {"quantity": "Not enough available stock for this quantity."}
        )
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


def remove_cart_item(user, item: CartItem) -> None:
    require_buyer(user)
    if item.cart.buyer_id != user.pk:
        raise exceptions.NotFound()
    item.delete()


# ── Checkout & orders ──────────────────────────────────────────────────
def release_stock(order: Order, *, actor) -> None:
    """Give reserved units back to available stock (no status change)."""
    for item in order.items.select_related("product"):
        if item.product is None:
            continue
        product = Product.objects.select_for_update().get(pk=item.product.pk)
        product.reserved_quantity = max(product.reserved_quantity - item.quantity, 0)
        product.save(update_fields=["reserved_quantity", "updated_at"])
        InventoryMovement.objects.create(
            product=product,
            delta=-item.quantity,
            reason=InventoryMovementReason.RELEASED,
            order=order,
            actor=actor,
        )


@transaction.atomic
def checkout(user, *, shipping: dict, request=None) -> list[Order]:
    """Reserve stock and create one order per supplier; prices are snapshotted."""
    require_buyer(user)
    cart = get_or_create_cart(user)
    items = list(cart.items.select_related("product", "product__supplier"))
    if not items:
        raise exceptions.ValidationError({"cart": "Your cart is empty."})

    problems: dict[str, str] = {}
    for item in items:
        product = Product.objects.select_for_update().get(pk=item.product_id)
        if not product.is_sellable:
            problems[str(product.pk)] = "This product is no longer for sale."
        elif item.quantity > product.free_quantity:
            problems[str(product.pk)] = (
                f"Only {product.free_quantity} unit(s) left for {product.sku}."
            )
    if problems:
        raise exceptions.ValidationError({"items": problems})

    by_supplier: dict = {}
    for item in items:
        product = Product.objects.select_for_update().get(pk=item.product_id)
        by_supplier.setdefault(product.supplier_id, []).append((item, product))

    orders: list[Order] = []
    for supplier_id, rows in by_supplier.items():
        subtotal = sum(item.quantity * product.unit_price for item, product in rows)
        order = Order.objects.create(
            buyer=user,
            supplier_id=supplier_id,
            subtotal=subtotal,
            total=subtotal,
            shipping_name=shipping.get("name", ""),
            shipping_address=shipping.get("address", ""),
            shipping_phone=shipping.get("phone", ""),
        )
        for item, product in rows:
            product.reserved_quantity += item.quantity
            product.save(update_fields=["reserved_quantity", "updated_at"])
            InventoryMovement.objects.create(
                product=product,
                delta=item.quantity,
                reason=InventoryMovementReason.RESERVED,
                order=order,
                actor=user,
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_sku=product.sku,
                product_description=product.description,
                quantity=item.quantity,
                unit_price=product.unit_price,
                line_total=item.quantity * product.unit_price,
            )
        record_audit(
            request=request,
            actor=user,
            action=AuditEvent.Action.ORDER_PLACED,
            object_type="order",
            object_pk=order.pk,
            metadata={
                "reference": order.reference,
                "supplier": order.supplier.company_name,
                "total": str(order.total),
            },
        )
        orders.append(order)
    cart.items.all().delete()
    return orders


@transaction.atomic
def cancel_order(order: Order, *, actor, reason: str = "", request=None) -> Order:
    if not order.is_cancellable:
        raise exceptions.ValidationError(
            {"status": f"An order in status '{order.status}' cannot be cancelled."}
        )
    is_owner = order.buyer_id == getattr(actor, "pk", None)
    if not is_owner and not is_platform_admin(actor):
        raise exceptions.PermissionDenied(
            "Only the buyer or a platform administrator can cancel this order.",
            code="permission_denied",
        )
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason[:255]
    order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    release_stock(order, actor=actor)
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.ORDER_CANCELLED,
        object_type="order",
        object_pk=order.pk,
        metadata={"reference": order.reference, "reason_provided": bool(reason.strip())},
    )
    return order


def visible_orders(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Order.objects.none()
    if user.is_platform_admin:
        return Order.objects.all()
    profile = get_supplier_profile(user)
    if profile is not None:
        return Order.objects.filter(buyer=user) | Order.objects.filter(supplier=profile)
    return Order.objects.filter(buyer=user)


# ── Shipping ───────────────────────────────────────────────────────────
def ship_order(order: Order, *, actor, tracking_number: str = "", request=None):
    profile = require_supplier(actor)
    if order.supplier_id != profile.pk:
        raise exceptions.NotFound()
    if order.status != OrderStatus.PAID:
        raise exceptions.ValidationError(
            {"status": "Only a paid order can be shipped."}
        )
    shipment = Shipment.objects.create(
        order=order,
        tracking_number=tracking_number[:100],
        shipped_by=actor,
    )
    order.status = OrderStatus.SHIPPED
    order.save(update_fields=["status", "updated_at"])
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.SHIPMENT_SHIPPED,
        object_type="order",
        object_pk=order.pk,
        metadata={
            "reference": order.reference,
            "tracking_provided": bool(tracking_number.strip()),
        },
    )
    return shipment


def deliver_order(order: Order, *, actor, request=None):
    profile = require_supplier(actor)
    if order.supplier_id != profile.pk:
        raise exceptions.NotFound()
    shipment = Shipment.objects.filter(order=order).first()
    if shipment is None or shipment.status != ShipmentStatus.SHIPPED:
        raise exceptions.ValidationError(
            {"status": "Only a shipped order can be marked as delivered."}
        )
    shipment.status = ShipmentStatus.DELIVERED
    shipment.delivered_at = timezone.now()
    shipment.save(update_fields=["status", "delivered_at", "updated_at"])
    order.status = OrderStatus.DELIVERED
    order.save(update_fields=["status", "updated_at"])
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.SHIPMENT_DELIVERED,
        object_type="order",
        object_pk=order.pk,
        metadata={"reference": order.reference},
    )
    return shipment


# ── Refunds ────────────────────────────────────────────────────────────
REFUNDABLE_STATUSES = frozenset(
    {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED}
)


def request_refund(order: Order, *, buyer, reason: str = "", request=None) -> Refund:
    from .payments import log_payment_event

    require_buyer(buyer)
    if order.buyer_id != buyer.pk:
        raise exceptions.NotFound()
    if order.status not in REFUNDABLE_STATUSES:
        raise exceptions.ValidationError(
            {"status": f"An order in status '{order.status}' cannot be refunded."}
        )
    payment = order.payments.filter(status=PaymentStatus.SUCCEEDED).first()
    if payment is None:
        raise exceptions.ValidationError(
            {"payment": "No settled payment exists for this order."}
        )
    try:
        refund = Refund.objects.create(
            order=order,
            payment=payment,
            amount=payment.amount,
            currency=payment.currency,
            reason=reason[:4000],
            requested_by=buyer,
        )
    except IntegrityError:
        raise exceptions.ValidationError(
            {"refund": "A refund request is already pending for this order."}
        ) from None
    log_payment_event(
        payment, PaymentEventType.REFUND_REQUESTED, payload={"refund_id": str(refund.pk)}
    )
    record_audit(
        request=request,
        actor=buyer,
        action=AuditEvent.Action.REFUND_REQUESTED,
        object_type="refund",
        object_pk=refund.pk,
        metadata={"reference": order.reference, "reason_provided": bool(reason.strip())},
    )
    return refund


def decide_refund(
    refund: Refund, *, actor, approved: bool, decision_reason: str = "", request=None
) -> Refund:
    from .payments import log_payment_event, settle_refund

    if not has_role(actor, UserRole.SUPPLIER):
        raise exceptions.PermissionDenied(
            "Only the supplier can decide refunds.", code="permission_denied"
        )
    profile = get_supplier_profile(actor)
    if profile is None or refund.order.supplier_id != profile.pk:
        raise exceptions.NotFound()
    if refund.status != RefundStatus.PENDING:
        raise exceptions.ValidationError(
            {"status": "This refund request has already been decided."}
        )
    refund.decided_by = actor
    refund.decided_at = timezone.now()
    refund.decision_reason = decision_reason[:255]
    if not approved:
        refund.status = RefundStatus.REJECTED
        refund.save()
        log_payment_event(
            refund.payment,
            PaymentEventType.REFUND_REJECTED,
            payload={"refund_id": str(refund.pk)},
        )
        record_audit(
            request=request,
            actor=actor,
            action=AuditEvent.Action.REFUND_REJECTED,
            object_type="refund",
            object_pk=refund.pk,
            metadata={"reference": refund.order.reference},
        )
        return refund
    refund.status = RefundStatus.COMPLETED
    refund.save()
    settle_refund(refund, actor=actor, request=request)
    return refund


# ── Disputes ───────────────────────────────────────────────────────────
DISPUTABLE_STATUSES = REFUNDABLE_STATUSES


def is_order_party(user, order) -> bool:
    if not user or not user.is_authenticated:
        return False
    if order.buyer_id == user.pk:
        return True
    return order.supplier.user_id == user.pk


def open_dispute(order: Order, *, user, description: str, request=None) -> Dispute:
    if not description.strip():
        raise exceptions.ValidationError(
            {"description": "Describe the problem before opening a dispute."}
        )
    if not is_order_party(user, order):
        raise exceptions.NotFound()
    if order.status not in DISPUTABLE_STATUSES:
        raise exceptions.ValidationError(
            {"status": f"An order in status '{order.status}' cannot be disputed."}
        )
    if Dispute.objects.filter(order=order).exists():
        raise exceptions.ValidationError(
            {"dispute": "A dispute already exists for this order."}
        )
    dispute = Dispute.objects.create(
        order=order, opened_by=user, description=description
    )
    record_audit(
        request=request,
        actor=user,
        action=AuditEvent.Action.DISPUTE_OPENED,
        object_type="dispute",
        object_pk=dispute.pk,
        metadata={"reference": order.reference},
    )
    return dispute


def add_dispute_evidence(
    dispute: Dispute, *, user, body: str, file=None, request=None
) -> DisputeEvidence:
    if not is_order_party(user, dispute.order):
        raise exceptions.NotFound()
    if dispute.status != DisputeStatus.OPEN:
        raise exceptions.ValidationError(
            {"dispute": "Evidence can only be added while the dispute is open."}
        )
    if not body.strip() and file is None:
        raise exceptions.ValidationError(
            {"evidence": "Provide a description, a file, or both."}
        )
    evidence = DisputeEvidence.objects.create(
        dispute=dispute, author=user, body=body, file=file or ""
    )
    record_audit(
        request=request,
        actor=user,
        action=AuditEvent.Action.DISPUTE_EVIDENCE_ADDED,
        object_type="dispute",
        object_pk=dispute.pk,
        metadata={"reference": dispute.order.reference, "has_file": bool(file)},
    )
    return evidence


def resolve_dispute(
    dispute: Dispute,
    *,
    actor,
    resolution: str,
    note: str = "",
    request=None,
) -> Dispute:
    from .payments import refund_for_dispute

    if not is_platform_admin(actor):
        raise exceptions.PermissionDenied(
            "Only platform administrators resolve disputes.",
            code="permission_denied",
        )
    if dispute.status != DisputeStatus.OPEN:
        raise exceptions.ValidationError(
            {"status": "This dispute has already been resolved."}
        )
    if resolution not in DisputeResolution.values:
        raise exceptions.ValidationError(
            {"resolution": "Expected 'buyer_favored' or 'supplier_favored'."}
        )
    dispute.status = DisputeStatus.RESOLVED
    dispute.resolution = resolution
    dispute.resolution_note = note[:4000]
    dispute.resolved_by = actor
    dispute.resolved_at = timezone.now()
    dispute.save()
    if resolution == DisputeResolution.BUYER_FAVORED:
        refund_for_dispute(dispute, actor=actor, request=request)
    record_audit(
        request=request,
        actor=actor,
        action=AuditEvent.Action.DISPUTE_RESOLVED,
        object_type="dispute",
        object_pk=dispute.pk,
        metadata={"reference": dispute.order.reference, "resolution": resolution},
    )
    return dispute

