from types import SimpleNamespace

import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.logbook.tests.factories import SurgicalProcedureFactory
from apps.organizations.tests.factories import InstitutionFactory
from apps.reports.models import ReportJob
from apps.training.models import AssessmentStatus
from apps.training.tests.factories import (
    AssessmentFactory,
    CompetencyFactory,
    CompetencyRubricVersionFactory,
    TrainingPlacementFactory,
)

pytestmark = pytest.mark.django_db

SECRET_FEEDBACK = "SECRET-FEEDBACK-MARKER-77"


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Training Report Institute")
    supervisor = UserFactory(email="trp-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    trainee = UserFactory(email="trp-trainee@example.test")
    RoleAssignmentFactory(user=trainee, role=UserRole.TRAINEE, institution=institution)
    manager = UserFactory(email="trp-manager@example.test")
    RoleAssignmentFactory(
        user=manager, role=UserRole.DEPARTMENT_MANAGER, institution=institution
    )
    examiner = UserFactory(email="trp-examiner@example.test")
    RoleAssignmentFactory(
        user=examiner, role=UserRole.EXAMINER, institution=institution
    )
    placement = TrainingPlacementFactory(
        institution=institution,
        trainee=trainee,
        supervisor=supervisor,
        title="Training report rotation",
    )
    competency = CompetencyFactory(
        institution=institution, code="TRP-COMP", title="Report competency"
    )
    rubric = CompetencyRubricVersionFactory(competency=competency)
    return SimpleNamespace(
        institution=institution,
        supervisor=supervisor,
        trainee=trainee,
        manager=manager,
        examiner=examiner,
        placement=placement,
        competency=competency,
        rubric=rubric,
    )


def request_report(client, world, report_type, fmt="csv", **parameters):
    return client.post(
        "/api/v1/reports/",
        {
            "institution": str(world.institution.pk),
            "report_type": report_type,
            "format": fmt,
            "parameters": parameters,
        },
        format="json",
    )


def artifact_text(response) -> str:
    job = ReportJob.objects.get(pk=response.data["id"])
    return job.artifact.open("rb").read().decode("utf-8-sig")


class TestTraineeProgress:
    def test_trainee_exports_own_progress(self, client_factory, world):
        client = client_factory(world.trainee)
        response = request_report(
            client, world, "trainee_progress", target_user=str(world.trainee.pk)
        )
        assert response.status_code == 201, response.data
        text = artifact_text(response)
        assert world.placement.title in text
        assert "Training report rotation" in text

    def test_supervisor_exports_trainee_progress(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(
            client, world, "trainee_progress", target_user=str(world.trainee.pk)
        )
        assert response.status_code == 201
        assert response.data["row_count"] == 1

    def test_trainee_cannot_target_a_colleague(self, client_factory, world):
        client = client_factory(world.trainee)
        response = request_report(
            client, world, "trainee_progress", target_user=str(world.supervisor.pk)
        )
        assert response.status_code == 403

    def test_target_outside_institution_rejected(self, client_factory, world):
        stranger = UserFactory(email="trp-stranger@example.test")
        RoleAssignmentFactory(
            user=stranger,
            role=UserRole.TRAINEE,
            institution=InstitutionFactory(name="Training Report Other"),
        )
        client = client_factory(world.manager)
        response = request_report(
            client, world, "trainee_progress", target_user=str(stranger.pk)
        )
        assert response.status_code == 400


class TestCompetencyAssessments:
    @pytest.fixture
    def assessment(self, world):
        return AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
            feedback=SECRET_FEEDBACK,
            decision_reason=SECRET_FEEDBACK,
            status=AssessmentStatus.SUBMITTED,
        )

    def test_assessor_sees_own_reviews_without_target(self, client_factory, world, assessment):
        client = client_factory(world.supervisor)
        response = request_report(client, world, "competency_assessments")
        assert response.status_code == 201
        text = artifact_text(response)
        assert world.competency.code in text
        assert SECRET_FEEDBACK not in text

    def test_trainee_sees_own_assessments(self, client_factory, world, assessment):
        client = client_factory(world.trainee)
        response = request_report(client, world, "competency_assessments")
        assert response.status_code == 201
        assert artifact_text(response).count(world.trainee.email) >= 1

    def test_manager_can_target_a_trainee(self, client_factory, world, assessment):
        client = client_factory(world.manager)
        response = request_report(
            client,
            world,
            "competency_assessments",
            target_user=str(world.trainee.pk),
        )
        assert response.status_code == 201
        assert response.data["row_count"] == 1

    def test_trainee_cannot_target_a_colleague(self, client_factory, world, assessment):
        client = client_factory(world.trainee)
        response = request_report(
            client,
            world,
            "competency_assessments",
            target_user=str(world.supervisor.pk),
        )
        assert response.status_code == 403

    def test_foreign_institution_assessments_absent(self, client_factory, world):
        foreign_institution = InstitutionFactory(name="Training Report Foreign")
        foreign_trainee = UserFactory(email="trp-foreign-trainee@example.test")
        RoleAssignmentFactory(
            user=foreign_trainee,
            role=UserRole.TRAINEE,
            institution=foreign_institution,
        )
        foreign_placement = TrainingPlacementFactory(
            institution=foreign_institution,
            trainee=foreign_trainee,
            title="Foreign rotation",
        )
        foreign_competency = CompetencyFactory(
            institution=foreign_institution, code="TRP-FOREIGN"
        )
        foreign_rubric = CompetencyRubricVersionFactory(competency=foreign_competency)
        AssessmentFactory(
            placement=foreign_placement,
            competency=foreign_competency,
            rubric_version=foreign_rubric,
            assessor=foreign_trainee,
        )
        client = client_factory(world.manager)
        response = request_report(
            client, world, "competency_assessments", target_user=str(world.trainee.pk)
        )
        assert response.status_code == 201
        text = artifact_text(response)
        assert "TRP-FOREIGN" not in text
        assert "Foreign rotation" not in text


class TestExaminerReviews:
    @pytest.fixture
    def assessment(self, world):
        return AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.examiner,
        )

    def test_examiner_sees_own_history(self, client_factory, world, assessment):
        client = client_factory(world.examiner)
        response = request_report(client, world, "examiner_reviews")
        assert response.status_code == 201
        assert response.data["row_count"] == 1
        assert world.examiner.email in artifact_text(response)

    def test_manager_can_target_an_examiner(self, client_factory, world, assessment):
        client = client_factory(world.manager)
        response = request_report(
            client, world, "examiner_reviews", target_user=str(world.examiner.pk)
        )
        assert response.status_code == 201
        assert response.data["row_count"] == 1

    def test_examiner_cannot_target_someone_else(self, client_factory, world, assessment):
        client = client_factory(world.examiner)
        response = request_report(
            client, world, "examiner_reviews", target_user=str(world.supervisor.pk)
        )
        assert response.status_code == 403


