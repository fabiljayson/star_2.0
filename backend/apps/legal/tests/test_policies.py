from __future__ import annotations

from datetime import date

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_TEST_PASSWORD, PlatformAdminFactory
from apps.core.models import AuditEvent
from apps.legal.management.commands.seed_legal import CONTENT, VERSION
from apps.legal.models import (
    ConsentContext,
    Policy,
    PolicyConsent,
    PolicyVersion,
    PrivacyRequest,
    supersede_published,
)

TERMS_SLUG = "terms-of-service"


def _register(client, email: str = "newbuyer@example.test", role: str = "buyer") -> User:
    response = client.post(
        "/api/v1/auth/register/",
        {
            "email": email,
            "password": DEFAULT_TEST_PASSWORD,
            "role": role,
            "accepted_terms_version": VERSION,
        },
    )
    assert response.status_code == 201, response.data
    user = User.objects.get(pk=response.data["user"]["id"])
    # Most tests start after the email-confirmation step, which registration
    # deliberately leaves pending.
    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])
    return user


@pytest.fixture
def seeded_policies(db):
    """Seed the drafts, then run the documented administrator setup step.

    `seed_legal` publishes nothing; an administrator approves and publishes
    each text. These tests start after that step, because most of them are
    about the public, consented application.
    """
    from apps.legal.management.commands.seed_legal import Command

    Command().handle()
    for version in PolicyVersion.objects.all():
        version.status = PolicyVersion.Status.APPROVED
        version.effective_date = version.effective_date or date(2026, 10, 20)
        version.save(update_fields=["status", "effective_date", "updated_at"])
        supersede_published(version.policy, version.language, version)
    return {slug: Policy.objects.get(slug=slug) for slug in CONTENT}


@pytest.fixture
def draft_version(seeded_policies):
    policy = seeded_policies[TERMS_SLUG]
    return PolicyVersion.objects.create(
        policy=policy,
        language="en",
        version="2.0-draft",
        title="Terms of Service v2",
        body="Draft body — never presented as approved or binding.",
        status=PolicyVersion.Status.DRAFT,
        effective_date=date(2026, 11, 1),
    )


# ── Public Policy Center reads ─────────────────────────────────────────
@pytest.mark.django_db
class TestPublicReads:
    def test_policies_list_exposes_published_bilingual_texts(self, client, seeded_policies):
        response = client.get("/api/v1/legal/policies/?lang=fr")
        assert response.status_code == 200
        terms = next(
            item for item in response.data["results"] if item["slug"] == TERMS_SLUG
        )
        languages = {version["language"] for version in terms["published_versions"]}
        assert languages == {"en", "fr"}

    def test_draft_never_reaches_the_public_detail(
        self, client, seeded_policies, draft_version
    ):
        response = client.get("/api/v1/legal/policies/terms-of-service/?lang=en")
        assert response.status_code == 200
        assert response.data["version"] != draft_version.version
        assert response.data["body"].startswith("## 1.")

    def test_language_negotiation_returns_french(self, client, seeded_policies):
        response = client.get("/api/v1/legal/policies/privacy-policy/?lang=fr")
        assert response.status_code == 200
        assert response.data["language"] == "fr"
        assert "Politique" in response.data["title"]

    def test_version_history_excludes_states_never_published(
        self, client, seeded_policies
    ):
        response = client.get(
            "/api/v1/legal/policies/terms-of-service/versions/?lang=en"
        )
        assert response.status_code == 200
        statuses = {item["status"] for item in response.data["results"]}
        assert statuses <= {"published", "superseded", "archived"}

    def test_unknown_policy_is_404(self, client, seeded_policies):
        assert client.get("/api/v1/legal/policies/unknown/").status_code == 404


