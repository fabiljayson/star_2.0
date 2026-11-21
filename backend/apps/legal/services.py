from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from .models import (
    Policy,
    PolicyConsent,
    PolicyVersion,
    PrivacyRequest,
    supersede_published,
)

REQUEST_POLICY = "terms-of-service"


def policies_with_languages() -> list[Policy]:
    return list(Policy.objects.prefetch_related("versions").order_by("category", "title"))


def resolve_version(policy: Policy, language: str):
    """Published version in the requested language, else the EN anchor, else FR.
    A draft is never returned."""
    version = policy.published_version(language)
    if version is not None and language != "en":
        return version
    if version is None:
        version = policy.published_version("en") or policy.published_version("fr")
    return version


def record_consent(
    *,
    user,
    policy_version: PolicyVersion,
    context: str,
    request=None,
    withdrawn_reason: str = "",
) -> PolicyConsent:
    """Persist that a user accepted one exact published version."""
    if not policy_version.is_published:
        raise ValidationError(
            {"policy_version": "Only published versions can be consented to."}
        )
    with transaction.atomic():
        consent = PolicyConsent.objects.create(
            user=user,
            policy=policy_version.policy,
            policy_version=policy_version,
            context=context,
        )
        record_audit(
            action=AuditEvent.Action.CONSENT_RECORDED,
            request=request,
            actor=user,
            object_type="policy_consent",
            object_pk=consent.pk,
            metadata={
                "policy": policy_version.policy.slug,
                "version": policy_version.version,
                "language": policy_version.language,
                "context": context,
            },
        )
    return consent


def withdraw_consent(
    *,
    user,
    policy: Policy,
    reason: str = "",
    request=None,
) -> PolicyConsent | None:
    """Mark the latest active consent for one policy as withdrawn."""
    with transaction.atomic():
        consent = (
            PolicyConsent.objects.select_for_update()
            .filter(user=user, policy=policy, withdrawn_at__isnull=True)
            .first()
        )
        if consent is None:
            return None
        consent.withdrawn_at = timezone.now()
        consent.withdrawn_reason = reason[:200]
        consent.save(update_fields=["withdrawn_at", "withdrawn_reason", "updated_at"])
        record_audit(
            action=AuditEvent.Action.CONSENT_WITHDRAWN,
            request=request,
            actor=user,
            object_type="policy_consent",
            object_pk=consent.pk,
            metadata={"policy": policy.slug, "reason": reason},
        )
    return consent


def _transition(
    version: PolicyVersion,
    from_status: str,
    to_status: str,
    *,
    request,
    extra_update: dict | None = None,
) -> PolicyVersion:
    if version.status != from_status:
        raise ValidationError(
            {"status": f"Expected {from_status}, found {version.status}."}
        )
    with transaction.atomic():
        updates = {"status": to_status, **(extra_update or {})}
        for field, value in updates.items():
            setattr(version, field, value)
        version.save()
        record_audit(
            action={
                PolicyVersion.Status.DRAFT.value: AuditEvent.Action.POLICY_VERSION_CREATED,
                PolicyVersion.Status.PENDING_REVIEW.value: AuditEvent.Action.POLICY_SUBMITTED,
                PolicyVersion.Status.APPROVED.value: AuditEvent.Action.POLICY_APPROVED,
                PolicyVersion.Status.PUBLISHED.value: AuditEvent.Action.POLICY_PUBLISHED,
                PolicyVersion.Status.ARCHIVED.value: AuditEvent.Action.POLICY_ARCHIVED,
                PolicyVersion.Status.SUPERSEDED.value: AuditEvent.Action.POLICY_SUPERSEDED,
            }[to_status],
            request=request,
            object_type="policy_version",
            object_pk=version.pk,
            metadata={
                "policy": version.policy.slug,
                "language": version.language,
                "version": version.version,
                "previous_status": from_status,
            },
        )
    return version


def submit_for_review(version: PolicyVersion, *, request) -> PolicyVersion:
    if not version.is_published:
        return _transition(
            version, PolicyVersion.Status.DRAFT, PolicyVersion.Status.PENDING_REVIEW,
            request=request,
        )
    raise ValidationError({"status": "A published version cannot be resubmitted."})


def approve(version: PolicyVersion, *, request) -> PolicyVersion:
    return _transition(
        version,
        PolicyVersion.Status.PENDING_REVIEW,
        PolicyVersion.Status.APPROVED,
        request=request,
        extra_update={
            "approved_by_id": request.user.pk,
            "last_reviewed_at": timezone.now(),
        },
    )


def publish(version: PolicyVersion, *, request) -> PolicyVersion:
    if version.status != PolicyVersion.Status.APPROVED:
        raise ValidationError(
            {"status": "Only an approved version can be published."}
        )
    if version.effective_date is None:
        raise ValidationError(
            {"effective_date": "Set an effective date before publication."}
        )
    with transaction.atomic():
        # Only approved versions become binding published texts, and a new
        # published sibling automatically supersedes the previous one.
        supersede_published(version.policy, version.language, version)
        _notify_policy_update(version, actor=request.user)
        record_audit(
            action=AuditEvent.Action.POLICY_PUBLISHED,
            request=request,
            object_type="policy_version",
            object_pk=version.pk,
            metadata={
                "policy": version.policy.slug,
                "language": version.language,
                "version": version.version,
                "effective_date": str(version.effective_date),
            },
        )
    return version