class TestPlacementCompletion:
    @pytest.fixture
    def scored_placement(self, world):
        AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
            status=AssessmentStatus.APPROVED,
        )
        return world.placement

    def test_manager_sees_institution_placements_with_completion(
        self, client_factory, world, scored_placement
    ):
        client = client_factory(world.manager)
        response = request_report(client, world, "placement_completion")
        assert response.status_code == 201
        text = artifact_text(response)
        assert scored_placement.title in text
        assert "100%" in text

    def test_zero_assessments_show_na_not_zero_percent(self, client_factory, world):
        client = client_factory(world.manager)
        response = request_report(client, world, "placement_completion")
        assert response.status_code == 201
        assert "n/a" in artifact_text(response)

    def test_trainee_without_target_only_sees_own_placements(
        self, client_factory, world, scored_placement
    ):
        other_trainee = UserFactory(email="trp-trainee2@example.test")
        RoleAssignmentFactory(
            user=other_trainee, role=UserRole.TRAINEE, institution=world.institution
        )
        other_placement = TrainingPlacementFactory(
            institution=world.institution,
            trainee=other_trainee,
            title="Other trainee rotation",
        )
        client = client_factory(world.trainee)
        response = request_report(client, world, "placement_completion")
        assert response.status_code == 201
        text = artifact_text(response)
        assert scored_placement.title in text
        assert other_placement.title not in text

    def test_trainee_cannot_target_a_colleague(self, client_factory, world):
        client = client_factory(world.trainee)
        response = request_report(
            client, world, "placement_completion", target_user=str(world.supervisor.pk)
        )
        assert response.status_code == 403


class TestInstitutionSummary:
    def test_manager_gets_institution_metrics(self, client_factory, world):
        SurgicalProcedureFactory(
            institution=world.institution, author=world.trainee, status="draft"
        )
        client = client_factory(world.manager)
        response = request_report(client, world, "institution_summary")
        assert response.status_code == 201
        text = artifact_text(response)
        assert world.institution.name in text
        assert "Procedures draft" in text
        assert "Placements active" in text
        assert "Assessments draft" in text

    def test_supervisor_can_request_summary(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(client, world, "institution_summary")
        assert response.status_code == 201

    def test_trainee_denied_summary(self, client_factory, world):
        client = client_factory(world.trainee)
        response = request_report(client, world, "institution_summary")
        assert response.status_code == 403
