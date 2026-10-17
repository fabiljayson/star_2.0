from types import SimpleNamespace

import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.logbook.models import (
    ProcedureNoteVersion,
    ProcedureStatus,
    ReviewDecision,
    VersionChangeKind,
)
from apps.logbook.tests.factories import (
    PatientReferenceFactory,
    ProcedureParticipantFactory,
    SurgicalProcedureFactory,
)
from apps.organizations.tests.factories import DepartmentFactory, InstitutionFactory

from .helpers import error_details

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Alpha Surgical Institute")
    department = DepartmentFactory(institution=institution, name="General Surgery")
    trainee = UserFactory(email="log-trainee@example.test")
    RoleAssignmentFactory(
        user=trainee, role=UserRole.TRAINEE, institution=institution, department=department
    )
    supervisor = UserFactory(email="log-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    examiner = UserFactory(email="log-examiner@example.test")
    RoleAssignmentFactory(
        user=examiner, role=UserRole.EXAMINER, institution=institution
    )
    procedure = SurgicalProcedureFactory(
        institution=institution,
        department=department,
        author=trainee,
        procedure_name="Laparoscopic cholecystectomy",
    )
    return SimpleNamespace(
        institution=institution,
        department=department,
        trainee=trainee,
        supervisor=supervisor,
        examiner=examiner,
        procedure=procedure,
    )


def _payload(**overrides):
    payload = {
        "procedure_date": "2026-09-20",
        "procedure_name": "Inguinal hernia repair",
        "category": "elective",
        "indication": "Reducible right inguinal hernia",
        "summary": "Open Lichtenstein repair, mesh placed.",
    }
    payload.update(overrides)
    return payload


class TestCreationAndDraft:
    def test_trainee_can_create_draft_in_own_institution(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post(
            "/api/v1/procedures/",
            {**_payload(), "institution": world.institution.pk, "department": world.department.pk},
        )
        assert response.status_code == 201, response.data
        assert response.data["status"] == "draft"
        assert response.data["author_detail"]["email"] == world.trainee.email
        assert response.data["reference"].startswith("STAR-")

    def test_patient_reference_must_belong_to_same_institution(
        self, client_factory, world
    ):
        other = InstitutionFactory(name="Beta Institute")
        foreign_ref = PatientReferenceFactory(institution=other)
        client = client_factory(world.trainee)
        response = client.post(
            "/api/v1/procedures/",
            {
                **_payload(),
                "institution": world.institution.pk,
                "patient_reference": foreign_ref.pk,
            },
        )
        assert response.status_code == 400
        assert "patient_reference" in error_details(response)

    def test_draft_edit_keeps_single_version(self, client_factory, world):
        client = client_factory(world.trainee)
        url = f"/api/v1/procedures/{world.procedure.pk}/"
        response = client.patch(url, {"summary": "Draft note updated."})
        assert response.status_code == 200, response.data
        assert response.data["version"] == 1
        assert not ProcedureNoteVersion.objects.filter(procedure=world.procedure).exists()

    def test_non_author_cannot_edit(self, client_factory, world):
        ProcedureParticipantFactory(
            procedure=world.procedure, user=world.supervisor, role="assistant"
        )
        client = client_factory(world.supervisor)
        response = client.patch(
            f"/api/v1/procedures/{world.procedure.pk}/", {"summary": "Hijacked."}
        )
        assert response.status_code == 403
        world.procedure.refresh_from_db()
        assert world.procedure.summary != "Hijacked."


class TestSubmissionAndReview:
    def test_full_review_cycle_to_approval(self, client_factory, world):
        author = client_factory(world.trainee)
        url = f"/api/v1/procedures/{world.procedure.pk}/"

        submitted = author.post(f"{url}submit/")
        assert submitted.status_code == 200
        assert submitted.data["status"] == ProcedureStatus.SUBMITTED
        assert ProcedureNoteVersion.objects.filter(
            procedure=world.procedure, change_kind=VersionChangeKind.SUBMITTED
        ).exists()

        reviewer = client_factory(world.supervisor)
        started = reviewer.post(f"{url}reviews/", {"decision": "start_review"})
        assert started.status_code == 200
        assert started.data["procedure"]["status"] == ProcedureStatus.UNDER_REVIEW

        approved = reviewer.post(f"{url}reviews/", {"decision": "approve"})
        assert approved.status_code == 200
        assert approved.data["procedure"]["status"] == ProcedureStatus.APPROVED
        assert approved.data["procedure"]["approved_at"] is not None
        assert ReviewDecision.objects.filter(
            procedure=world.procedure, decision="approve", reviewer=world.supervisor
        ).exists()

    def test_return_requires_reason(self, client_factory, world):
        client_factory(world.trainee).post(f"/api/v1/procedures/{world.procedure.pk}/submit/")
        reviewer = client_factory(world.supervisor)
        response = reviewer.post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/",
            {"decision": "request_correction"},
        )
        assert response.status_code == 400
        assert "reason" in error_details(response)

    def test_return_with_reason_then_resubmit_and_approve(self, client_factory, world):
        url = f"/api/v1/procedures/{world.procedure.pk}/submit/"
        author = client_factory(world.trainee)
        author.post(url)

        reviewer = client_factory(world.examiner)
        returned = reviewer.post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/",
            {"decision": "request_correction", "reason": "Add postoperative plan."},
        )
        assert returned.status_code == 200
        assert returned.data["procedure"]["status"] == ProcedureStatus.RETURNED

        edited = author.patch(
            f"/api/v1/procedures/{world.procedure.pk}/",
            {"postoperative": "Day-case, review in 7 days."},
        )
        assert edited.status_code == 200
        resubmitted = author.post(url)
        assert resubmitted.status_code == 200
        assert resubmitted.data["status"] == ProcedureStatus.SUBMITTED

        approved = reviewer.post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/", {"decision": "approve"}
        )
        assert approved.status_code == 200
        assert approved.data["procedure"]["status"] == ProcedureStatus.APPROVED

    def test_author_cannot_review_own_record(self, client_factory, world):
        RoleAssignmentFactory(
            user=world.trainee, role=UserRole.SUPERVISOR, institution=world.institution
        )
        client_factory(world.trainee).post(
            f"/api/v1/procedures/{world.procedure.pk}/submit/"
        )
        response = client_factory(world.trainee).post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/",
            {"decision": "approve"},
        )
        assert response.status_code == 403
        world.procedure.refresh_from_db()
        assert world.procedure.status == ProcedureStatus.SUBMITTED

    def test_supervisor_of_other_institution_cannot_review(
        self, client_factory, world
    ):
        other = InstitutionFactory(name="Gamma Institute")
        outsider = UserFactory(email="outsider-sup@example.test")
        RoleAssignmentFactory(
            user=outsider, role=UserRole.SUPERVISOR, institution=other
        )
        client_factory(world.trainee).post(
            f"/api/v1/procedures/{world.procedure.pk}/submit/"
        )
        response = client_factory(outsider).post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/",
            {"decision": "approve"},
        )
        assert response.status_code == 404

    def test_cannot_submit_twice_or_approve_draft(self, client_factory, world):
        author = client_factory(world.trainee)
        url = f"/api/v1/procedures/{world.procedure.pk}/"
        author.post(f"{url}submit/")
        second = author.post(f"{url}submit/")
        assert second.status_code == 400

        fresh = SurgicalProcedureFactory(institution=world.institution, author=world.trainee)
        response = client_factory(world.supervisor).post(
            f"/api/v1/procedures/{fresh.pk}/reviews/", {"decision": "approve"}
        )
        assert response.status_code == 400


