from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness/readiness probe: verifies database connectivity."""
    try:
        connection.ensure_connection()
        database = "ok"
        code = status.HTTP_200_OK
    except Exception:
        database = "error"
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(
        {
            "status": "ok" if database == "ok" else "degraded",
            "service": "star-api",
            "api_version": "v1",
            "checks": {"database": database},
        },
        status=code,
    )
