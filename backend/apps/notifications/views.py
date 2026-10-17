from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import exceptions, generics, status, views
from rest_framework.response import Response

from . import services
from .models import Notification
from .serializers import NotificationPreferenceSerializer, NotificationSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    ordering_fields = ["created_at", "category", "is_read"]
    ordering = ["-created_at"]
    filterset_fields = ["is_read", "category"]

    def get_queryset(self) -> QuerySet[Notification]:
        return services.visible_notifications(self.request.user)


class NotificationUnreadCountView(views.APIView):
    def get(self, request):
        return Response({"count": services.unread_count(request.user)})


class NotificationReadView(views.APIView):
    def post(self, request, pk):
        notification = services.mark_read(request.user, pk)
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(views.APIView):
    def post(self, request):
        updated = services.mark_all_read(request.user)
        return Response({"updated": updated})


class NotificationPreferenceListUpdateView(views.APIView):
    def get(self, request):
        serializer = NotificationPreferenceSerializer(
            services.list_preferences(request.user), many=True
        )
        return Response(serializer.data)

    def put(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        raw = request.data.get("preferences")
        if not isinstance(raw, list):
            raise exceptions.ValidationError(
                {"preferences": "Expected a list of preference objects."}
            )
        items = [item if isinstance(item, dict) else {"category": None} for item in raw]
        preferences = services.update_preferences(request.user, items)
        serializer = NotificationPreferenceSerializer(preferences, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
