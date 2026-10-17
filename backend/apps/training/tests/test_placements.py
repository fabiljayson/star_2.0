from types import SimpleNamespace

import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.core.models import AuditEvent
from apps.logbook.tests.helpers import error_details
from apps.organizations.tests.factories import DepartmentFactory, InstitutionFactory
from apps.training.models import PlacementStatus
from apps.training.tests.factories import TrainingPlacementFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Training Institute North")
    department = DepartmentFactory(institution=institution, name="General Surgery")
    trainee = UserFactory(email="tr-trainee@example.test")
    RoleAssignmentFactory(
        user=trainee, role=UserRole.TRAINEE, institution=institution, department=department
    )
    supervisor = UserFactory(email="tr-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    examiner = UserFactory(email="tr-examiner@example.test")
    RoleAssignmentFactory(
        user=examiner, role=UserRole.EXAMINER, institution=institution
    )
    manager = UserFactory(email="tr-manager@example.test")
    RoleAssignmentFactory(
        user=manager, role=UserRole.DEPARTMENT_MANAGER, institution=institution
    )
    placement = TrainingPlacementFactory(
        institution=institution,
        department=department,
        trainee=trainee,
        supervisor=supervisor,
        title="General surgery rotation",
    )
    return SimpleNamespace(
        institution=institution,
        department=department,
        trainee=trainee,
        supervisor=supervisor,
        examiner=examiner,
        manager=manager,
        placement=placement,
    )


def _payload(world, **overrides):
    payload = {
        "title": "Cardiothoracic rotation",
        "institution": world.institution.pk,
        "department": world.department.pk,
        "trainee": world.trainee.pk,
        "start_date": "2026-11-01",
        "end_date": "2027-04-30",
        "objectives": "Master basic operative steps.",
    }
    payload.update(overrides)
    return payload


class TestPlacementCreation:
    @pytest.fixture
    def free_trainee(self, world):
        trainee = UserFactory(email="tr-free-trainee@example.test")
        RoleAssignmentFactory(
            user=trainee, role=UserRole.TRAINEE, institution=world.institution
        )
        return trainee

    def test_trainee_cannot_create_placement(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post("/api/v1/training/placements/", _payload(world))
        assert response.status_code == 403, response.data

    def test_supervisor_creates_placement(self, client_factory, world, free_trainee):
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/training/placements/",
            _payload(world, trainee=free_trainee.pk, title="Neuro rotation"),
        )
        assert response.status_code == 201, response.data
        assert response.data["status"] == PlacementStatus.ACTIVE
        assert response.data["trainee_detail"]["email"] == free_trainee.email

    def test_manager_creates_placement(self, client_factory, world, free_trainee):
        client = client_factory(world.manager)
        response = client.post(
            "/api/v1/training/placements/",
            _payload(world, trainee=free_trainee.pk, title="Manager rotation"),
        )
        assert response.status_code == 201, response.data

    def test_requires_active_trainee_role_in_institution(self, client_factory, world):
        outsider_trainee = UserFactory(email="tr-outsider-trainee@example.test")
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/training/placements/",
            _payload(world, trainee=outsider_trainee.pk),
        )
        assert response.status_code == 400
        assert "trainee" in error_details(response)

    def test_end_date_before_start_date_rejected(self, client_factory, world):
        other_trainee = UserFactory(email="tr-trainee2@example.test")
        RoleAssignmentFactory(
            user=other_trainee, role=UserRole.TRAINEE, institution=world.institution
        )
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/training/placements/",
            _payload(world, trainee=other_trainee.pk, start_date="2027-01-01", end_date="2026-12-01"),
        )
        assert response.status_code == 400
        assert "end_date" in error_details(response)

    def test_second_active_placement_for_same_trainee_rejected(
        self, client_factory, world
    ):
        other_trainee = UserFactory(email="tr-trainee3@example.test")
        RoleAssignmentFactory(
            user=other_trainee, role=UserRole.TRAINEE, institution=world.institution
        )
        client = client_factory(world.supervisor)
        assert (
            client.post(
                "/api/v1/training/placements/", _payload(world, trainee=other_trainee.pk)
            ).status_code
            == 201
        )
        response = client.post(
            "/api/v1/training/placements/", _payload(world, trainee=other_trainee.pk)
        )
        assert response.status_code == 400
        assert "trainee" in error_details(response)

    def test_placement_creation_is_audited(self, client_factory, world, free_trainee):
        client = client_factory(world.supervisor)
        client.post(
            "/api/v1/training/placements/",
            _payload(world, trainee=free_trainee.pk, title="Audited"),
        )
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.PLACEMENT_CREATED, actor=world.supervisor
        ).exists()