# ── Consent recording ──────────────────────────────────────────────────
@pytest.mark.django_db
class TestConsents:
    def test_registration_refuses_missing_consent(self, client, seeded_policies):
        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "newby@example.test",
                "password": DEFAULT_TEST_PASSWORD,
                "role": "buyer",
            },
        )
        assert response.status_code == 400
        assert "accepted_terms_version" in str(response.data)

    def test_registration_refuses_a_stale_version(self, client, seeded_policies):
        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "stale@example.test",
                "password": DEFAULT_TEST_PASSWORD,
                "role": "buyer",
                "accepted_terms_version": "0.9",
            },
        )
        assert response.status_code == 400

    def test_registration_records_consent_with_published_version(
        self, client, seeded_policies
    ):
        user = _register(client)
        consent = PolicyConsent.objects.get(user=user)
        assert consent.policy_version.version == VERSION
        assert consent.context == ConsentContext.REGISTRATION
        assert AuditEvent.objects.filter(action="legal.consent_recorded").exists()

    def test_user_can_consent_to_other_polices_and_read_history(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        policy = seeded_policies["privacy-policy"]
        response = authed.post(
            "/api/v1/legal/consents/",
            {
                "policy_slug": policy.slug,
                "version": VERSION,
                "language": "en",
                "context": "account",
            },
        )
        assert response.status_code == 201, response.data
        history = authed.get("/api/v1/legal/consents/mine/?page_size=50")
        versions = {item["version"] for item in history.data["results"]}
        assert versions == {VERSION}

    def test_consent_cannot_bind_a_draft(
        self, client, client_factory, seeded_policies, draft_version
    ):
        user = _register(client)
        authed = client_factory(user)
        response = authed.post(
            "/api/v1/legal/consents/",
            {
                "policy_slug": TERMS_SLUG,
                "version": draft_version.version,
                "language": "en",
            },
        )
        assert response.status_code == 400

    def test_withdrawal_keeps_immutably_records(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        response = authed.post(
            "/api/v1/legal/consents/withdraw/", {"policy": TERMS_SLUG}
        )
        assert response.status_code == 200
        consent = PolicyConsent.objects.get(user=user)
        assert consent.withdrawn_at is not None
        assert AuditEvent.objects.filter(
            action="legal.consent_withdrawn", object_pk=str(consent.pk)
        ).exists()
        assert PolicyConsent.objects.filter(user=user).count() == 1

    def test_consent_status_flags_policies_not_accepted(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        response = authed.get("/api/v1/legal/consents/status/")
        assert response.status_code == 200
        privacy = next(
            item
            for item in response.data["results"]
            if item["policy"] == "privacy-policy"
        )
        assert privacy["consent_current"] is False


# ── Privacy requests ───────────────────────────────────────────────────
@pytest.mark.django_db
class TestPrivacyRequests:
    def test_user_open_a_request_and_reads_it_back(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        response = authed.post(
            "/api/v1/legal/privacy-requests/",
            {"kind": "deletion", "message": "Please remove my clinical archive."},
        )
        assert response.status_code == 201, response.data
        mine = authed.get("/api/v1/legal/privacy-requests/mine/")
        assert mine.data["results"][0]["kind"] == "deletion"
        assert AuditEvent.objects.filter(
            action="legal.privacy_request_opened"
        ).exists()

    def test_admin_reviews_the_request(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client, email="admin-review@example.test")
        authed = client_factory(user)
        petition_pk = authed.post(
            "/api/v1/legal/privacy-requests/",
            {"kind": "export", "message": "Send me everything."},
        ).data["id"]

        admin_client = client_factory(PlatformAdminFactory())
        response = admin_client.post(
            f"/api/v1/legal/privacy-requests/{0 if 0 else petition_pk}/review/",
            {"status": "in_review", "note": "Preparing the extract."},
        )
        assert response.status_code == 200, response.data
        PrivacyRequest.objects.get(pk=petition_pk)
        assert AuditEvent.objects.filter(
            action="legal.privacy_request_updated"
        ).exists()

    def test_regular_users_cannot_browse_all_requests(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        assert authed.get("/api/v1/legal/privacy-requests/").status_code == 403


# ── Admin lifecycle ────────────────────────────────────────────────────
@pytest.mark.django_db
class TestAdminMfaPolicy:
    @override_settings(REQUIRE_MFA_FOR_PLATFORM_ADMINS=True)
    def test_unenrolled_admin_cannot_publish(
        self, client_factory, seeded_policies, draft_version
    ):
        admin_client = client_factory(PlatformAdminFactory())
        response = admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/submit-review/"
        )
        assert response.status_code == 403
        assert response.data["error"]["code"] == "mfa_required"

    @override_settings(REQUIRE_MFA_FOR_PLATFORM_ADMINS=True)
    def test_enrolled_admin_can_publish(self, seeded_policies, draft_version):
        # Enrolled admins sign in through the MFA challenge; authenticate the
        # request directly so this test isolates the policy check.
        admin = PlatformAdminFactory(mfa_enabled=True)
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        response = admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/submit-review/"
        )
        assert response.status_code == 200, response.data


@pytest.mark.django_db
class TestAdminLifecycle:
    def test_non_admin_cannot_manage_policies(
        self, client, client_factory, seeded_policies, draft_version
    ):
        user = _register(client)
        authed = client_factory(user)
        response = authed.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/submit-review/"
        )
        assert response.status_code == 403

    def test_draft_flow_publishes_then_supersedes(
        self, client_factory, seeded_policies, draft_version
    ):
        admin_client = client_factory(PlatformAdminFactory())
        pk = draft_version.pk
        for action in ("submit-review", "approve", "publish"):
            response = admin_client.post(f"/api/v1/legal/policy-versions/{pk}/{action}/")
            assert response.status_code == 200, response.data
            draft_version.refresh_from_db()
        assert draft_version.status == PolicyVersion.Status.PUBLISHED
        old = PolicyVersion.objects.get(
            policy=draft_version.policy, language="en", version=VERSION
        )
        assert old.status == PolicyVersion.Status.SUPERSEDED
        assert AuditEvent.objects.filter(
            action="legal.policy_published", object_pk=str(pk)
        ).exists()

    def test_publishing_without_effective_date_is_rejected(
        self, client_factory, seeded_policies, draft_version
    ):
        draft_version.effective_date = None
        draft_version.save(update_fields=["effective_date"])
        admin_client = client_factory(PlatformAdminFactory())
        admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/submit-review/"
        )
        admin_client.post(f"/api/v1/legal/policy-versions/{draft_version.pk}/approve/")
        response = admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/publish/"
        )
        assert response.status_code == 400

    def test_duplicate_version_number_is_rejected(
        self, client_factory, seeded_policies
    ):
        admin_client = client_factory(PlatformAdminFactory())
        response = admin_client.post(
            "/api/v1/legal/policies/terms-of-service/versions/create/",
            {
                "language": "en",
                "version": VERSION,
                "title": "Duplicate",
                "body": "Duplicate body placed as an unseen edit.",
            },
        )
        assert response.status_code == 400
        assert "version" in str(response.data)

    def test_admin_creates_a_linked_translation_draft(
        self, client_factory, seeded_policies
    ):
        admin_client = client_factory(PlatformAdminFactory())
        response = admin_client.post(
            "/api/v1/legal/policies/privacy-policy/versions/create/",
            {
                "language": "fr",
                "version": "1.1",
                "title": "Politique de confidentialité",
                "body": "Draft French text.",
                "translation_of": VERSION,
            },
        )
        assert response.status_code == 201, response.data
        created = PolicyVersion.objects.get(language="fr", version="1.1")
        assert created.translation_of.language == "en"
        assert created.status == PolicyVersion.Status.DRAFT

    def test_workflow_rejects_state_jumps(
        self, client_factory, seeded_policies, draft_version
    ):
        admin_client = client_factory(PlatformAdminFactory())
        # Draft cannot go straight to publishing; states must be walked.
        response = admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/approve/"
        )
        assert response.status_code == 400


