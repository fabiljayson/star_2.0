from django.urls import path

from . import views

urlpatterns = [
    path("institutions/", views.InstitutionListCreateView.as_view(), name="institution-list"),
    path(
        "institutions/<uuid:pk>/",
        views.InstitutionDetailView.as_view(),
        name="institution-detail",
    ),
    path("departments/", views.DepartmentListCreateView.as_view(), name="department-list"),
    path(
        "departments/<uuid:pk>/",
        views.DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    path("specialties/", views.SpecialtyListCreateView.as_view(), name="specialty-list"),
    path("memberships/", views.MembershipListCreateView.as_view(), name="membership-list"),
    path(
        "memberships/<uuid:pk>/",
        views.MembershipDetailView.as_view(),
        name="membership-detail",
    ),
    path("invitations/", views.InvitationListCreateView.as_view(), name="invitation-list"),
    path(
        "invitations/accept/",
        views.InvitationAcceptView.as_view(),
        name="invitation-accept",
    ),
    path(
        "invitations/<uuid:pk>/revoke/",
        views.InvitationRevokeView.as_view(),
        name="invitation-revoke",
    ),
]
