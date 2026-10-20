from __future__ import annotations

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import (
    CartItem,
    Dispute,
    DisputeEvidence,
    Order,
    OrderItem,
    Payment,
    PaymentEvent,
    Product,
    ProductCategory,
    Refund,
    SellerSubscription,
    Shipment,
    SupplierProfile,
)


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "slug", "is_active"]


class SupplierProfileSerializer(serializers.ModelSerializer):
    user_detail = UserSummarySerializer(source="user", read_only=True)

    class Meta:
        model = SupplierProfile
        fields = [
            "id",
            "user",
            "user_detail",
            "company_name",
            "contact_email",
            "contact_phone",
            "address",
            "commercial_notes",
            "verification_status",
            "verified_at",
            "suspension_reason",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "verification_status",
            "verified_at",
            "suspension_reason",
            "created_at",
        ]


class ProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    free_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "category",
            "category_name",
            "name",
            "description",
            "sku",
            "unit_price",
            "currency",
            "available_quantity",
            "reserved_quantity",
            "free_quantity",
            "is_published",
            "approval_status",
            "specifications",
            "regulatory_notes",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "supplier",
            "reserved_quantity",
            "free_quantity",
            "approval_status",
            "created_at",
        ]


class CartItemSerializer(serializers.ModelSerializer):
    product_detail = ProductSerializer(source="product", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_detail", "quantity", "line_total"]

    def get_line_total(self, obj) -> str:
        return str(obj.line_total)


class CartItemCreateSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "product_description",
            "quantity",
            "unit_price",
            "line_total",
        ]


# ── Subscription (M8) ─────────────────────────────────────────────────
class SubscriptionCheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["monthly", "semiannual", "annual"])
    idempotency_key = serializers.CharField(
        max_length=64, allow_blank=True, required=False, default=""
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerSubscription
        fields = [
            "id",
            "reference",
            "plan",
            "status",
            "amount",
            "currency",
            "starts_at",
            "expires_at",
            "created_at",
        ]
        read_only_fields = fields


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    subscription_detail = SubscriptionSerializer(source="subscription", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "subscription",
            "subscription_detail",
            "provider",
            "status",
            "amount",
            "currency",
            "provider_reference",
            "failure_reason",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class ShippingSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, allow_blank=True, required=False)
    address = serializers.CharField(allow_blank=True, required=False)
    phone = serializers.CharField(max_length=40, allow_blank=True, required=False)


class CheckoutSerializer(serializers.Serializer):
    shipping = ShippingSerializer(required=False)


# ── Payments / shipments / refunds / disputes (M5b) ───────────────────
class PaymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentEvent
        fields = ["id", "event_type", "payload", "signature_valid", "created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    events = PaymentEventSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "subscription",
            "provider",
            "status",
            "amount",
            "currency",
            "idempotency_key",
            "provider_reference",
            "failure_reason",
            "paid_at",
            "events",
            "created_at",
        ]
        read_only_fields = fields


class SimulatePaymentSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["succeeded", "failed"])


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = [
            "id",
            "status",
            "tracking_number",
            "shipped_at",
            "delivered_at",
        ]
        read_only_fields = fields


class ShipSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(
        max_length=100, allow_blank=True, required=False
    )


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            "id",
            "order",
            "payment",
            "status",
            "amount",
            "currency",
            "reason",
            "decision_reason",
            "requested_by",
            "decided_by",
            "decided_at",
            "created_at",
        ]
        read_only_fields = fields


class RefundRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=True, required=False, default="")


class RefundDecideSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True, required=False, default="")


class DisputeEvidenceSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = DisputeEvidence
        fields = ["id", "author", "body", "file", "file_name", "created_at"]
        read_only_fields = ["id", "author", "created_at", "file_name"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_file_name(self, obj) -> str | None:
        # Private storage never exposes a URL; the name links to the
        # authenticated download endpoint instead.
        return obj.file.name.rsplit("/", 1)[-1] if obj.file else None


class DisputeSerializer(serializers.ModelSerializer):
    evidence_entries = DisputeEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = Dispute
        fields = [
            "id",
            "order",
            "opened_by",
            "status",
            "description",
            "resolution",
            "resolution_note",
            "resolved_by",
            "resolved_at",
            "evidence_entries",
            "created_at",
        ]
        read_only_fields = fields


class DisputeCreateSerializer(serializers.Serializer):
    description = serializers.CharField()


class DisputeResolveSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(
        choices=["buyer_favored", "supplier_favored"]
    )
    note = serializers.CharField(allow_blank=True, required=False, default="")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    buyer_detail = UserSummarySerializer(source="buyer", read_only=True)
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    shipment = serializers.SerializerMethodField()
    dispute = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "reference",
            "buyer",
            "buyer_detail",
            "supplier",
            "supplier_name",
            "status",
            "currency",
            "subtotal",
            "total",
            "shipping_name",
            "shipping_address",
            "shipping_phone",
            "placed_at",
            "paid_at",
            "cancelled_at",
            "cancel_reason",
            "items",
            "payments",
            "refunds",
            "shipment",
            "dispute",
        ]
        read_only_fields = fields

    def get_shipment(self, obj):
        shipment = getattr(obj, "shipment", None)
        return ShipmentSerializer(shipment).data if shipment else None

    def get_dispute(self, obj):
        dispute = getattr(obj, "dispute", None)
        return DisputeSerializer(dispute).data if dispute else None
