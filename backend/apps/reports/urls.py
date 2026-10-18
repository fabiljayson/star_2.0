from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("reports/", views.ReportListCreateView.as_view(), name="report-list"),
    path("reports/<uuid:pk>/", views.ReportDetailView.as_view(), name="report-detail"),
    path(
        "reports/<uuid:pk>/download/",
        views.ReportDownloadView.as_view(),
        name="report-download",
    ),
]