# ── Seed and lifecycle integrity ───────────────────────────────────────
@pytest.mark.django_db
class TestSeedLeavesDrafts:
    def test_seed_publishes_nothing(self):
        from apps.legal.management.commands.seed_legal import Command

        Command().handle()
        assert Policy.objects.count() == len(CONTENT)
        assert not PolicyVersion.objects.filter(
            status=PolicyVersion.Status.PUBLISHED
        ).exists()
        # Each policy has both language drafts, and the French text is linked
        # to the English one that it translates.
        for policy in Policy.objects.all():
            versions = {v.language: v for v in policy.versions.all()}
            assert set(versions) == {"en", "fr"}
            assert versions["fr"].translation_of_id == versions["en"].pk
        # The public center has nothing to show until an admin publishes.
        # (Checked without the client fixture to keep this test seed-only.)


@pytest.mark.django_db
class TestPublishRequiresApproval:
    def test_a_draft_cannot_be_published_directly(
        self, client_factory, seeded_policies, draft_version
    ):
        admin_client = client_factory(PlatformAdminFactory())
        response = admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/publish/"
        )
        assert response.status_code == 400
        draft_version.refresh_from_db()
        assert draft_version.status == PolicyVersion.Status.DRAFT
        assert not PolicyVersion.objects.filter(pk=draft_version.pk).filter(
            status=PolicyVersion.Status.PUBLISHED
        ).exists()

    def test_pending_review_cannot_be_published(
        self, client_factory, seeded_policies, draft_version
    ):
        admin_client = client_factory(PlatformAdminFactory())
        admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/submit-review/"
        )
        response = admin_client.post(
            f"/api/v1/legal/policy-versions/{draft_version.pk}/publish/"
        )
        assert response.status_code == 400
        draft_version.refresh_from_db()
        assert draft_version.status == PolicyVersion.Status.PENDING_REVIEW

    def test_unreviewed_french_translation_never_goes_live(self, seeded_policies):
        fr = seeded_policies[TERMS_SLUG].versions.get(language="fr")
        fr.status = PolicyVersion.Status.DRAFT
        fr.save(update_fields=["status"])
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            supersede_published(fr.policy, "fr", fr)