class TestApprovedRecordCorrection:
    def test_post_approval_edit_creates_version_and_resubmits(
        self, client_factory, world
    ):
        url = f"/api/v1/procedures/{world.procedure.pk}/"
        author = client_factory(world.trainee)
        author.post(f"{url}submit/")
        reviewer = client_factory(world.supervisor)
        reviewer.post(f"{url}reviews/", {"decision": "approve"})

        corrected = author.patch(f"{url}", {"summary": "Corrected operative note."})
        assert corrected.status_code == 200
        world.procedure.refresh_from_db()
        assert world.procedure.status == ProcedureStatus.SUBMITTED
        assert world.procedure.version == 2
        assert world.procedure.approved_at is None

        version = ProcedureNoteVersion.objects.get(
            procedure=world.procedure, change_kind=VersionChangeKind.CORRECTION
        )
        assert version.snapshot["summary"] != "Corrected operative note."
        assert version.snapshot["procedure_name"] == "Laparoscopic cholecystectomy"

    def test_submitted_record_is_locked(self, client_factory, world):
        url = f"/api/v1/procedures/{world.procedure.pk}/"
        author = client_factory(world.trainee)
        author.post(f"{url}submit/")
        response = author.patch(f"{url}", {"summary": "Sneaky edit."})
        assert response.status_code == 400
        assert "status" in error_details(response)

    def test_archived_record_is_locked(self, client_factory, world):
        url = f"/api/v1/procedures/{world.procedure.pk}/"
        author = client_factory(world.trainee)
        author.post(f"{url}submit/")
        reviewer = client_factory(world.supervisor)
        reviewer.post(f"{url}reviews/", {"decision": "approve"})
        archived = reviewer.post(f"{url}archive/")
        assert archived.status_code == 200
        assert archived.data["status"] == ProcedureStatus.ARCHIVED

        response = author.patch(f"{url}", {"summary": "Edit after archive."})
        assert response.status_code == 400

    def test_archiving_requires_approval(self, client_factory, world):
        response = client_factory(world.supervisor).post(
            f"/api/v1/procedures/{world.procedure.pk}/archive/"
        )
        assert response.status_code == 403


