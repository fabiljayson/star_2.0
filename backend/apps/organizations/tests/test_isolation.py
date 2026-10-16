from types import SimpleNamespace

import pytest

from apps.accounts.models import RoleAssignment, User, UserRole
from apps.accounts.tests.factories import (
    PlatformAdminFactory,
    RoleAssignmentFactory,
    UserFactory,
)
from apps.organizations.models import Department
from apps.organizations.tests.factories import DepartmentFactory, InstitutionFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    institution_a = InstitutionFactory(name="Alpha General Hospital")
    institution_b = InstitutionFactory(name="Beta General Hospital")
    admin_a = UserFactory(email="admin-alpha@example.test")
    RoleAssignmentFactory(
        user=admin_a, role=UserRole.INSTITUTION_ADMIN, institution=institution_a
    )
    admin_b = UserFactory(email="admin-beta@example.test")
    RoleAssignmentFactory(
        user=admin_b, role=UserRole.INSTITUTION_ADMIN, institution=institution_b
    )
    trainee_b = UserFactory(email="trainee-beta@example.test")
    RoleAssignmentFactory(
        user=trainee_b, role=UserRole.TRAINEE, institution=institution_b
    )
    return SimpleNamespace(
        institution_a=institution_a,
        institution_b=institution_b,
        admin_a=admin_a,
        admin_b=admin_b,
        trainee_b=trainee_b,
    )


class TestInstitutionIsolation:
    def test_admin_cannot_list_other_institution_memberships(
        self, client_factory, world
    ):
        client = client_factory(world.admin_a)
        response = client.get(
            "/api/v1/memberships/", {"institution": world.institution_b.pk}
        )
        assert response.status_code == 403
        assert response.data["error"]["code"] == "permission_denied"

    def test_membership_list_without_scope_returns_only_own(self, client_factory, world):
        client = client_factory(world.admin_a)
        response = client.get("/api/v1/memberships/")
        assert response.status_code == 200
        emails = {row["user_detail"]["email"] for row in response.data["results"]}
        assert emails == {world.admin_a.email}

    def test_user_directory_hides_other_institution_users(self, client_factory, world):
        client = client_factory(world.admin_a)
        response = client.get("/api/v1/users/")
        assert response.status_code == 200
        emails = {row["email"] for row in response.data["results"]}
        assert world.trainee_b.email not in emails
        assert world.admin_a.email in emails

    def test_user_directory_scoped_to_other_institution_is_denied(
        self, client_factory, world
    ):
        client = client_factory(world.admin_a)
        response = client.get("/api/v1/users/", {"institution": world.institution_b.pk})
        assert response.status_code == 403

    def test_user_directory_denied_for_plain_users(self, client_factory, world):
        plain = UserFactory(email="plain@example.test")
        client = client_factory(plain)
        response = client.get("/api/v1/users/")
        assert response.status_code == 403

    def test_cannot_create_department_in_other_institution(
        self, client_factory, world
    ):
        client = client_factory(world.admin_a)
        response = client.post(
            "/api/v1/departments/",
            {"institution": world.institution_b.pk, "name": "Cardiac Surgery"},
        )
        assert response.status_code == 403

    def test_cannot_edit_other_institution_profile(self, client_factory, world):
        client = client_factory(world.admin_a)
        response = client.patch(
            f"/api/v1/institutions/{world.institution_b.pk}/", {"city": "Hacked"}
        )
        assert response.status_code == 403
        world.institution_b.refresh_from_db()
        assert world.institution_b.city != "Hacked"

    def test_plain_user_cannot_grant_roles(self, client_factory, world):
        plain = UserFactory()
        client = client_factory(plain)
        response = client.post(
            "/api/v1/memberships/",
            {
                "user": plain.pk,
                "role": UserRole.INSTITUTION_ADMIN,
                "institution": world.institution_a.pk,
            },
        )
        assert response.status_code == 403

    def test_admin_cannot_grant_roles_in_other_institution(
        self, client_factory, world
    ):
        client = client_factory(world.admin_a)
        fresh_user = UserFactory(email="fresh-for-role@example.test")
        response = client.post(
            "/api/v1/memberships/",
            {
                "user": fresh_user.pk,
                "role": UserRole.TRAINEE,
                "institution": world.institution_b.pk,
            },
        )
        assert response.status_code == 403
        assert not RoleAssignment.objects.filter(
            user=fresh_user, institution=world.institution_b
        ).exists()


