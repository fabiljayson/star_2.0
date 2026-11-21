from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.core.models import AuditEvent
from apps.logbook.tests.factories import SurgicalProcedureFactory
from apps.notifications.models import Notification, NotificationCategory
from apps.organizations.tests.factories import InstitutionFactory
from apps.training.models import AssessmentStatus
from apps.training.tests.factories import (
    AssessmentFactory,
    CompetencyFactory,
    CompetencyRubricVersionFactory,
    TrainingPlacementFactory,
)

pytestmark = pytest.mark.django_db

CLINICAL_MARKER = "TOP-SECRET-CLINICAL-DETAIL-9f3a"


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Notify Institute")
    trainee = UserFactory(email="nt-trainee@example.test")
    RoleAssignmentFactory(user=trainee, role=UserRole.TRAINEE, institution=institution)
    supervisor = UserFactory(email="nt-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    examiner = UserFactory(email="nt-examiner@example.test")
    RoleAssignmentFactory(
        user=examiner, role=UserRole.EXAMINER, institution=institution
    )
    procedure = SurgicalProcedureFactory(
        institution=institution,
        author=trainee,
        procedure_name="Notified case",
        summary=f"Operative summary {CLINICAL_MARKER}",
    )
    return SimpleNamespace(
        institution=institution,
        trainee=trainee,
        supervisor=supervisor,
        examiner=examiner,
        procedure=procedure,
    )


class TestClinicalTriggers:
    def test_submission_notifies_reviewers_not_author(self, client_factory, world):
        client = client_factory(world.trainee)
        assert (
            client.post(f"/api/v1/procedures/{world.procedure.pk}/submit/").status_code
            == 200
        )

        def categories(user):
            return set(
                Notification.objects.filter(recipient=user).values_list(
                    "category", flat=True
                )
            )

        assert NotificationCategory.PROCEDURE_SUBMITTED in categories(world.supervisor)
        assert NotificationCategory.PROCEDURE_SUBMITTED in categories(world.examiner)
        assert categories(world.trainee) == set()

    def test_approval_notifies_author_without_clinical_text(
        self, client_factory, world
    ):
        submit = client_factory(world.trainee)
        submit.post(f"/api/v1/procedures/{world.procedure.pk}/submit/")
        review = client_factory(world.supervisor)
        response = review.post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/", {"decision": "approve"}
        )
        assert response.status_code == 200, response.data

        notification = Notification.objects.get(
            recipient=world.trainee, category=NotificationCategory.PROCEDURE_APPROVED
        )
        assert world.procedure.reference in notification.title
        blob = f"{notification.title} {notification.body}"
        assert CLINICAL_MARKER not in blob
        assert "Operative summary" not in blob

    def test_return_for_correction_notifies_author(self, client_factory, world):
        client_factory(world.trainee).post(
            f"/api/v1/procedures/{world.procedure.pk}/submit/"
        )
        response = client_factory(world.supervisor).post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/",
            {"decision": "request_correction", "reason": "Clarify steps."},
        )
        assert response.status_code == 200
        assert Notification.objects.filter(
            recipient=world.trainee,
            category=NotificationCategory.PROCEDURE_RETURNED,
        ).exists()

    def test_transcription_failure_notified_only_in_audit(self, client_factory, world):
        # Audit row exists; notifications are not used for provider outages.
        upload = SimpleUploadedFile(
            "dictation.wav", b"RIFF" + b"\x00" * 4 + b"WAVE" + b"fmt " + b"\x00" * 24,
            content_type="audio/wav",
        )
        with override_settings(TRANSCRIPTION_MOCK_FAILURE=True):
            response = client_factory(world.trainee).post(
                f"/api/v1/procedures/{world.procedure.pk}/transcribe/",
                {"audio": upload},
                format="multipart",
            )
        assert response.status_code == 503, response.data
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.TRANSCRIPTION_FAILED
        ).exists()
        assert Notification.objects.count() == 0