class TestParticipants:
    def test_author_can_add_and_remove_participant(self, client_factory, world):
        assistant = UserFactory(email="assistant@example.test")
        client = client_factory(world.trainee)
        base = f"/api/v1/procedures/{world.procedure.pk}/participants/"

        added = client.post(base, {"user": assistant.pk, "role": "assistant"})
        assert added.status_code == 201, added.data
        duplicate = client.post(base, {"user": assistant.pk, "role": "observer"})
        assert duplicate.status_code == 400

        participant_id = added.data["id"]
        removed = client.delete(f"{base}{participant_id}/")
        assert removed.status_code == 204
        assert not world.procedure.participants.filter(user=assistant).exists()

    def test_non_author_cannot_manage_participants(self, client_factory, world):
        target = UserFactory(email="target@example.test")
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/procedures/{world.procedure.pk}/participants/",
            {"user": target.pk, "role": "assistant"},
        )
        assert response.status_code == 403

    def test_author_cannot_be_added_as_participant(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post(
            f"/api/v1/procedures/{world.procedure.pk}/participants/",
            {"user": world.trainee.pk, "role": "assistant"},
        )
        assert response.status_code == 400


class TestFilters:
    def test_list_only_returns_visible_records(self, client_factory, world):
        other_institution = InstitutionFactory(name="Delta Institute")
        hidden = SurgicalProcedureFactory(
            institution=other_institution, procedure_name="Secret case"
        )
        mine = SurgicalProcedureFactory(institution=world.institution, author=world.trainee)

        client = client_factory(world.trainee)
        response = client.get("/api/v1/procedures/")
        assert response.status_code == 200
        references = {row["reference"] for row in response.data["results"]}
        assert world.procedure.reference in references
        assert mine.reference in references
        assert hidden.reference not in references

        search = client.get("/api/v1/procedures/", {"search": "Secret"})
        assert search.data["results"] == []

    def test_mine_and_status_filters(self, client_factory, world):
        other_author = UserFactory(email="other-author@example.test")
        SurgicalProcedureFactory(
            institution=world.institution, author=other_author, procedure_name="Their case"
        )
        client = client_factory(world.trainee)
        mine = client.get("/api/v1/procedures/", {"mine": "1"})
        references = {row["reference"] for row in mine.data["results"]}
        assert references == {world.procedure.reference}

        empty = client.get("/api/v1/procedures/", {"status": "approved"})
        assert empty.data["results"] == []

    def test_participant_role_filter(self, client_factory, world):
        colleague = UserFactory(email="colleague@example.test")
        ProcedureParticipantFactory(
            procedure=world.procedure, user=colleague, role="primary_operator"
        )
        client = client_factory(colleague)
        response = client.get(
            "/api/v1/procedures/", {"participant_role": "primary_operator"}
        )
        references = {row["reference"] for row in response.data["results"]}
        assert references == {world.procedure.reference}

        none = client.get("/api/v1/procedures/", {"participant_role": "observer"})
        assert none.data["results"] == []
