from django.urls import path

from . import views

app_name = "legal"

urlpatterns = [
    path("legal/policies/", views.PolicyListView.as_view(), name="policies"),
    path("legal/policies/<slug:slug>/", views.PolicyDetailView.as_view(), name="policy"),
    path(
        "legal/policies/<slug:slug>/versions/",
        views.PolicyHistoryView.as_view(),
        name="policy-history",
    ),
    path("legal/consents/mine/", views.ConsentHistoryView.as_view(), name="consents-mine"),
    path(
        "legal/consents/status/",
        views.ConsentStatusView.as_view(),
        name="consents-status",
    ),
    path("legal/consents/withdraw/", views.ConsentWithdrawView.as_view(), name="consents-withdraw"),
    path("legal/consents/", views.ConsentCreateView.as_view(), name="consents-create"),
    path(
        "legal/privacy-requests/mine/",
        views.PrivacyRequestMineView.as_view(),
        name="privacy-requests-mine",
    ),
    path(
        "legal/privacy-requests/<uuid:pk>/review/",
        views.PrivacyRequestAdminActionView.as_view(),
        name="privacy-request-review",
    ),
    path(
        "legal/privacy-requests/",
        views.PrivacyRequestAdminView.as_view(),
        name="privacy-requests",
    ),
    path(
        "legal/policy-versions/<uuid:pk>/",
        views.PolicyVersionDetailView.as_view(),
        name="policy-version-detail",
    ),
    path(
        "legal/policy-versions/<uuid:pk>/<str:action>/",
        views.PolicyVersionAdminActionView.as_view(),
        name="policy-version-action",
    ),
    path(
        "legal/policy-versions/",
        views.PolicyVersionListView.as_view(),
        name="policy-versions",
    ),
    path(
        "legal/policies/<slug:slug>/versions/create/",
        views.PolicyVersionAdminCreateView.as_view(),
        name="policy-version-create",
    ),
]
