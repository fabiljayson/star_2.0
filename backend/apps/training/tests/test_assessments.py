from types import SimpleNamespace

import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.core.models import AuditEvent
from apps.logbook.tests.factories import (
    ProcedureParticipantFactory,
    SurgicalProcedureFactory,
)
from apps.logbook.tests.helpers import error_details
from apps.organizations.tests.factories import DepartmentFactory, InstitutionFactory
from apps.training.models import Assessment, AssessmentStatus
from apps.training.tests.factories import (
    AssessmentFactory,
    CompetencyFactory,
    CompetencyRubricVersionFactory,
    TrainingPlacementFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Assessment Institute")
    department = DepartmentFactory(institution=institution, name="Surgery")
    trainee = UserFactory(email="as-trainee@example.test")
    RoleAssignmentFactory(
        user=trainee, role=UserRole.TRAINEE, institution=institution, department=department
    )
    supervisor = UserFactory(email="as-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    examiner = UserFactory(email="as-examiner@example.test")
    RoleAssignmentFactory(
        user=examiner, role=UserRole.EXAMINER, institution=institution
    )
    manager = UserFactory(email="as-manager@example.test")
    RoleAssignmentFactory(
        user=manager, role=UserRole.DEPARTMENT_MANAGER, institution=institution
    )
    placement = TrainingPlacementFactory(
        institution=institution,
        department=department,
        trainee=trainee,
        supervisor=supervisor,
        title="Surgical assessment rotation",
    )
    competency = CompetencyFactory(
        institution=institution, code="SAFE-CHOLE", title="Safe cholecystectomy"
    )
    rubric = CompetencyRubricVersionFactory(competency=competency)
    return SimpleNamespace(
        institution=institution,
        department=department,
        trainee=trainee,
        supervisor=supervisor,
        examiner=examiner,
        manager=manager,
        placement=placement,
        competency=competency,
        rubric=rubric,
    )


def _payload(world, **overrides):
    payload = {
        "placement": world.placement.pk,
        "competency": world.competency.pk,
        "scores": {
            "planning": "competent",
            "technique": "advanced_beginner",
            "safety": "competent",
            "professionalism": "proficient",
        },
        "overall_level": "competent",
        "feedback": "Solid fundamentals under supervision.",
    }
    payload.update(overrides)
    return payload


class TestAssessmentCreation:
    def test_supervisor_creates_draft_assessment(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.post("/api/v1/assessments/", _payload(world))
        assert response.status_code == 201, response.data
        assert response.data["status"] == AssessmentStatus.DRAFT
        assert response.data["rubric_version"] == world.rubric.pk
        assert response.data["assessor_detail"]["email"] == world.supervisor.email

    def test_trainee_cannot_assess(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post("/api/v1/assessments/", _payload(world))
        assert response.status_code == 403, response.data

    def test_unassigned_examiner_cannot_assess(self, client_factory, world):
        client = client_factory(world.examiner)
        response = client.post("/api/v1/assessments/", _payload(world))
        assert response.status_code == 403

    def test_assigned_examiner_can_assess(self, client_factory, world):
        supervisor = client_factory(world.supervisor)
        supervisor.post(
            f"/api/v1/training/placements/{world.placement.pk}/examiners/",
            {"examiner": world.examiner.pk},
        )
        client = client_factory(world.examiner)
        response = client.post("/api/v1/assessments/", _payload(world))
        assert response.status_code == 201, response.data
        assert response.data["assessor_detail"]["email"] == world.examiner.email

    def test_unknown_criterion_rejected(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/assessments/",
            _payload(world, scores={"made_up": "competent"}),
        )
        assert response.status_code == 400
        details = error_details(response)
        assert "scores" in details or "non_field_errors" in details

    def test_unknown_level_rejected(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/assessments/", _payload(world, overall_level="legendary")
        )
        assert response.status_code == 400

    def test_competency_from_other_institution_rejected(self, client_factory, world):
        foreign_competency = CompetencyFactory(
            institution=InstitutionFactory(name="Foreign Assessment Institute")
        )
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/assessments/", _payload(world, competency=foreign_competency.pk)
        )
        assert response.status_code == 400
        assert "competency" in error_details(response)

    def test_competency_without_rubric_rejected(self, client_factory, world):
        rubricless = CompetencyFactory(
            institution=world.institution, code="NO-RUBRIC", title="No rubric yet"
        )
        client = client_factory(world.supervisor)
        response = client.post(
            "/api/v1/assessments/", _payload(world, competency=rubricless.pk)
        )
        assert response.status_code == 400
        assert "rubric_version" in error_details(response)


@pytest.fixture
def submitted(world) -> Assessment:
    assessment = AssessmentFactory(
        placement=world.placement,
        competency=world.competency,
        rubric_version=world.rubric,
        assessor=world.supervisor,
    )
    assessment.status = AssessmentStatus.SUBMITTED
    assessment.save()
    return assessment


class TestAssessmentWorkflow:
    def test_submit_requires_scores(self, client_factory, world):
        assessment = AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
            scores={},
            overall_level="",
        )
        client = client_factory(world.supervisor)
        response = client.post(f"/api/v1/assessments/{assessment.pk}/submit/")
        assert response.status_code == 400
        assert "scores" in error_details(response)

    def test_only_assessor_submits(self, client_factory, world, submitted):
        client = client_factory(world.manager)
        response = client.post(f"/api/v1/assessments/{submitted.pk}/submit/")
        assert response.status_code == 403

    def test_unassigned_examiner_cannot_even_see_it(self, client_factory, world, submitted):
        client = client_factory(world.examiner)
        assert (
            client.get(f"/api/v1/assessments/{submitted.pk}/").status_code == 404
        )

    def test_assessor_cannot_self_approve(self, client_factory, world, submitted):
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/assessments/{submitted.pk}/decide/", {"decision": "approved"}
        )
        assert response.status_code == 403
        submitted.refresh_from_db()
        assert submitted.status == AssessmentStatus.SUBMITTED

    def test_supervisor_approves(self, client_factory, world):
        assessment = AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.manager,
        )
        assessment.status = AssessmentStatus.SUBMITTED
        assessment.save()
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/assessments/{assessment.pk}/decide/",
            {"decision": "approved", "feedback": "Meets the standard."},
        )
        assert response.status_code == 200, response.data
        assert response.data["status"] == AssessmentStatus.APPROVED
        assert response.data["decided_by_detail"]["email"] == world.supervisor.email
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.ASSESSMENT_DECIDED
        ).exists()

    def test_correction_requires_reason(self, client_factory, world, submitted):
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/assessments/{submitted.pk}/decide/",
            {"decision": "needs_correction"},
        )
        assert response.status_code == 400
        assert "reason" in error_details(response)

    def test_correction_then_resubmit_then_approve(self, client_factory, world):
        assessment = AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
        )
        assessor_client = client_factory(world.supervisor)
        assert (
            assessor_client.post(f"/api/v1/assessments/{assessment.pk}/submit/").status_code
            == 200
        )

        manager_client = client_factory(world.manager)
        correction = manager_client.post(
            f"/api/v1/assessments/{assessment.pk}/decide/",
            {
                "decision": "needs_correction",
                "reason": "Add the safety criterion justification.",
            },
        )
        assert correction.status_code == 200
        assert correction.data["status"] == AssessmentStatus.NEEDS_CORRECTION

        edit = assessor_client.patch(
            f"/api/v1/assessments/{assessment.pk}/",
            {"feedback": "Expanded safety justification."},
        )
        assert edit.status_code == 200, edit.data

        resubmit = assessor_client.post(f"/api/v1/assessments/{assessment.pk}/submit/")
        assert resubmit.status_code == 200
        assert resubmit.data["status"] == AssessmentStatus.SUBMITTED

        approve = manager_client.post(
            f"/api/v1/assessments/{assessment.pk}/decide/", {"decision": "approved"}
        )
        assert approve.status_code == 200
        assert approve.data["status"] == AssessmentStatus.APPROVED

    def test_locked_after_approval(self, client_factory, world, submitted):
        manager = client_factory(world.manager)
        manager.post(
            f"/api/v1/assessments/{submitted.pk}/decide/", {"decision": "approved"}
        )
        assessor = client_factory(world.supervisor)
        edit = assessor.patch(
            f"/api/v1/assessments/{submitted.pk}/", {"feedback": "changed"}
        )
        assert edit.status_code == 400
        assert "status" in error_details(edit)

    def test_decide_requires_submitted_status(self, client_factory, world):
        draft = AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
        )
        client = client_factory(world.manager)
        response = client.post(
            f"/api/v1/assessments/{draft.pk}/decide/", {"decision": "approved"}
        )
        assert response.status_code == 400
        assert "status" in error_details(response)

    def test_unassigned_examiner_cannot_decide(self, client_factory, world, submitted):
        client = client_factory(world.examiner)
        response = client.post(
            f"/api/v1/assessments/{submitted.pk}/decide/", {"decision": "approved"}
        )
        assert response.status_code == 404

    def test_assigned_examiner_can_decide(self, client_factory, world, submitted):
        client_factory(world.supervisor).post(
            f"/api/v1/training/placements/{world.placement.pk}/examiners/",
            {"examiner": world.examiner.pk},
        )
        client = client_factory(world.examiner)
        response = client.post(
            f"/api/v1/assessments/{submitted.pk}/decide/", {"decision": "approved"}
        )
        assert response.status_code == 200, response.data
        assert response.data["status"] == AssessmentStatus.APPROVED


class TestAssessmentIsolation:
    def test_out_of_scope_assessment_is_404(self, client_factory, world, submitted):
        outsider = UserFactory(email="as-outsider@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.SUPERVISOR,
            institution=InstitutionFactory(name="Outside Institute"),
        )
        client = client_factory(outsider)
        base = f"/api/v1/assessments/{submitted.pk}"
        assert client.get(base + "/").status_code == 404
        assert client.post(base + "/submit/").status_code == 404
        assert (
            client.post(base + "/decide/", {"decision": "approved"}).status_code == 404
        )

    def test_trainee_sees_own_assessments(self, client_factory, world):
        AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
        )
        client = client_factory(world.trainee)
        data = client.get("/api/v1/assessments/").data
        assert data["count"] == 1
        assert data["results"][0]["trainee_detail"]["email"] == world.trainee.email

    def test_other_trainee_does_not_see_them(self, client_factory, world):
        AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
        )
        other = UserFactory(email="as-other-trainee@example.test")
        RoleAssignmentFactory(
            user=other, role=UserRole.TRAINEE, institution=world.institution
        )
        client = client_factory(other)
        assert client.get("/api/v1/assessments/").data["count"] == 0
        assessment_id = Assessment.objects.first().pk
        assert (
            client.get(f"/api/v1/assessments/{assessment_id}/").status_code == 404
        )

    def test_marketplace_account_sees_nothing(self, client_factory, world):
        supplier = UserFactory(email="as-supplier@example.test")
        RoleAssignmentFactory(user=supplier, role=UserRole.SUPPLIER, institution=None)
        client = client_factory(supplier)
        assert client.get("/api/v1/assessments/").data["count"] == 0


class TestProgressTracking:
    @pytest.fixture
    def progress_world(self, world):
        approved = SurgicalProcedureFactory(
            institution=world.institution,
            department=world.department,
            author=world.trainee,
            procedure_name="Approved case",
            status="approved",
        )
        awaiting = SurgicalProcedureFactory(
            institution=world.institution,
            author=world.trainee,
            procedure_name="Awaiting case",
            status="submitted",
        )
        assisted = SurgicalProcedureFactory(
            institution=world.institution,
            author=world.supervisor,
            procedure_name="Assisted case",
        )
        ProcedureParticipantFactory(procedure=assisted, user=world.trainee, role="assistant")
        observed = SurgicalProcedureFactory(
            institution=world.institution,
            author=world.supervisor,
            procedure_name="Observed case",
        )
        ProcedureParticipantFactory(procedure=observed, user=world.trainee, role="observer")
        world.placement.expected_competencies.add(world.competency)
        world.placement.save()
        return SimpleNamespace(
            approved=approved,
            awaiting=awaiting,
            assisted=assisted,
            observed=observed,
        )

    def test_progress_counts_and_competency_state(self, client_factory, world, progress_world):
        approved_assessment = AssessmentFactory(
            placement=world.placement,
            competency=world.competency,
            rubric_version=world.rubric,
            assessor=world.supervisor,
        )
        approved_assessment.status = AssessmentStatus.APPROVED
        approved_assessment.save()

        client = client_factory(world.trainee)
        response = client.get(
            f"/api/v1/training/placements/{world.placement.pk}/progress/"
        )
        assert response.status_code == 200, response.data

        procedures = response.data["procedures"]
        assert procedures["performed"] == 2
        assert procedures["assisted"] == 1
        assert procedures["observed"] == 1
        assert procedures["awaiting_review"] == 1
        assert procedures["approved"] == 1

        progress = response.data["competency_progress"]
        assert len(progress) == 1
        assert progress[0]["code"] == world.competency.code
        assert progress[0]["approved"] is True
        assert progress[0]["overall_level"] == "competent"

        assert response.data["assessments"]["approved"] == 1

    def test_progress_requires_visibility(self, client_factory, world, progress_world):
        outsider = UserFactory(email="as-outsider-progress@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.SUPERVISOR,
            institution=InstitutionFactory(name="Progress Foreign Institute"),
        )
        client = client_factory(outsider)
        response = client.get(
            f"/api/v1/training/placements/{world.placement.pk}/progress/"
        )
        assert response.status_code == 404
