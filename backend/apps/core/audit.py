from __future__ import annotations

import logging

from .models import AuditEvent

logger = logging.getLogger("star.audit")


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit(
    *,
    action: str,
    request=None,
    actor=None,
    object_type: str = "",
    object_pk="",
    institution=None,
    metadata: dict | None = None,
) -> AuditEvent:
    """Persist one audit event.

    Raises on persistence failure: losing an audit record must fail the
    business operation rather than succeed silently.
    """
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            actor = user

    user_agent = ""
    request_id = ""
    if request is not None:
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:256]
        request_id = getattr(request, "request_id", "") or ""

    event = AuditEvent.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        action=action,
        object_type=object_type,
        object_pk=str(object_pk or ""),
        institution=institution,
        ip_address=_client_ip(request),
        user_agent=user_agent,
        request_id=request_id,
        metadata=metadata or {},
    )
    logger.info("audit %s object=%s%s", action, object_type, object_pk)
    return event
