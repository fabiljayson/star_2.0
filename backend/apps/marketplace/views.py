from __future__ import annotations

import json
import mimetypes

from django.db.models import Q
from django.http import FileResponse
from rest_framework import exceptions, generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole

from . import payments, services, subscriptions
from .models import (
    CartItem,
    Dispute,
    Payment,
    Product,
    ProductCategory,
    Refund,
    SellerSubscription,
    SupplierProfile,
)
from .serializers import (
    CartItemCreateSerializer,
    CartItemSerializer,
    CheckoutSerializer,
    DisputeCreateSerializer,
    DisputeEvidenceSerializer,
    DisputeResolveSerializer,
    DisputeSerializer,
    OrderSerializer,
    PaymentSerializer,
    ProductCategorySerializer,
    ProductSerializer,
    RefundDecideSerializer,
    RefundRequestSerializer,
    RefundSerializer,
    ShipmentSerializer,
    ShipSerializer,
    SimulatePaymentSerializer,
    SubscriptionCheckoutSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionSerializer,
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

    def perform_update(self, serializer):
        wants_publish = bool(serializer.validated_data.get("is_published"))
        if wants_publish and not serializer.instance.is_published:
            subscriptions.require_active_subscription(self.request.user)
        serializer.save()

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


# ── Payments (M5b) ─────────────────────────────────────────────────────
class OrderPayView(APIView):
    def post(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        if order.buyer_id != request.user.pk:
            raise exceptions.PermissionDenied(
                "Only the buyer can pay for this order.", code="permission_denied"
            )
        idempotency_key = request.headers.get("Idempotency-Key", "") or str(
            request.data.get("idempotency_key", "")
        )
        payment, created = payments.initiate_payment(
            order,
            buyer=request.user,
            idempotency_key=idempotency_key,
            request=request,
        )
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PaymentDetailView(APIView):
    def get(self, request, pk):
        if services.is_platform_admin(request.user):
            payment = Payment.objects.filter(pk=pk).first()
        else:
            payment = (
                Payment.objects.filter(pk=pk)
                .filter(
                    Q(order__buyer=request.user)
                    | Q(order__supplier__user=request.user)
                )
                .first()
            )
        if payment is None:
            raise exceptions.NotFound()
        return Response(PaymentSerializer(payment).data)


class PaymentSimulateView(APIView):
    """Sandbox provider stand-in: delivers a signed webhook to the real handler."""

    def post(self, request, pk):
        if not services.is_platform_admin(request.user):
            raise exceptions.PermissionDenied(
                "Only platform administrators trigger sandbox outcomes.",
                code="permission_denied",
            )
        payment = Payment.objects.filter(pk=pk).first()
        if payment is None:
            raise exceptions.NotFound()
        serializer = SimulatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = payments.simulate_payment(
                payment,
                outcome=serializer.validated_data["outcome"],
                request=request,
            )
        except exceptions.ValidationError:
            raise
        return Response(PaymentSerializer(payment).data)


class PaymentWebhookView(APIView):
    """Provider callback; signature over the canonical JSON body decides truth."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise exceptions.ValidationError(
                {"payload": "Expected a JSON object."}
            ) from None
        signature = request.headers.get(payments.WEBHOOK_SIGNATURE_HEADER, "")
        payment = payments.apply_webhook(payload, signature, request=request)
        return Response(
            {"payment": str(payment.pk), "status": payment.status}
        )


# ── Seller subscription (M8) ──────────────────────────────────────────
class SubscriptionStatusView(APIView):
    def get(self, request):
        payload = subscriptions.status_payload(request.user)
        plans = [
            {
                "plan": plan,
                "price_fcfa": subscriptions.price_for(request.user, plan),
                "duration_months": subscriptions.PLAN_MONTHS[plan],
            }
            for plan in (
                subscriptions.PLAN_MONTHLY,
                subscriptions.PLAN_SEMIANNUAL,
                subscriptions.PLAN_ANNUAL,
            )
        ]
        payload["plans"] = plans
        return Response(payload)


class SubscriptionCheckoutView(APIView):
    def post(self, request):
        serializer = SubscriptionCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription, payment, created = subscriptions.start_checkout(
            request.user,
            plan=serializer.validated_data["plan"],
            idempotency_key=serializer.validated_data.get("idempotency_key", ""),
            request=request,
        )
        return Response(
            SubscriptionPaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SubscriptionPaymentDetailView(APIView):
    def get(self, request, pk):
        payment = Payment.objects.filter(
            pk=pk, subscription__user=request.user
        ).first()
        if payment is None:
            raise exceptions.NotFound()
        return Response(SubscriptionPaymentSerializer(payment).data)


class SubscriptionHistoryView(generics.ListAPIView):
    serializer_class = SubscriptionSerializer
    pagination_class = None
    ordering = ["-created_at"]

    def get_queryset(self):
        return SellerSubscription.objects.filter(user=self.request.user)


# ── Shipping (M5b) ─────────────────────────────────────────────────────
class OrderShipView(APIView):
    def post(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        serializer = ShipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipment = services.ship_order(
            order,
            actor=request.user,
            tracking_number=serializer.validated_data.get("tracking_number", ""),
            request=request,
        )
        return Response(ShipmentSerializer(shipment).data, status=201)


class OrderDeliverView(APIView):
    def post(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        shipment = services.deliver_order(order, actor=request.user, request=request)
        return Response(ShipmentSerializer(shipment).data)


# ── Refunds (M5b) ──────────────────────────────────────────────────────
class OrderRefundRequestView(APIView):
    def post(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = services.request_refund(
            order,
            buyer=request.user,
            reason=serializer.validated_data.get("reason", ""),
            request=request,
        )
        return Response(RefundSerializer(refund).data, status=201)


class RefundDecideView(APIView):
    def _refund(self, user, pk):
        if not services.has_role(user, UserRole.SUPPLIER):
            raise exceptions.PermissionDenied(
                "Only the supplier can decide refunds.", code="permission_denied"
            )
        refund = Refund.objects.filter(pk=pk).select_related("order").first()
        if refund is None:
            raise exceptions.NotFound()
        profile = services.get_supplier_profile(user)
        if profile is None or refund.order.supplier_id != profile.pk:
            raise exceptions.NotFound()
        return refund

    def post(self, request, pk):
        refund = self._refund(request.user, pk)
        serializer = RefundDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = services.decide_refund(
            refund,
            actor=request.user,
            approved=serializer.validated_data["approved"],
            decision_reason=serializer.validated_data.get("reason", ""),
            request=request,
        )
        return Response(RefundSerializer(refund).data)


# ── Disputes (M5b) ─────────────────────────────────────────────────────
class OrderDisputeView(APIView):
    def get(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        dispute = Dispute.objects.filter(order=order).first()
        if dispute is None:
            raise exceptions.NotFound()
        return Response(DisputeSerializer(dispute).data)

    def post(self, request, pk):
        order = services.visible_orders(request.user).filter(pk=pk).first()
        if order is None:
            raise exceptions.NotFound()
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispute = services.open_dispute(
            order,
            user=request.user,
            description=serializer.validated_data["description"],
            request=request,
        )
        return Response(DisputeSerializer(dispute).data, status=201)


class DisputeDetailView(APIView):
    def get(self, request, pk):
        if services.is_platform_admin(request.user):
            dispute = Dispute.objects.filter(pk=pk).first()
        else:
            dispute = (
                Dispute.objects.filter(pk=pk)
                .filter(
                    Q(order__buyer=request.user)
                    | Q(order__supplier__user=request.user)
                )
                .first()
            )
        if dispute is None:
            raise exceptions.NotFound()
        return Response(DisputeSerializer(dispute).data)


class DisputeEvidenceView(APIView):
    def post(self, request, pk):
        dispute = Dispute.objects.filter(pk=pk).first()
        if dispute is None:
            raise exceptions.NotFound()
        serializer = DisputeEvidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evidence = services.add_dispute_evidence(
            dispute,
            user=request.user,
            body=serializer.validated_data.get("body", ""),
            file=serializer.validated_data.get("file"),
            request=request,
        )
        return Response(DisputeEvidenceSerializer(evidence).data, status=201)


class DisputeEvidenceDownloadView(APIView):
    def get(self, request, pk, evidence_id):
        dispute = Dispute.objects.filter(pk=pk).first()
        if dispute is None:
            raise exceptions.NotFound()
        if not (
            services.is_platform_admin(request.user)
            or services.is_order_party(request.user, dispute.order)
        ):
            raise exceptions.NotFound()
        evidence = dispute.evidence_entries.filter(pk=evidence_id).first()
        if evidence is None or not evidence.file:
            raise exceptions.NotFound()
        if not evidence.file.storage.exists(evidence.file.name):
            raise exceptions.NotFound("File content is no longer available.")
        filename = evidence.file.name.rsplit("/", 1)[-1]
        content_type, _ = mimetypes.guess_type(filename)
        response = FileResponse(
            evidence.file.open("rb"),
            as_attachment=True,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class DisputeResolveView(APIView):
    def post(self, request, pk):
        dispute = Dispute.objects.filter(pk=pk).first()
        if dispute is None:
            raise exceptions.NotFound()
        serializer = DisputeResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispute = services.resolve_dispute(
            dispute,
            actor=request.user,
            resolution=serializer.validated_data["resolution"],
            note=serializer.validated_data.get("note", ""),
            request=request,
        )
        return Response(DisputeSerializer(dispute).data)


class DisputeListView(generics.ListAPIView):
    serializer_class = DisputeSerializer
    ordering = ["-created_at"]

    def get_queryset(self):
        if not services.is_platform_admin(self.request.user):
            raise exceptions.PermissionDenied(
                "Only platform administrators list all disputes.",
                code="permission_denied",
            )
        queryset = Dispute.objects.all()
        open_only = self.request.query_params.get("status")
        if open_only:
            queryset = queryset.filter(status=open_only)
        return queryset
