from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("star.api")

# Never leak internal details to clients.
_GENERIC_MESSAGES = {
    status.HTTP_500_INTERNAL_SERVER_ERROR: "An unexpected error occurred.",
}


class SellerSubscriptionRequired(exceptions.APIException):
    """403 raised when a seller action needs an active paid subscription."""

    status_code = status.HTTP_403_FORBIDDEN
    default_code = "seller_subscription_required"
    default_detail = (
        "An active seller subscription is required to publish equipment."
    )


def _format_detail(detail):
    if isinstance(detail, (list, tuple)):
        return [_format_detail(item) for item in detail]
    if isinstance(detail, dict):
        return {key: _format_detail(value) for key, value in detail.items()}
    if isinstance(detail, exceptions.ErrorDetail):
        return str(detail)
    return detail


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        if isinstance(exc, DjangoPermissionDenied):
            return Response(
                {
                    "error": {
                        "code": "permission_denied",
                        "message": "You do not have permission to perform this action.",
                        "details": {},
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if isinstance(exc, Http404):
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": "Not found.",
                        "details": {},
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        logger.exception("Unhandled API exception (request_id=%s)",
                         getattr(context.get("request"), "request_id", ""))
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": _GENERIC_MESSAGES[status.HTTP_500_INTERNAL_SERVER_ERROR],
                    "details": {},
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = "error"
    if isinstance(exc, exceptions.NotAuthenticated):
        code = "not_authenticated"
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code = "authentication_failed"
    elif isinstance(exc, exceptions.PermissionDenied):
        code = getattr(exc, "default_code", None) or "permission_denied"
    elif isinstance(exc, exceptions.NotFound):
        code = "not_found"
    elif isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
    elif isinstance(exc, exceptions.MethodNotAllowed):
        code = "method_not_allowed"
    elif isinstance(exc, exceptions.NotAcceptable):
        code = "not_acceptable"
    elif isinstance(exc, exceptions.Throttled):
        code = "throttled"
    elif isinstance(exc, exceptions.APIException):
        code = getattr(exc, "default_code", "error")

    message = getattr(exc, "default_detail", "Request failed.")
    if isinstance(message, (list, tuple)):
        message = " ".join(str(item) for item in message)

    response.data = {
        "error": {
            "code": code,
            "message": str(message),
            "details": _format_detail(getattr(exc, "detail", {})),
        }
    }
    if response.status_code == 429 and "Retry-After" not in response:
        retry = getattr(exc, "wait", None)
        if retry:
            response["Retry-After"] = str(int(retry))
    return response
