from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    InventoryMovement,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    SupplierProfile,
)


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "verification_status", "created_at")
    list_filter = ("verification_status",)
    search_fields = ("company_name", "contact_email", "user__email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "unit_price", "approval_status", "is_published")
    list_filter = ("approval_status", "is_published")
    search_fields = ("name", "sku")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "status", "total", "placed_at")
    list_filter = ("status",)
    search_fields = ("reference", "buyer__email")


admin.site.register([ProductCategory, Cart, CartItem, OrderItem, InventoryMovement])