class TestTrainingTriggers:
    @pytest.fixture
    def training(self, world):
        placement = TrainingPlacementFactory(
            institution=world.institution,
            trainee=world.trainee,
            supervisor=world.supervisor,
            title="Notification rotation",
        )
        competency = CompetencyFactory(
            institution=world.institution, code="NT-COMP", title="Notify competency"
        )
        rubric = CompetencyRubricVersionFactory(competency=competency)
        return SimpleNamespace(
            placement=placement, competency=competency, rubric=rubric
        )

    def test_examiner_assignment_notifies_examiner(self, client_factory, world, training):
        client = client_factory(world.supervisor)
        response = client.post(
            f"/api/v1/training/placements/{training.placement.pk}/examiners/",
            {"examiner": world.examiner.pk},
        )
        assert response.status_code == 201
        assert Notification.objects.filter(
            recipient=world.examiner,
            category=NotificationCategory.EXAMINER_ASSIGNED,
        ).exists()

    def test_assessment_submission_notifies_deciders_except_assessor(
        self, client_factory, world, training
    ):
        manager = UserFactory(email="nt-manager@example.test")
        RoleAssignmentFactory(
            user=manager,
            role=UserRole.DEPARTMENT_MANAGER,
            institution=world.institution,
        )
        assessment = AssessmentFactory(
            placement=training.placement,
            competency=training.competency,
            rubric_version=training.rubric,
            assessor=world.supervisor,
        )
        client = client_factory(world.supervisor)
        assert (
            client.post(f"/api/v1/assessments/{assessment.pk}/submit/").status_code
            == 200
        )
        assert Notification.objects.filter(
            recipient=manager,
            category=NotificationCategory.ASSESSMENT_SUBMITTED,
        ).exists()
        assert not Notification.objects.filter(
            recipient=world.supervisor,
            category=NotificationCategory.ASSESSMENT_SUBMITTED,
        ).exists()
        # An examiner who was never assigned to this placement is not a decider.
        assert not Notification.objects.filter(
            recipient=world.examiner,
            category=NotificationCategory.ASSESSMENT_SUBMITTED,
        ).exists()

    def test_assessment_approval_notifies_trainee(
        self, client_factory, world, training
    ):
        assessment = AssessmentFactory(
            placement=training.placement,
            competency=training.competency,
            rubric_version=training.rubric,
            assessor=world.supervisor,
        )
        assessment.status = AssessmentStatus.SUBMITTED
        assessment.save()
        # An unassigned examiner cannot even see the assessment (404 by design).
        assert (
            client_factory(world.examiner).post(
                f"/api/v1/assessments/{assessment.pk}/decide/",
                {"decision": "approved"},
            ).status_code
            == 404
        )
        client_factory(world.supervisor).post(
            f"/api/v1/training/placements/{training.placement.pk}/examiners/",
            {"examiner": world.examiner.pk},
        )
        response = client_factory(world.examiner).post(
            f"/api/v1/assessments/{assessment.pk}/decide/", {"decision": "approved"}
        )
        assert response.status_code == 200, response.data
        assert Notification.objects.filter(
            recipient=world.trainee,
            category=NotificationCategory.ASSESSMENT_RESULT,
        ).exists()
        assert not Notification.objects.filter(
            recipient=world.supervisor,
            category=NotificationCategory.ASSESSMENT_RESULT,
        ).exists()

    def test_correction_request_notifies_assessor(
        self, client_factory, world, training
    ):
        assessment = AssessmentFactory(
            placement=training.placement,
            competency=training.competency,
            rubric_version=training.rubric,
            assessor=world.supervisor,
        )
        assessment.status = AssessmentStatus.SUBMITTED
        assessment.save()
        manager = UserFactory(email="nt-manager@example.test")
        RoleAssignmentFactory(
            user=manager, role=UserRole.DEPARTMENT_MANAGER, institution=world.institution
        )
        response = client_factory(manager).post(
            f"/api/v1/assessments/{assessment.pk}/decide/",
            {"decision": "needs_correction", "reason": "Elaborate."},
        )
        assert response.status_code == 200
        assert Notification.objects.filter(
            recipient=world.supervisor,
            category=NotificationCategory.ASSESSMENT_CORRECTION,
        ).exists()
        assert not Notification.objects.filter(
            recipient=manager,
            category=NotificationCategory.ASSESSMENT_CORRECTION,
        ).exists()


