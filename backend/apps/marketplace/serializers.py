from __future__ import annotations

from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer

from .models import (
    CartItem,
    Order,
    OrderItem,
    Product,
    ProductCategory,
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


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    buyer_detail = UserSummarySerializer(source="buyer", read_only=True)
    supplier_name = serializers.CharField(source="supplier.company_name", read_only=True)

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
            "cancelled_at",
            "cancel_reason",
            "items",
        ]
        read_only_fields = fields


class ShippingSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, allow_blank=True, required=False)
    address = serializers.CharField(allow_blank=True, required=False)
    phone = serializers.CharField(max_length=40, allow_blank=True, required=False)


class CheckoutSerializer(serializers.Serializer):
    shipping = ShippingSerializer(required=False)