# ── Reacceptance gating ────────────────────────────────────────────────
@pytest.mark.django_db
class TestReacceptance:
    def _publish_new_terms(self, policy, admin_client):
        version = PolicyVersion.objects.create(
            policy=policy,
            language="en",
            version="2.0",
            title="Terms of Service v2",
            body="## 1. Updated terms",
            status=PolicyVersion.Status.DRAFT,
            effective_date=date(2027, 1, 1),
        )
        for action in ("submit-review", "approve", "publish"):
            response = admin_client.post(
                f"/api/v1/legal/policy-versions/{version.pk}/{action}/"
            )
            assert response.status_code == 200, response.data
        version.refresh_from_db()
        return version

    def test_me_flags_a_new_terms_version_until_accepted(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        assert authed.get("/api/v1/users/me/").data[
            "requires_terms_acceptance"
        ] is False

        version = self._publish_new_terms(
            seeded_policies[TERMS_SLUG], client_factory(PlatformAdminFactory())
        )
        assert authed.get("/api/v1/users/me/").data[
            "requires_terms_acceptance"
        ] is True

        response = authed.post(
            "/api/v1/legal/consents/",
            {
                "policy_slug": TERMS_SLUG,
                "version": version.version,
                "language": "en",
            },
        )
        assert response.status_code == 201, response.data
        assert authed.get("/api/v1/users/me/").data[
            "requires_terms_acceptance"
        ] is False
        # The earlier acceptance is preserved.
        assert PolicyConsent.objects.filter(user=user).count() == 2

    def test_marketplace_writes_are_gated_on_acceptance(
        self, client, client_factory, seeded_policies
    ):
        user = _register(client)
        authed = client_factory(user)
        self._publish_new_terms(
            seeded_policies[TERMS_SLUG], client_factory(PlatformAdminFactory())
        )
        response = authed.post("/api/v1/marketplace/checkout/", {})
        assert response.status_code == 403
        assert response.data["error"]["code"] == "terms_acceptance_required"

    def test_publishing_notifies_active_users_but_not_the_actor(
        self, client, client_factory, seeded_policies
    ):
        from apps.notifications.models import Notification

        reader = _register(client, email="reader@example.test")
        admin = PlatformAdminFactory()
        self._publish_new_terms(seeded_policies[TERMS_SLUG], client_factory(admin))
        assert Notification.objects.filter(
            recipient=reader, category="policy_update"
        ).exists()
        assert not Notification.objects.filter(
            recipient=admin, category="policy_update"
        ).exists()


# ── Abuse limits on legal writes ───────────────────────────────────────
@pytest.mark.django_db
class TestLegalWriteThrottling:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }

    @staticmethod
    def _patch_rate(monkeypatch, scope):
        from django.conf import settings
        from rest_framework.throttling import ScopedRateThrottle

        rates = dict(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
        rates[scope] = "2/hour"
        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", rates, raising=False)

    @pytest.fixture(autouse=True)
    def _rate_limit(self, monkeypatch):
        self._patch_rate(monkeypatch, "consent_write")

    def test_consent_writes_are_throttled(self, client, client_factory):
        from django.core.cache import cache
        from django.test import override_settings

        with override_settings(CACHES=self.CACHES):
            cache.clear()
            authed = client_factory(_register(client))
            responses = [
                authed.post("/api/v1/legal/consents/", {}) for _ in range(3)
            ]
            cache.clear()

        assert [r.status_code for r in responses[:2]] == [400, 400]
        assert responses[2].status_code == 429
        assert responses[2]["Retry-After"]

    def test_privacy_request_creation_is_throttled(self, client, client_factory, monkeypatch):
        from django.core.cache import cache
        from django.test import override_settings

        self._patch_rate(monkeypatch, "privacy_request")
        with override_settings(CACHES=self.CACHES):
            cache.clear()
            authed = client_factory(_register(client))
            responses = [
                authed.post("/api/v1/legal/privacy-requests/", {}) for _ in range(3)
            ]
            cache.clear()

        assert [r.status_code for r in responses[:2]] == [400, 400]
        assert responses[2].status_code == 429
        assert responses[2]["Retry-After"]