class TestNotificationCenter:
    @pytest.fixture
    def two_notifications(self, world) -> list:
        Notification.objects.create(
            recipient=world.trainee,
            category=NotificationCategory.PROCEDURE_APPROVED,
            title="One",
        )
        Notification.objects.create(
            recipient=world.trainee,
            category=NotificationCategory.PROCEDURE_RETURNED,
            title="Two",
        )
        Notification.objects.create(
            recipient=world.supervisor,
            category=NotificationCategory.PROCEDURE_SUBMITTED,
            title="Other user",
        )
        return list(Notification.objects.filter(recipient=world.trainee))

    def test_list_is_recipient_scoped(self, client_factory, world, two_notifications):
        client = client_factory(world.trainee)
        data = client.get("/api/v1/notifications/").data
        assert data["count"] == 2
        assert all(row["title"] != "Other user" for row in data["results"])

    def test_unread_count_and_mark_read(self, client_factory, world, two_notifications):
        client = client_factory(world.trainee)
        assert client.get("/api/v1/notifications/unread-count/").data == {"count": 2}

        first = two_notifications[0]
        response = client.post(f"/api/v1/notifications/{first.pk}/read/")
        assert response.status_code == 200
        assert response.data["is_read"] is True
        assert client.get("/api/v1/notifications/unread-count/").data == {"count": 1}

    def test_read_all(self, client_factory, world, two_notifications):
        client = client_factory(world.trainee)
        response = client.post("/api/v1/notifications/read-all/")
        assert response.data["updated"] == 2
        assert client.get("/api/v1/notifications/unread-count/").data == {"count": 0}

    def test_cannot_read_another_users_notification(self, client_factory, world):
        foreign = Notification.objects.create(
            recipient=world.supervisor,
            category=NotificationCategory.PROCEDURE_SUBMITTED,
            title="Supervisor only",
        )
        client = client_factory(world.trainee)
        assert (
            client.post(f"/api/v1/notifications/{foreign.pk}/read/").status_code == 404
        )
        foreign.refresh_from_db()
        assert foreign.is_read is False

    def test_marketplace_account_has_empty_center(self, client_factory, world):
        supplier = UserFactory(email="nt-supplier@example.test")
        RoleAssignmentFactory(user=supplier, role=UserRole.SUPPLIER, institution=None)
        client = client_factory(supplier)
        assert client.get("/api/v1/notifications/").data["count"] == 0


class TestPreferences:
    def test_defaults_list_every_category_in_app_on(self, client_factory, world):
        client = client_factory(world.trainee)
        data = client.get("/api/v1/notifications/preferences/").data
        assert len(data) == len(NotificationCategory.values)
        assert all(row["in_app"] is True for row in data)
        # Email is not a delivered channel yet, so it must not be advertised.
        assert all("email" not in row for row in data)

    def test_preference_blocks_future_notifications(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.put(
            "/api/v1/notifications/preferences/",
            {
                "preferences": [
                    {"category": NotificationCategory.PROCEDURE_APPROVED, "in_app": False}
                ]
            },
        )
        assert response.status_code == 200, response.data

        client.post(f"/api/v1/procedures/{world.procedure.pk}/submit/")
        client_factory(world.supervisor).post(
            f"/api/v1/procedures/{world.procedure.pk}/reviews/", {"decision": "approve"}
        )
        assert not Notification.objects.filter(
            recipient=world.trainee,
            category=NotificationCategory.PROCEDURE_APPROVED,
        ).exists()
        # other categories still delivered
        assert Notification.objects.filter(
            recipient=world.supervisor,
            category=NotificationCategory.PROCEDURE_SUBMITTED,
        ).exists()

    def test_email_channel_is_rejected_until_implemented(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.put(
            "/api/v1/notifications/preferences/",
            {
                "preferences": [
                    {"category": NotificationCategory.PROCEDURE_APPROVED, "email": True}
                ]
            },
        )
        assert response.status_code == 400

    def test_unknown_category_rejected(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.put(
            "/api/v1/notifications/preferences/",
            {"preferences": [{"category": "bogus", "in_app": False}]},
        )
        assert response.status_code == 400

    def test_one_preference_row_is_upserted_not_duplicated(self, client_factory, world):
        client = client_factory(world.trainee)
        payload = {
            "preferences": [
                {"category": NotificationCategory.PROCEDURE_APPROVED, "in_app": False}
            ]
        }
        client.put("/api/v1/notifications/preferences/", payload)
        client.put("/api/v1/notifications/preferences/", payload)
        from apps.notifications.models import NotificationPreference

        assert NotificationPreference.objects.filter(
            user=world.trainee, category=NotificationCategory.PROCEDURE_APPROVED
        ).count() == 1
