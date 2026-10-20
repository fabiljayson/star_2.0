from __future__ import annotations

import rest_framework.views as views
from django.http import Http404
from rest_framework import permissions, status
from rest_framework.response import Response

from apps.core.audit import record_audit
from apps.core.models import AuditEvent
from apps.core.pagination import StandardPagination
from apps.core.permissions import is_platform_admin

from . import services
from .models import (
    ConsentContext,
    Policy,
    PolicyConsent,
    PolicyVersion,
    PrivacyRequest,
)
from .serializers import (
    ConsentCreateSerializer,
    ConsentSerializer,
    PolicyHistorySerializer,
    PolicyListSerializer,
    PolicyVersionAdminSerializer,
    PolicyVersionCreateSerializer,
    PolicyVersionDetailSerializer,
    PrivacyRequestAdminActionSerializer,
    PrivacyRequestAdminSerializer,
    PrivacyRequestCreateSerializer,
    PrivacyRequestSerializer,
)


def _policy_or_404(slug: str) -> Policy:
    policy = (
        Policy.objects.prefetch_related("versions", "related_policies")
        .filter(slug=slug)
        .first()
    )
    if policy is None:
        raise Http404("Unknown policy.")
    return policy


def _negotiated_language(request) -> str:
    header = request.query_params.get("lang") or request.headers.get("Accept-Language") or ""
    return "fr" if header.lower().startswith("fr") else "en"


# ── Public Policy Center ──────────────────────────────────────────────
class PolicyListView(views.APIView):
    """Public and cacheable: published texts only — drafts never appear here."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        policies = services.policies_with_languages()
        payload = PolicyListSerializer(policies, many=True).data
        return Response({"results": payload, "count": len(payload)})


class PolicyDetailView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug: str):
        policy = _policy_or_404(slug)
        language = _negotiated_language(request)
        versions = policy.versions.filter(
            status=PolicyVersion.Status.PUBLISHED,
        )
        version = (
            versions.filter(language=language).first()
            or versions.filter(language="en").first()
            or versions.filter(language="fr").first()
        )
        if version is None:
            response = Response(
                {"detail": "No published version yet."}, status=404
            )
            response["X-Policy-Draft"] = "false"
            return response
        payload = PolicyVersionDetailSerializer(version).data
        payload["related"] = [
            {"slug": p.slug, "title": p.title}
            for p in policy.related_policies.all()
        ]
        return Response(payload)


class PolicyHistoryView(views.APIView):
    """Public: the version history — superseded/archived states only."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, slug: str):
        policy = _policy_or_404(slug)
        language = _negotiated_language(request)
        history = policy.versions.filter(
            language=language,
            status__in=[
                PolicyVersion.Status.PUBLISHED,
                PolicyVersion.Status.SUPERSEDED,
                PolicyVersion.Status.ARCHIVED,
            ],
        ).order_by("-published_at")
        return Response(
            {"results": PolicyHistorySerializer(history, many=True).data}
        )


# ── Consents ──────────────────────────────────────────────────────────
class ConsentCreateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = serializer.validated_data.get("context", ConsentContext.ACCOUNT)
        consent = services.record_consent(
            user=request.user,
            policy_version=serializer.validated_data["policy_version"],
            context=context,
            request=request,
        )
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


class ConsentHistoryView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        consents = PolicyConsent.objects.filter(user=request.user).select_related(
            "policy", "policy_version"
        )
        pager = StandardPagination()
        page = pager.paginate_queryset(consents, request, view=self)
        return pager.get_paginated_response(ConsentSerializer(page, many=True).data)


class ConsentStatusView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"results": services.consent_status_for(request.user)})


class ConsentWithdrawView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        slug = (request.data or {}).get("policy", "")
        policy = Policy.objects.filter(slug=slug).first()
        if policy is None:
            return Response({"policy": ["Unknown policy."]}, status=400)
        consent = services.withdraw_consent(
            user=request.user, policy=policy, request=request
        )
        if consent is None:
            return Response({"message": "No active consent."}, status=200)
        return Response(
            {
                "message": "Consent withdrawn.",
                "consent_id": str(consent.pk),
            },
            status=200,
        )


# ── Privacy requests ──────────────────────────────────────────────────
class PrivacyRequestMineView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        pager = StandardPagination()
        page = pager.paginate_queryset(
            PrivacyRequest.objects.filter(user=request.user), request, view=self
        )
        return pager.get_paginated_response(PrivacyRequestSerializer(page, many=True).data)


class PrivacyRequestAdminView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PrivacyRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        petition = services.open_privacy_request(
            user=request.user,
            kind=serializer.validated_data["kind"],
            message=serializer.validated_data["message"],
            request=request,
        )
        return Response(
            PrivacyRequestSerializer(petition).data,
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Only platform administrators browse privacy requests."},
                status=403,
            )
        status_filter = request.query_params.get("status")
        petitions = PrivacyRequest.objects.select_related("user")
        if status_filter:
            petitions = petitions.filter(status=status_filter)
        pager = StandardPagination()
        page = pager.paginate_queryset(petitions, request, view=self)
        return pager.get_paginated_response(
            PrivacyRequestAdminSerializer(page, many=True).data
        )


class PrivacyRequestAdminActionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Only platform administrators handle privacy requests."},
                status=403,
            )
        petition = PrivacyRequest.objects.filter(pk=pk).first()
        if petition is None:
            return Response({"detail": "Not found."}, status=404)
        serializer = PrivacyRequestAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        petition = services.update_privacy_request(
            petition,
            status=serializer.validated_data["status"],
            note=serializer.validated_data.get("note", ""),
            handled_by=request.user,
            request=request,
        )
        return Response(PrivacyRequestAdminSerializer(petition).data)


# ── Admin: policy draft & lifecycle ──────────────────────────────────
class PolicyVersionListView(views.APIView):
    """Admin workspace: every version in its lifecycle state."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Only platform administrators manage policies."},
                status=403,
            )
        queryset = PolicyVersion.objects.select_related("policy")
        status_filter = request.query_params.get("status")
        language = request.query_params.get("language")
        slug = request.query_params.get("policy")
        if slug:
            queryset = queryset.filter(policy__slug=slug)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if language:
            queryset = queryset.filter(language=language)
        pager = StandardPagination()
        page = pager.paginate_queryset(queryset, request, view=self)
        return pager.get_paginated_response(
            PolicyVersionAdminSerializer(page, many=True).data
        )


class PolicyVersionAdminActionView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, action: str):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Only platform administrators manage policies."},
                status=403,
            )
        version = PolicyVersion.objects.select_related("policy").filter(pk=pk).first()
        if version is None:
            return Response({"detail": "Not found."}, status=404)
        try:
            if action == "submit-review":
                services.submit_for_review(version, request=request)
            elif action == "approve":
                services.approve(version, request=request)
            elif action == "publish":
                services.publish(version, request=request)
            elif action == "archive":
                services.archive(version, request=request)
            else:
                return Response({"detail": "Unknown action."}, status=404)
        except Exception as error:
            return Response(
                getattr(error, "message_dict", None) or {"detail": [str(error)]},
                status=400,
            )
        return Response(PolicyVersionAdminSerializer(version).data)


class PolicyVersionAdminCreateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug: str):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Only platform administrators manage policies."},
                status=403,
            )
        policy = _policy_or_404(slug)
        serializer = PolicyVersionCreateSerializer(
            data=request.data, context={"policy": policy}
        )
        serializer.is_valid(raise_exception=True)
        version = serializer.create(serializer.validated_data, created_by=request.user)
        record_audit(
            action=AuditEvent.Action.POLICY_VERSION_CREATED,
            request=request,
            object_type="policy_version",
            object_pk=version.pk,
            metadata={
                "policy": policy.slug,
                "language": version.language,
                "version": version.version,
            },
        )
        return Response(PolicyVersionAdminSerializer(version).data, status=201)
