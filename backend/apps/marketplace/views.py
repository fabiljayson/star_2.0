from __future__ import annotations

from django.db.models import Q
from rest_framework import exceptions, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import CartItem, Product, ProductCategory, SupplierProfile
from .serializers import (
    CartItemCreateSerializer,
    CartItemSerializer,
    CheckoutSerializer,
    OrderSerializer,
    ProductCategorySerializer,
    ProductSerializer,
    SupplierProfileSerializer,
)


class CategoryListView(generics.ListAPIView):
    serializer_class = ProductCategorySerializer
    queryset = ProductCategory.objects.filter(is_active=True)
    pagination_class = None


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    ordering_fields = ["name", "unit_price", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = services.visible_products(self.request.user)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        search = self.request.query_params.get("q")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(sku__icontains=search)
            )
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer

    def get_object(self):
        product = (
            services.visible_products(self.request.user)
            .filter(pk=self.kwargs["pk"])
            .first()
        )
        if product is None:
            raise exceptions.NotFound()
        return product


# ── Supplier catalog ───────────────────────────────────────────────────
class SupplierProfileView(APIView):
    def get(self, request):
        profile = services.get_supplier_profile(request.user)
        if profile is None:
            return Response({"detail": "No supplier profile yet."}, status=404)
        return Response(SupplierProfileSerializer(profile).data)

    def post(self, request):
        serializer = SupplierProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = services.register_or_update_profile(
            request.user, data=serializer.validated_data, request=request
        )
        return Response(
            SupplierProfileSerializer(profile).data, status=status.HTTP_201_CREATED
        )

    def patch(self, request):
        profile = services.get_supplier_profile(request.user)
        if profile is None:
            raise exceptions.NotFound()
        serializer = SupplierProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = services.register_or_update_profile(
            request.user, data=serializer.validated_data, request=request
        )
        return Response(SupplierProfileSerializer(profile).data)


class SupplierProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        profile = services.get_supplier_profile(self.request.user)
        if profile is None:
            return Product.objects.none()
        return profile.products.select_related("category", "supplier")

    def create(self, request, *args, **kwargs):
        profile = services.require_supplier(request.user)
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(
            profile, data=serializer.validated_data, request=request
        )
        return Response(ProductSerializer(product).data, status=201)


class SupplierProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer

    def get_object(self):
        profile = services.require_supplier(self.request.user)
        product = profile.products.filter(pk=self.kwargs["pk"]).first()
        if product is None:
            raise exceptions.NotFound()
        return product

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_published = False
        instance.save(update_fields=["is_active", "is_published", "updated_at"])


class SupplierRestockView(APIView):
    def post(self, request, pk):
        profile = services.require_supplier(request.user)
        product = profile.products.filter(pk=pk).first()
        if product is None:
            raise exceptions.NotFound()
        quantity = request.data.get("quantity")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise exceptions.ValidationError(
                {"quantity": "Expected a positive integer."}
            ) from None
        services.restock(product, quantity, actor=request.user, request=request)
        product.refresh_from_db()
        return Response(ProductSerializer(product).data)


# ── Platform admin ─────────────────────────────────────────────────────
class AdminSupplierListView(generics.ListAPIView):
    serializer_class = SupplierProfileSerializer
    queryset = SupplierProfile.objects.all().select_related("user")
    ordering = ["company_name"]
    pagination_class = None


class AdminSupplierDecideView(APIView):
    def _profile(self, pk):
        profile = SupplierProfile.objects.filter(pk=pk).first()
        if profile is None:
            raise exceptions.NotFound()
        return profile

    def post(self, request, pk, action):
        profile = self._profile(pk)
        if action == "verify":
            profile = services.verify_supplier(
                request.user, profile, approve=True, request=request
            )
        elif action == "reject":
            profile = services.verify_supplier(
                request.user, profile, approve=False, request=request
            )
        elif action == "suspend":
            profile = services.suspend_supplier(
                request.user,
                profile,
                reason=str(request.data.get("reason", "")),
                request=request,
            )
        else:
            raise exceptions.NotFound()
        return Response(SupplierProfileSerializer(profile).data)


class AdminProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.filter(is_active=True).select_related(
        "category", "supplier"
    )
    ordering = ["created_at"]


class AdminProductDecideView(APIView):
    def post(self, request, pk, action):
        product = Product.objects.filter(pk=pk, is_active=True).first()
        if product is None:
            raise exceptions.NotFound()
        if action not in {"approve", "reject"}:
            raise exceptions.NotFound()
        product = services.decide_product(
            request.user, product, approve=action == "approve", request=request
        )
        return Response(ProductSerializer(product).data)


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductCategorySerializer
    queryset = ProductCategory.objects.all()

    def perform_create(self, serializer):
        if not services.is_platform_admin(self.request.user):
            raise exceptions.PermissionDenied(
                "Only platform administrators manage categories.",
                code="permission_denied",
            )
        serializer.save()


# ── Cart & checkout ────────────────────────────────────────────────────
class CartView(generics.ListAPIView):
    serializer_class = CartItemSerializer

    def get_queryset(self):
        services.require_buyer(self.request.user)
        cart = services.get_or_create_cart(self.request.user)
        return cart.items.select_related("product", "product__supplier")


class CartItemCreateView(APIView):
    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = services.add_to_cart(
            request.user,
            product=serializer.validated_data["product"],
            quantity=serializer.validated_data["quantity"],
            request=request,
        )
        return Response(CartItemSerializer(item).data, status=201)


class CartItemDetailView(APIView):
    def _item(self, request, pk):
        item = CartItem.objects.filter(pk=pk).first()
        if item is None:
            raise exceptions.NotFound()
        return item

    def patch(self, request, pk):
        item = self._item(request, pk)
        try:
            quantity = int(request.data.get("quantity"))
        except (TypeError, ValueError):
            raise exceptions.ValidationError(
                {"quantity": "Expected a positive integer."}
            ) from None
        item = services.update_cart_item(request.user, item, quantity=quantity)
        return Response(CartItemSerializer(item).data)

    def delete(self, request, pk):
        item = self._item(request, pk)
        services.remove_cart_item(request.user, item)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(APIView):
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipping = serializer.validated_data.get("shipping", {})
        orders = services.checkout(request.user, shipping=shipping, request=request)
        return Response(
            OrderSerializer(orders, many=True).data, status=status.HTTP_201_CREATED
        )


# ── Orders ─────────────────────────────────────────────────────────────
class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    ordering_fields = ["placed_at", "status", "total"]
    ordering = ["-placed_at"]

    def get_queryset(self):
        return services.visible_orders(self.request.user).prefetch_related("items")


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer

    def get_object(self):
        order = (
            services.visible_orders(self.request.user)
            .filter(pk=self.kwargs["pk"])
            .prefetch_related("items")
            .first()
        )
        if order is None:
            raise exceptions.NotFound()
        return order


class OrderCancelView(APIView):
    def post(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        order = services.cancel_order(
            order,
            actor=request.user,
            reason=str(request.data.get("reason", "")),
            request=request,
        )
        return Response(OrderSerializer(order).data)