def _notify_policy_update(version: PolicyVersion, *, actor) -> int:
    """Tell active users a new text is live; previews stay generic."""
    from apps.accounts.models import User
    from apps.notifications.models import NotificationCategory
    from apps.notifications.services import notify

    return notify(
        recipients=User.objects.filter(is_active=True).exclude(pk=actor.pk),
        category=NotificationCategory.POLICY_UPDATE,
        title=f"{version.policy.title} updated",
        body=(
            f"Version {version.version} ({version.language.upper()}) is now in "
            "force. Review it in the Policies & Legal Center."
        ),
        link=f"/legal/policies/{version.policy.slug}",
        actor=actor,
        object_type="policy_version",
        object_pk=version.pk,
    )


def archive(version: PolicyVersion, *, request) -> PolicyVersion:
    return _transition(
        version,
        PolicyVersion.Status.DRAFT,
        PolicyVersion.Status.ARCHIVED,
        request=request,
    )

def open_privacy_request(
    *, user, kind: str, message: str, request=None
) -> PrivacyRequest:
    with transaction.atomic():
        petition = PrivacyRequest.objects.create(
            user=user, kind=kind, message=message
        )
        record_audit(
            action=AuditEvent.Action.PRIVACY_REQUEST_OPENED,
            request=request,
            actor=user,
            object_type="privacy_request",
            object_pk=petition.pk,
            metadata={"kind": kind},
        )
    return petition


def update_privacy_request(
    petition: PrivacyRequest,
    *,
    status: str,
    note: str = "",
    handled_by,
    request=None,
) -> PrivacyRequest:
    if status == PrivacyRequest.Status.OPEN and petition.status != PrivacyRequest.Status.OPEN:
        raise ValidationError({"status": "Cannot reopen a privacy request."})
    with transaction.atomic():
        petition.status = status
        petition.response_note = note
        petition.handled_by = handled_by
        petition.handled_at = timezone.now()
        petition.save()
        record_audit(
            action=AuditEvent.Action.PRIVACY_REQUEST_UPDATED,
            request=request,
            actor=handled_by,
            object_type="privacy_request",
            object_pk=petition.pk,
            metadata={"kind": petition.kind, "status": status},
        )
    return petition


def published_terms_version(language: str = "en") -> PolicyVersion | None:
    """The exact published Terms of Service version a registration must accept."""
    policy = Policy.objects.filter(slug=REQUEST_POLICY).first()
    if policy is None:
        return None
    return (
        policy.published_version(language)
        or policy.published_version("en")
        or policy.published_version("fr")
    )


def terms_acceptance_required(user) -> bool:
    """True when a published Terms text exists that this user has not accepted.

    Returns False for anonymous users, and while no Terms is published (the
    draft-only demo state): there is nothing to accept yet.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    policy = Policy.objects.filter(slug=REQUEST_POLICY).first()
    if policy is None:
        return False
    version = policy.published_version("en") or policy.published_version("fr")
    if version is None:
        return False
    return not PolicyConsent.objects.filter(
        user=user,
        policy_version=version,
        withdrawn_at__isnull=True,
    ).exists()


def ensure_terms_consent(user, *, request=None) -> bool:
    """True when the user has accepted the current published ToS version."""
    policy = Policy.objects.filter(slug=REQUEST_POLICY).first()
    if policy is None:
        return False
    version = policy.published_version("en") or policy.published_version("fr")
    if version is None:
        return False
    return PolicyConsent.objects.filter(
        user=user,
        policy_version=version,
        withdrawn_at__isnull=True,
    ).exists()


def consent_status_for(user) -> list[dict]:
    """Server-side consent overview: every policy, its published versions."""
    out: list[dict] = []
    for policy in policies_with_languages():
        versions = policy.versions.filter(
            status=PolicyVersion.Status.PUBLISHED
        ).order_by("-published_at")
        current = versions.first()
        latest_user_consent = (
            PolicyConsent.objects.filter(user=user, policy=policy).first()
        )
        if current is not None:
            out.append(
                {
                    "policy": policy.slug,
                    "title": current.title,
                    "current_version": current.version,
                    "consent_current": bool(
                        latest_user_consent
                        and latest_user_consent.policy_version_id == current.pk
                        and latest_user_consent.withdrawn_at is None
                    ),
                    "latest_withdrawn_at": (
                        latest_user_consent.withdrawn_at.isoformat()
                        if latest_user_consent and latest_user_consent.withdrawn_at
                        else None
                    ),
                }
            )
    return out


def require_platform_admin(user) -> None:
    if user is None or not user.is_authenticated or not user.is_platform_admin:
        raise PermissionDenied(
            "Only platform administrators manage policy lifecycle.",
            code="permission_denied",
        )
