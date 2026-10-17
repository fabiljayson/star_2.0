from types import SimpleNamespace

import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.core.models import AuditEvent
from apps.logbook.tests.helpers import error_details
from apps.organizations.tests.factories import DepartmentFactory, InstitutionFactory
from apps.training.models import (
    CompetencyRubricVersion,
)
from apps.training.tests.factories import (
    CompetencyFactory,
    TrainingPlacementFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Catalog Institute")
    department = DepartmentFactory(institution=institution, name="Surgery")
    manager = UserFactory(email="cat-manager@example.test")
    RoleAssignmentFactory(
        user=manager, role=UserRole.DEPARTMENT_MANAGER, institution=institution
    )
    supervisor = UserFactory(email="cat-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    trainee = UserFactory(email="cat-trainee@example.test")
    RoleAssignmentFactory(
        user=trainee, role=UserRole.TRAINEE, institution=institution, department=department
    )
    competency = CompetencyFactory(
        institution=institution, code="lap-basic", title="Laparoscopic basics"
    )
    placement = TrainingPlacementFactory(
        institution=institution, trainee=trainee, supervisor=supervisor
    )
    return SimpleNamespace(
        institution=institution,
        department=department,
        manager=manager,
        supervisor=supervisor,
        trainee=trainee,
        competency=competency,
        placement=placement,
    )


class TestCompetencyCatalog:
    def test_trainee_cannot_create_competency(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post(
            "/api/v1/competencies/",
            {
                "institution": world.institution.pk,
                "code": "steering",
                "title": "Camera steering",
            },
        )
        assert response.status_code == 403, response.data

    def test_supervisor_cannot_create_competency(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/competencies/",
            {
                "institution": world.institution.pk,
                "code": "steering",
                "title": "Camera steering",
            },
        )
        assert response.status_code == 403

    def test_manager_creates_competency_with_normalized_code(
        self, client_factory, world
    ):
        client = client_factory(world.manager)
        response = client.post(
            "/api/v1/competencies/",
            {
                "institution": world.institution.pk,
                "code": "  steering ",
                "title": "Camera steering",
            },
        )
        assert response.status_code == 201, response.data
        assert response.data["code"] == "STEERING"
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.COMPETENCY_CREATED
        ).exists()

    def test_duplicate_code_rejected(self, client_factory, world):
        client = client_factory(world.manager)
        response = client.post(
            "/api/v1/competencies/",
            {
                "institution": world.institution.pk,
                "code": "LAP-BASIC",
                "title": "Duplicate",
            },
        )
        assert response.status_code == 400

    def test_cross_institution_visibility_is_404(self, client_factory, world):
        outsider = UserFactory(email="cat-outsider@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.INSTITUTION_ADMIN,
            institution=InstitutionFactory(name="Foreign Catalog Institute"),
        )
        client = client_factory(outsider)
        base = f"/api/v1/competencies/{world.competency.pk}"
        assert client.get(base + "/").status_code == 404
        assert (
            client.patch(base + "/", {"title": "Hijacked"}).status_code == 404
        )

    def test_trainee_can_view_but_not_edit(self, client_factory, world):
        client = client_factory(world.trainee)
        assert (
            client.get(f"/api/v1/competencies/{world.competency.pk}/").status_code == 200
        )
        response = client.patch(
            f"/api/v1/competencies/{world.competency.pk}/", {"title": "Renamed"}
        )
        assert response.status_code == 403

    def test_training_member_sees_institution_catalog(self, client_factory, world):
        client = client_factory(world.trainee)
        data = client.get("/api/v1/competencies/").data
        assert data["count"] >= 1
        assert all(
            row["institution"] == world.institution.pk for row in data["results"]
        )


class TestRubricVersions:
    def _url(self, world) -> str:
        return f"/api/v1/competencies/{world.competency.pk}/rubric-versions/"

    def test_manager_creates_first_version_with_default_template(
        self, client_factory, world
    ):
        client = client_factory(world.manager)
        response = client.post(self._url(world), {})
        assert response.status_code == 201, response.data
        assert response.data["version"] == 1
        assert response.data["is_current"] is True
        assert response.data["levels"]["scale"]

    def test_new_version_supersedes_previous(self, client_factory, world):
        client = client_factory(world.manager)
        first = client.post(self._url(world), {})
        second = client.post(
            self._url(world),
            {"levels": {"scale": [{"key": "a", "label": "A", "rank": 1}],
                         "criteria": [{"key": "safe", "label": "Safety"}]}},
        )
        assert second.status_code == 201, second.data
        assert second.data["version"] == 2

        first_rubric = CompetencyRubricVersion.objects.get(pk=first.data["id"])
        second_rubric = CompetencyRubricVersion.objects.get(pk=second.data["id"])
        assert first_rubric.is_current is False
        assert second_rubric.is_current is True

    def test_rubric_versions_are_immutable(self, client_factory, world):
        client = client_factory(world.manager)
        created = client.post(self._url(world), {})
        detail = f"{self._url(world)}{created.data['id']}/"
        assert client.get(detail).status_code == 200
        assert client.patch(detail, {"notes": "changed"}).status_code == 405
        assert client.delete(detail).status_code == 405

    def test_empty_scale_rejected(self, client_factory, world):
        client = client_factory(world.manager)
        response = client.post(
            self._url(world), {"levels": {"scale": [], "criteria": []}}
        )
        assert response.status_code == 400
        assert "levels" in error_details(response) or "non_field_errors" in error_details(response)

    def test_trainee_cannot_create_rubric(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post(self._url(world), {})
        assert response.status_code == 403

    def test_out_of_scope_competency_is_404(self, client_factory, world):
        outsider = UserFactory(email="cat-outsider2@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.INSTITUTION_ADMIN,
            institution=InstitutionFactory(name="Another Foreign Institute"),
        )
        client = client_factory(outsider)
        assert client.post(self._url(world), {}).status_code == 404


class TestExpectedCompetencies:
    @pytest.fixture
    def free_trainee(self, world):
        trainee = UserFactory(email="cat-trainee2@example.test")
        RoleAssignmentFactory(
            user=trainee, role=UserRole.TRAINEE, institution=world.institution
        )
        return trainee

    def test_placement_accepts_own_institution_competency(
        self, client_factory, world, free_trainee
    ):
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/training/placements/",
            {
                "title": "Catalog rotation",
                "institution": world.institution.pk,
                "trainee": free_trainee.pk,
                "start_date": "2026-12-01",
                "expected_competency_ids": [world.competency.pk],
            },
        )
        assert response.status_code == 201, response.data
        assert response.data["expected_competencies"][0]["code"] == world.competency.code

    def test_foreign_competency_rejected(
        self, client_factory, world, free_trainee
    ):
        foreign = CompetencyFactory(institution=InstitutionFactory(name="Foreign"))
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/training/placements/",
            {
                "title": "Bad rotation",
                "institution": world.institution.pk,
                "trainee": free_trainee.pk,
                "start_date": "2026-12-01",
                "expected_competency_ids": [foreign.pk],
            },
        )
        assert response.status_code == 400
        assert "expected_competency_ids" in error_details(response)

    def test_manager_can_update_expected_competencies(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.patch(
            f"/api/v1/training/placements/{world.placement.pk}/",
            {"expected_competency_ids": [world.competency.pk]},
        )
        assert response.status_code == 200, response.data
        assert len(response.data["expected_competencies"]) == 1
        world.placement.refresh_from_db()
        assert world.competency in world.placement.expected_competencies.all()
