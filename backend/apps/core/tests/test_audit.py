import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import (
    PlatformAdminFactory,
    RoleAssignmentFactory,
    UserFactory,
)
from apps.core.models import AuditEvent
from apps.organizations.tests.factories import InstitutionFactory

pytestmark = pytest.mark.django_db


class TestAuditTrail:
    def test_registration_is_audited(self, api):
        response = api.post(
            "/api/v1/auth/register/",
            {
                "email": "audited@example.test",
                "password": "Str0ng!Passw0rd",
                "role": "buyer",
            },
        )
        assert response.status_code == 201
        event = AuditEvent.objects.filter(action=AuditEvent.Action.AUTH_REGISTERED).get()
        assert event.actor_email == "audited@example.test"
        assert event.object_type == "user"
        assert event.metadata["role"] == "buyer"
        assert event.ip_address is not None

    def test_role_grant_is_audited(self, client_factory):
        platform = PlatformAdminFactory(email="root@example.test")
        institution = InstitutionFactory(name="Audit Hospital")
        target = UserFactory(email="granted@example.test")
        client = client_factory(platform)
        response = client.post(
            "/api/v1/memberships/",
            {
                "user": target.pk,
                "role": UserRole.TRAINEE,
                "institution": institution.pk,
            },
        )
        assert response.status_code == 201
        event = AuditEvent.objects.filter(action=AuditEvent.Action.ROLE_GRANTED).get()
        assert event.institution == institution
        assert event.actor_email == platform.email
        assert event.metadata["role"] == UserRole.TRAINEE

    def test_audit_endpoint_is_read_only(self, client_factory):
        platform = PlatformAdminFactory()
        client = client_factory(platform)
        response = client.post("/api/v1/audit/", {"action": "forged.event"})
        assert response.status_code == 405


class TestAuditVisibility:
    @pytest.fixture
    def audit_world(self):
        institution_a = InstitutionFactory(name="Audit Hospital A")
        institution_b = InstitutionFactory(name="Audit Hospital B")
        admin_a = UserFactory(email="audit-admin-a@example.test")
        RoleAssignmentFactory(
            user=admin_a, role=UserRole.INSTITUTION_ADMIN, institution=institution_a
        )
        admin_b = UserFactory(email="audit-admin-b@example.test")
        RoleAssignmentFactory(
            user=admin_b, role=UserRole.INSTITUTION_ADMIN, institution=institution_b
        )
        platform = PlatformAdminFactory(email="audit-root@example.test")
        return institution_a, institution_b, admin_a, admin_b, platform

    def _grant(self, client, user, role, institution):
        response = client.post(
            "/api/v1/memberships/",
            {"user": user.pk, "role": role, "institution": institution.pk},
        )
        assert response.status_code == 201

    def test_institution_admin_sees_only_own_institution_events(
        self, client_factory, audit_world
    ):
        inst_a, inst_b, admin_a, admin_b, platform = audit_world
        platform_client = client_factory(platform)
        self._grant(platform_client, UserFactory(), UserRole.TRAINEE, inst_a)
        self._grant(platform_client, UserFactory(), UserRole.TRAINEE, inst_b)

        client_a = client_factory(admin_a)
        response = client_a.get("/api/v1/audit/")
        assert response.status_code == 200
        actions = {row["action"] for row in response.data["results"]}
        assert actions <= {"role.granted"}  # institution-scoped subset
        inst_ids = {row["institution"] for row in response.data["results"]}
        assert inst_ids == {inst_a.pk}

        root_client = client_factory(platform)
        root_response = root_client.get("/api/v1/audit/")
        assert root_response.status_code == 200
        root_institutions = {row["institution"] for row in root_response.data["results"]}
        assert inst_a.pk in root_institutions and inst_b.pk in root_institutions

    def test_plain_user_has_no_audit_access(self, client_factory, audit_world):
        *_, platform = audit_world
        plain = UserFactory(email="no-audit@example.test")
        client = client_factory(plain)
        assert client.get("/api/v1/audit/").status_code == 403

    def test_audit_action_filter(self, client_factory, audit_world):
        inst_a, _, admin_a, _, platform = audit_world
        platform_client = client_factory(platform)
        self._grant(platform_client, UserFactory(), UserRole.TRAINEE, inst_a)

        client = client_factory(platform)
        response = client.get(
            "/api/v1/audit/", {"action": AuditEvent.Action.AUTH_REGISTERED}
        )
        assert response.status_code == 200
        assert all(
            row["action"] == AuditEvent.Action.AUTH_REGISTERED
            for row in response.data["results"]
        )
        assert client.get("/api/v1/audit/", {"action": "unknown.action"}).status_code in (
            200,
            400,
        )