class TestRoleManagement:
    def test_admin_can_grant_roles_in_own_institution(self, client_factory, world):
        client = client_factory(world.admin_a)
        new_trainee = UserFactory(email="new-trainee@example.test")
        response = client.post(
            "/api/v1/memberships/",
            {
                "user": new_trainee.pk,
                "role": UserRole.TRAINEE,
                "institution": world.institution_a.pk,
            },
        )
        assert response.status_code == 201, response.data
        assert RoleAssignment.objects.filter(
            user=new_trainee, role=UserRole.TRAINEE, is_active=True
        ).exists()

    def test_platform_role_cannot_be_granted_through_memberships(
        self, client_factory, world
    ):
        platform = PlatformAdminFactory(email="root@example.test")
        client = client_factory(platform)
        target = UserFactory()
        response = client.post(
            "/api/v1/memberships/",
            {"user": target.pk, "role": UserRole.PLATFORM_ADMIN},
        )
        assert response.status_code == 400
        assert not target.is_platform_admin

    def test_duplicate_role_assignment_is_rejected(self, client_factory, world):
        client = client_factory(world.admin_a)
        trainee = UserFactory()
        payload = {
            "user": trainee.pk,
            "role": UserRole.TRAINEE,
            "institution": world.institution_a.pk,
        }
        assert client.post("/api/v1/memberships/", payload).status_code == 201
        assert client.post("/api/v1/memberships/", payload).status_code == 400

    def test_delete_membership_soft_deactivates(self, client_factory, world):
        RoleAssignmentFactory(
            user=world.admin_a, role=UserRole.EXAMINER, institution=world.institution_a
        )
        assignment = RoleAssignment.objects.get(
            user=world.admin_a, role=UserRole.EXAMINER
        )
        client = client_factory(world.admin_a)
        response = client.delete(f"/api/v1/memberships/{assignment.pk}/")
        assert response.status_code == 204
        assignment.refresh_from_db()
        assert assignment.is_active is False  # retained for audit history

    def test_institution_admin_can_edit_own_profile_fields(
        self, client_factory, world
    ):
        client = client_factory(world.admin_a)
        response = client.patch(
            f"/api/v1/institutions/{world.institution_a.pk}/",
            {"contact_email": "contact@alpha.test"},
        )
        assert response.status_code == 200
        world.institution_a.refresh_from_db()
        assert world.institution_a.contact_email == "contact@alpha.test"

    def test_is_active_of_institution_only_writable_by_platform_admin(
        self, client_factory, world
    ):
        client = client_factory(world.admin_a)
        response = client.patch(
            f"/api/v1/institutions/{world.institution_a.pk}/", {"is_active": False}
        )
        assert response.status_code == 200
        world.institution_a.refresh_from_db()
        assert world.institution_a.is_active is True  # ignored: field read-only


class TestInstitutionCreation:
    def test_plain_user_cannot_create_institution(self, client_factory, world):
        plain = UserFactory()
        client = client_factory(plain)
        response = client.post(
            "/api/v1/institutions/", {"name": "Rogue Hospital"}
        )
        assert response.status_code == 403

    def test_platform_admin_can_create_institution(self, client_factory):
        platform = PlatformAdminFactory(email="root@example.test")
        client = client_factory(platform)
        response = client.post(
            "/api/v1/institutions/",
            {"name": "Central Teaching Hospital", "country": "FR", "city": "Paris"},
        )
        assert response.status_code == 201, response.data
        assert response.data["slug"] == "central-teaching-hospital"


