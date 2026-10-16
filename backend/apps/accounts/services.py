from __future__ import annotations

import pyotp
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import exceptions

from .jwt import StarTokenObtainPairSerializer
from .models import AuthActionToken, MFASession, User


# ── Tokens ─────────────────────────────────────────────────────────────
def issue_token_pair(user: User) -> dict[str, str]:
    refresh = StarTokenObtainPairSerializer.get_token(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def create_action_token(user: User, purpose: str) -> AuthActionToken:
    return AuthActionToken.objects.create(
        user=user,
        purpose=purpose,
        expires_at=timezone.now() + settings.AUTH_ACTION_TOKEN_TTL,
    )


def consume_action_token(raw: str, purpose: str) -> User:
    record = (
        AuthActionToken.objects.select_related("user")
        .filter(token=raw, purpose=purpose)
        .first()
    )
    if record is None or not record.is_valid:
        raise exceptions.ValidationError(
            {"token": "This link is invalid, expired, or already used."}
        )
    record.mark_used()
    return record.user


# ── MFA ────────────────────────────────────────────────────────────────
def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def mfa_provisioning_uri(user: User, secret: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="STAR"
    )


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return bool(pyotp.TOTP(secret).verify(code.strip(), valid_window=1))


def start_mfa_session(user: User) -> tuple[MFASession, int]:
    session = MFASession.objects.create(
        user=user,
        expires_at=timezone.now() + settings.MFA_SESSION_TTL,
    )
    ttl = int(settings.MFA_SESSION_TTL.total_seconds())
    return session, ttl


def consume_mfa_session(raw: str, code: str) -> User:
    session = (
        MFASession.objects.select_related("user")
        .filter(token=raw)
        .first()
    )
    if session is None or not session.is_valid:
        raise exceptions.ValidationError(
            {"mfa_token": "This verification session is invalid or expired."}
        )
    if not verify_totp(session.user.mfa_secret, code):
        raise exceptions.AuthenticationFailed("Invalid verification code.")
    session.mark_used()
    return session.user


# ── Emails (no clinical or sensitive content in bodies) ────────────────
def _build_link(path: str, token: str) -> str:
    return f"{settings.FRONTEND_URL}/{path}?token={token}"


def send_verification_email(user: User, token: str) -> None:
    link = _build_link("verify-email", token)
    send_mail(
        subject="STAR — confirm your email address",
        message=(
            f"Hello {user.full_name or user.email},\n\n"
            "Confirm your STAR account by opening this link:\n"
            f"{link}\n\n"
            "If you did not create an account, ignore this message."
        ),
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(user: User, token: str) -> None:
    link = _build_link("reset-password", token)
    send_mail(
        subject="STAR — reset your password",
        message=(
            "A password reset was requested for your STAR account.\n"
            "Open this link to choose a new password:\n"
            f"{link}\n\n"
            "The link expires in "
            f"{int(settings.AUTH_ACTION_TOKEN_TTL.total_seconds() // 60)} minutes. "
            "If you did not request this, ignore this message."
        ),
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )
