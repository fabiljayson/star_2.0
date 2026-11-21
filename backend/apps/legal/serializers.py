from __future__ import annotations

import rest_framework.serializers as serializers

from .models import (
    ConsentContext,
    Policy,
    PolicyConsent,
    PolicyVersion,
    PrivacyRequest,
)


# ── Public reads ───────────────────────────────────────────────────────
class PolicyVersionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyVersion
        fields = [
            "id",
            "language",
            "version",
            "status",
            "published_at",
            "effective_date",
        ]


class PolicyListSerializer(serializers.ModelSerializer):
    published_versions = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        fields = [
            "id",
            "slug",
            "title",
            "category",
            "summary",
            "published_versions",
        ]

    def get_published_versions(self, policy: Policy) -> list[dict]:
        return PolicyVersionBriefSerializer(
            policy.versions.filter(
                status=PolicyVersion.Status.PUBLISHED,
            )
            .order_by("language", "-published_at")
            .distinct("language"),
            many=True,
        ).data


class PolicyVersionDetailSerializer(serializers.ModelSerializer):
    policy_slug = serializers.CharField(source="policy.slug", read_only=True)
    policy_summary = serializers.CharField(source="policy.summary", read_only=True)
    translation_of = serializers.SerializerMethodField()

    class Meta:
        model = PolicyVersion
        fields = [
            "id",
            "policy_slug",
            "policy_summary",
            "language",
            "version",
            "status",
            "title",
            "body",
            "effective_date",
            "published_at",
            "last_reviewed_at",
            "translation_of",
        ]

    def get_translation_of(self, version: PolicyVersion):
        source = version.translation_of
        if source is None:
            return None
        return {
            "id": source.pk,
            "language": source.language,
            "version": source.version,
        }


class PolicyHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyVersion
        fields = [
            "id",
            "language",
            "version",
            "status",
            "published_at",
            "effective_date",
            "last_reviewed_at",
        ]


# ── Consents ───────────────────────────────────────────────────────────
class ConsentCreateSerializer(serializers.Serializer):
    policy_slug = serializers.SlugField()
    version = serializers.CharField(max_length=32)
    language = serializers.ChoiceField(choices=["en", "fr"])
    context = serializers.ChoiceField(
        choices=ConsentContext.choices,
        default=ConsentContext.ACCOUNT,
    )

    def validate(self, attrs: dict) -> dict:
        policy = Policy.objects.filter(slug=attrs["policy_slug"]).first()
        if policy is None:
            raise serializers.ValidationError(
                {"policy_slug": "Unknown policy."}
            )
        version = (
            policy.versions.filter(
                language=attrs["language"],
                version=attrs["version"],
                status=PolicyVersion.Status.PUBLISHED,
            ).first()
        )
        if version is None:
            raise serializers.ValidationError(
                {
                    "version": (
                        "This version is not a published text; consent can only "
                        "bind to a published policy."
                    )
                }
            )
        attrs["policy_version"] = version
        return attrs


class ConsentSerializer(serializers.ModelSerializer):
    policy_slug = serializers.CharField(source="policy.slug", read_only=True)
    policy_title = serializers.CharField(source="policy.title", read_only=True)
    version = serializers.CharField(source="policy_version.version", read_only=True)

    class Meta:
        model = PolicyConsent
        fields = [
            "id",
            "policy_slug",
            "policy_title",
            "version",
            "context",
            "withdrawn_at",
            "withdrawn_reason",
            "created_at",
        ]


# ── Privacy requests ──────────────────────────────────────────────────
class PrivacyRequestSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = PrivacyRequest
        fields = [
            "id",
            "kind",
            "kind_label",
            "status",
            "response_note",
            "handled_at",
            "created_at",
        ]


class PrivacyRequestAdminSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = PrivacyRequest
        fields = [
            "id",
            "user_email",
            "kind",
            "status",
            "message",
            "response_note",
            "handled_by",
            "handled_at",
            "created_at",
        ]


class PrivacyRequestCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=PrivacyRequest.Kind.choices)
    message = serializers.CharField(max_length=2000)


class PrivacyRequestAdminActionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            PrivacyRequest.Status.IN_REVIEW,
            PrivacyRequest.Status.COMPLETED,
            PrivacyRequest.Status.REJECTED,
        ]
    )
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)


# ── Admin drafts & lifecycle ──────────────────────────────────────────
class PolicyVersionAdminSerializer(serializers.ModelSerializer):
    policy_slug = serializers.CharField(source="policy.slug", read_only=True)
    approved_by_email = serializers.EmailField(
        source="approved_by.email", read_only=True
    )

    class Meta:
        model = PolicyVersion
        fields = [
            "id",
            "policy_slug",
            "language",
            "version",
            "status",
            "title",
            "body",
            "effective_date",
            "published_at",
            "approved_by_email",
            "review_note",
        ]
        read_only_fields = ["status", "published_at", "approved_by_email"]


class PolicyVersionDraftUpdateSerializer(serializers.ModelSerializer):
    """Limited edit surface: drafts only, and never the lifecycle fields."""

    class Meta:
        model = PolicyVersion
        fields = ["title", "body", "effective_date", "review_note"]

    def validate(self, attrs: dict) -> dict:
        if self.instance.status != PolicyVersion.Status.DRAFT:
            raise serializers.ValidationError(
                {"status": "Only a draft can be edited; create a new version instead."}
            )
        return attrs


class PolicyVersionCreateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["en", "fr"])
    version = serializers.CharField(max_length=32)
    title = serializers.CharField(max_length=200)
    body = serializers.CharField()
    effective_date = serializers.DateField(required=False, allow_null=True)
    translation_of = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        policy = self.context["policy"]
        version = attrs["version"].strip()
        if not version:
            raise serializers.ValidationError({"version": "Required."})
        duplicate = policy.versions.filter(
            language=attrs["language"], version=version
        ).exists()
        if duplicate:
            raise serializers.ValidationError(
                {"version": "This version number already exists for the language."}
            )
        translation_of = attrs.get("translation_of") or ""
        if translation_of:
            source = policy.versions.filter(
                language=attrs["language"] == "fr" and "en" or "fr",
                version=translation_of,
            ).first()
            if source is None:
                raise serializers.ValidationError(
                    {"translation_of": "No source version with this number."}
                )
            attrs["translation_of"] = source
        return attrs

    def create(self, validated_data: dict, created_by=None) -> PolicyVersion:
        version = PolicyVersion.objects.create(
            policy=self.context["policy"],
            translation_of=validated_data.get("translation_of"),
            language=validated_data["language"],
            version=validated_data["version"].strip(),
            title=validated_data["title"],
            body=validated_data["body"],
            effective_date=validated_data.get("effective_date"),
        )
        if created_by is not None:
            version.created_by = created_by
            version.save(update_fields=["created_by", "updated_at"])
        return version
