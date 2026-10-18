from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import RoleAssignment, UserRole
from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from .models import (
    Cart,
    CartItem,
    InventoryMovement,
    InventoryMovementReason,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductApprovalStatus,
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
    """Public catalog: approved + published products of verified suppliers."""
    return Product.objects.filter(
        is_active=True,
        is_published=True,
        approval_status=ProductApprovalStatus.APPROVED,
        supplier__verification_status=SupplierVerificationStatus.VERIFIED,
    ).select_related("category", "supplier")


def create_product(profile: SupplierProfile, *, data: dict, request=None) -> Product:
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
    profile = get_supplier_profile(user)
    if profile is not None:
        return Order.objects.filter(buyer=user) | Order.objects.filter(supplier=profile)
    return Order.objects.filter(buyer=user)
