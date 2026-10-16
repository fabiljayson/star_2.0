from django.urls import path

from . import views

urlpatterns = [
    # Authentication
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/verify/", views.VerifyEmailView.as_view(), name="auth-verify"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh/", views.StarTokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/logout-all/", views.LogoutAllView.as_view(), name="auth-logout-all"),
    path(
        "auth/password/forgot/",
        views.PasswordForgotView.as_view(),
        name="auth-password-forgot",
    ),
    path(
        "auth/password/reset/",
        views.PasswordResetView.as_view(),
        name="auth-password-reset",
    ),
    # Multi-factor authentication
    path("auth/mfa/setup/", views.MFASetupView.as_view(), name="auth-mfa-setup"),
    path("auth/mfa/enable/", views.MFAEnableView.as_view(), name="auth-mfa-enable"),
    path("auth/mfa/disable/", views.MFADisableView.as_view(), name="auth-mfa-disable"),
    path("auth/mfa/verify/", views.MFAVerifyView.as_view(), name="auth-mfa-verify"),
    # Users
    path("users/me/", views.MeView.as_view(), name="users-me"),
    path("users/", views.UserListView.as_view(), name="users-list"),
]