class TestInvitations:
    def test_invite_accept_and_role_assignment(self, client_factory, world):
        admin = client_factory(world.admin_a)
        invite = admin.post(
            "/api/v1/invitations/",
            {
                "institution": world.institution_a.pk,
                "email": "Invited.Trainee@example.test",
                "role": UserRole.TRAINEE,
            },
        )
        assert invite.status_code == 201, invite.data
        assert invite.data["email"] == "invited.trainee@example.test"
        token = invite.data["token"]

        accept = admin.post(
            "/api/v1/invitations/accept/",
            {"token": token, "password": "Invite!Passw0rd", "first_name": "Inv"},
        )
        assert accept.status_code == 201, accept.data

        invited = User.objects.get(email="invited.trainee@example.test")
        assert invited.is_verified is True
        assert RoleAssignment.objects.filter(
            user=invited, role=UserRole.TRAINEE, institution=world.institution_a
        ).exists()

        # Token cannot be reused.
        reused = admin.post(
            "/api/v1/invitations/accept/",
            {"token": token, "password": "Invite!Passw0rd"},
        )
        assert reused.status_code == 400

        # The invited user can sign in immediately.
        login = admin.post(
            "/api/v1/auth/login/",
            {"email": invited.email, "password": "Invite!Passw0rd"},
        )
        assert login.status_code == 200

        # The new member now appears in the institution directory.
        members = admin.get("/api/v1/memberships/", {"institution": world.institution_a.pk})
        emails = {row["user_detail"]["email"] for row in members.data["results"]}
        assert invited.email in emails

    def test_only_institution_roles_can_be_invited(self, client_factory, world):
        admin = client_factory(world.admin_a)
        response = admin.post(
            "/api/v1/invitations/",
            {
                "institution": world.institution_a.pk,
                "email": "someone@example.test",
                "role": UserRole.PLATFORM_ADMIN,
            },
        )
        assert response.status_code == 400

    def test_revoked_invitation_cannot_be_accepted(self, client_factory, world):
        admin = client_factory(world.admin_a)
        invite = admin.post(
            "/api/v1/invitations/",
            {
                "institution": world.institution_a.pk,
                "email": "revoked@example.test",
                "role": UserRole.TRAINEE,
            },
        )
        token = invite.data["token"]
        revoke = admin.post(f"/api/v1/invitations/{invite.data['id']}/revoke/")
        assert revoke.status_code == 200

        accept = admin.post(
            "/api/v1/invitations/accept/", {"token": token, "password": "Invite!Passw0rd"}
        )
        assert accept.status_code == 400

    def test_cannot_invite_into_other_institution(self, client_factory, world):
        admin = client_factory(world.admin_a)
        response = admin.post(
            "/api/v1/invitations/",
            {
                "institution": world.institution_b.pk,
                "email": "intruder@example.test",
                "role": UserRole.TRAINEE,
            },
        )
        assert response.status_code == 403


class TestDepartments:
    def test_department_soft_delete_keeps_row(self, client_factory, world):
        department = DepartmentFactory(institution=world.institution_a, name="Trauma")
        client = client_factory(world.admin_a)
        response = client.delete(f"/api/v1/departments/{department.pk}/")
        assert response.status_code == 204
        department.refresh_from_db()
        assert department.is_active is False
        assert Department.objects.filter(pk=department.pk).exists()

    def test_duplicate_department_name_rejected_case_insensitively(
        self, client_factory, world
    ):
        DepartmentFactory(institution=world.institution_a, name="Neurosurgery")
        client = client_factory(world.admin_a)
        response = client.post(
            "/api/v1/departments/",
            {"institution": world.institution_a.pk, "name": "neurosurgery"},
        )
        assert response.status_code == 400
