from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("marketplace/categories/", views.CategoryListView.as_view(), name="categories"),
    path("marketplace/products/", views.ProductListView.as_view(), name="products"),
    path(
        "marketplace/products/<uuid:pk>/",
        views.ProductDetailView.as_view(),
        name="product-detail",
    ),
    path(
        "marketplace/supplier/profile/",
        views.SupplierProfileView.as_view(),
        name="supplier-profile",
    ),
    path(
        "marketplace/supplier/products/",
        views.SupplierProductListCreateView.as_view(),
        name="supplier-products",
    ),
    path(
        "marketplace/supplier/products/<uuid:pk>/",
        views.SupplierProductDetailView.as_view(),
        name="supplier-product-detail",
    ),
    path(
        "marketplace/supplier/products/<uuid:pk>/restock/",
        views.SupplierRestockView.as_view(),
        name="supplier-restock",
    ),
    path("marketplace/admin/suppliers/", views.AdminSupplierListView.as_view()),
    path(
        "marketplace/admin/suppliers/<uuid:pk>/<str:action>/",
        views.AdminSupplierDecideView.as_view(),
    ),
    path("marketplace/admin/products/", views.AdminProductListView.as_view()),
    path(
        "marketplace/admin/products/<uuid:pk>/<str:action>/",
        views.AdminProductDecideView.as_view(),
    ),
    path(
        "marketplace/admin/categories/",
        views.AdminCategoryListCreateView.as_view(),
    ),
    path("marketplace/cart/", views.CartView.as_view(), name="cart"),
    path("marketplace/cart/items/", views.CartItemCreateView.as_view()),
    path("marketplace/cart/items/<uuid:pk>/", views.CartItemDetailView.as_view()),
    path("marketplace/checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("marketplace/orders/", views.OrderListView.as_view(), name="orders"),
    path(
        "marketplace/orders/<uuid:pk>/", views.OrderDetailView.as_view(), name="order-detail"
    ),
    path(
        "marketplace/orders/<uuid:pk>/cancel/",
        views.OrderCancelView.as_view(),
        name="order-cancel",
    ),
]
