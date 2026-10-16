import uuid

from django.utils.deprecation import MiddlewareMixin


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a per-request id used in logs and error responses."""

    HEADER = "X-Request-ID"

    def process_request(self, request):
        incoming = request.META.get(f"HTTP_{self.HEADER.upper().replace('-', '_')}")
        request.request_id = incoming[:64] if incoming else str(uuid.uuid4())

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response[self.HEADER] = request_id
        return response