class TestPlacementLifecycle:
    def test_complete_then_locked(self, client_factory, world):
        client = client_factory(world.supervisor)
        url = f"/api/v1/training/placements/{world.placement.pk}/complete/"
        response = client.post(url)
        assert response.status_code == 200
        assert response.data["status"] == PlacementStatus.COMPLETED
        assert response.data["completed_at"] is not None

        assert client.post(url).status_code == 400
        patch = client.patch(
            f"/api/v1/training/placements/{world.placement.pk}/",
            {"title": "Renamed"},
        )
        assert patch.status_code == 400
        assert "status" in error_details(patch)

    def test_cancel_with_reason(self, client_factory, world):
        client = client_factory(world.manager)
        response = client.post(
            f"/api/v1/training/placements/{world.placement.pk}/cancel/",
            {"reason": "Trainee transferred."},
        )
        assert response.status_code == 200
        assert response.data["status"] == PlacementStatus.CANCELLED
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.PLACEMENT_CANCELLED
        ).exists()

    def test_trainee_cannot_complete_or_cancel(self, client_factory, world):
        client = client_factory(world.trainee)
        base = f"/api/v1/training/placements/{world.placement.pk}"
        assert client.post(f"{base}/complete/").status_code == 403
        assert client.post(f"{base}/cancel/", {}).status_code == 403

    def test_trainee_cannot_edit_placement(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.patch(
            f"/api/v1/training/placements/{world.placement.pk}/",
            {"title": "Hijacked"},
        )
        assert response.status_code == 403

    def test_supervisor_can_edit_active_placement(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.patch(
            f"/api/v1/training/placements/{world.placement.pk}/",
            {"title": "Updated rotation", "objectives": "New objectives."},
        )
        assert response.status_code == 200, response.data
        assert response.data["title"] == "Updated rotation"

    def test_scope_and_trainee_are_immutable(self, client_factory, world):
        other_institution = InstitutionFactory(name="Other Institute")
        client = client_factory(world.supervisor)
        response = client.patch(
            f"/api/v1/training/placements/{world.placement.pk}/",
            {"institution": other_institution.pk, "trainee": world.supervisor.pk},
        )
        assert response.status_code == 200
        world.placement.refresh_from_db()
        assert world.placement.institution_id == world.institution.pk
        assert world.placement.trainee_id == world.trainee.pk


class TestPlacementIsolation:
    def test_out_of_scope_placement_is_404(self, client_factory, world):
        outsider = UserFactory(email="tr-outsider-sup@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.SUPERVISOR,
            institution=InstitutionFactory(name="Rival Institute"),
        )
        client = client_factory(outsider)
        base = f"/api/v1/training/placements/{world.placement.pk}"
        assert client.get(base + "/").status_code == 404
        assert client.patch(base + "/", {"title": "x"}).status_code == 404
        assert client.post(base + "/complete/").status_code == 404

    def test_marketplace_account_sees_nothing(self, client_factory, world):
        supplier = UserFactory(email="tr-supplier@example.test")
        RoleAssignmentFactory(user=supplier, role=UserRole.SUPPLIER, institution=None)
        client = client_factory(supplier)
        assert (
            client.get(f"/api/v1/training/placements/{world.placement.pk}/").status_code
            == 404
        )
        assert client.get("/api/v1/training/placements/").data["count"] == 0

    def test_trainee_sees_only_own_placement(self, client_factory, world):
        other_trainee = UserFactory(email="tr-other-trainee@example.test")
        RoleAssignmentFactory(
            user=other_trainee, role=UserRole.TRAINEE, institution=world.institution
        )
        TrainingPlacementFactory(
            institution=world.institution,
            trainee=other_trainee,
            title="Other rotation",
        )
        client = client_factory(world.trainee)
        data = client.get("/api/v1/training/placements/").data
        assert data["count"] == 1
        assert data["results"][0]["id"] == str(world.placement.pk)

    def test_unassigned_examiner_does_not_see_placement(self, client_factory, world):
        client = client_factory(world.examiner)
        assert client.get("/api/v1/training/placements/").data["count"] == 0
        assert (
            client.get(f"/api/v1/training/placements/{world.placement.pk}/").status_code
            == 404
        )


class TestExaminerAssignments:
    def test_supervisor_assigns_and_examiner_gains_visibility(
        self, client_factory, world
    ):
        supervisor = client_factory(world.supervisor)
        url = f"/api/v1/training/placements/{world.placement.pk}/examiners/"
        response = supervisor.post(url, {"examiner": world.examiner.pk})
        assert response.status_code == 201, response.data
        assert response.data["examiner_detail"]["email"] == world.examiner.email

        examiner_client = client_factory(world.examiner)
        listing = examiner_client.get("/api/v1/training/placements/")
        assert listing.data["count"] == 1

    def test_duplicate_assignment_rejected(self, client_factory, world):
        client = client_factory(world.supervisor)
        url = f"/api/v1/training/placements/{world.placement.pk}/examiners/"
        assert client.post(url, {"examiner": world.examiner.pk}).status_code == 201
        duplicate = client.post(url, {"examiner": world.examiner.pk})
        assert duplicate.status_code == 400
        assert "examiner" in error_details(duplicate)

    def test_non_examiner_role_rejected(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/training/placements/{world.placement.pk}/examiners/",
            {"examiner": world.trainee.pk},
        )
        assert response.status_code == 400
        assert "examiner" in error_details(response)

    def test_trainee_cannot_assign_examiners(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post(
            f"/api/v1/training/placements/{world.placement.pk}/examiners/",
            {"examiner": world.examiner.pk},
        )
        assert response.status_code == 403

    def test_revoke_removes_visibility(self, client_factory, world):
        supervisor = client_factory(world.supervisor)
        url = f"/api/v1/training/placements/{world.placement.pk}/examiners/"
        assignment_id = supervisor.post(url, {"examiner": world.examiner.pk}).data["id"]

        examiner_client = client_factory(world.examiner)
        assert examiner_client.get("/api/v1/training/placements/").data["count"] == 1

        revoke = supervisor.delete(f"{url}{assignment_id}/")
        assert revoke.status_code == 204, revoke.data
        assert examiner_client.get("/api/v1/training/placements/").data["count"] == 0
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.EXAMINER_REVOKED
        ).exists()

    def test_assignment_blocked_on_closed_placement(self, client_factory, world):
        world.placement.status = PlacementStatus.COMPLETED
        world.placement.save()
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/training/placements/{world.placement.pk}/examiners/",
            {"examiner": world.examiner.pk},
        )
        assert response.status_code == 400
        assert "status" in error_details(response)
