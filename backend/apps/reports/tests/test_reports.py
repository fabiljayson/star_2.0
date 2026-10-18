from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.core.models import AuditEvent
from apps.logbook.tests.factories import (
    PatientReferenceFactory,
    ProcedureParticipantFactory,
    SurgicalProcedureFactory,
)
from apps.organizations.tests.factories import InstitutionFactory
from apps.reports.models import ReportJob, ReportStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Report Institute")
    supervisor = UserFactory(email="rp-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    trainee = UserFactory(email="rp-trainee@example.test")
    RoleAssignmentFactory(user=trainee, role=UserRole.TRAINEE, institution=institution)
    manager = UserFactory(email="rp-manager@example.test")
    RoleAssignmentFactory(
        user=manager, role=UserRole.DEPARTMENT_MANAGER, institution=institution
    )
    procedure = SurgicalProcedureFactory(
        institution=institution,
        author=trainee,
        procedure_name="Cholecystectomy",
        category="elective",
    )
    return SimpleNamespace(
        institution=institution,
        supervisor=supervisor,
        trainee=trainee,
        manager=manager,
        procedure=procedure,
    )


def request_report(client, payload):
    return client.post("/api/v1/reports/", payload, format="json")


def base_payload(world, report_type, fmt="csv", **parameters):
    return {
        "institution": str(world.institution.pk),
        "report_type": report_type,
        "format": fmt,
        "parameters": parameters,
    }


def read_artifact(job) -> bytes:
    return job.artifact.open("rb").read()


class TestPermissions:
    def test_trainee_cannot_request_aggregate_report(self, client_factory, world):
        client = client_factory(world.trainee)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 403
        assert response.data["error"]["code"] == "permission_denied"

    def test_supervisor_can_request_aggregate_report(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 201, response.data
        assert response.data["status"] == "succeeded"
        assert response.data["row_count"] == 1

    def test_out_of_scope_institution_is_denied(self, client_factory, world):
        foreign = InstitutionFactory(name="Report Foreign Institute")
        client = client_factory(world.supervisor)
        response = request_report(
            client,
            {
                "institution": str(foreign.pk),
                "report_type": "activity_by_date",
                "format": "csv",
            },
        )
        assert response.status_code == 403

    def test_supplier_cannot_request_reports(self, client_factory, world):
        supplier = UserFactory(email="rp-supplier@example.test")
        RoleAssignmentFactory(user=supplier, role=UserRole.SUPPLIER, institution=None)
        client = client_factory(supplier)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 403

    def test_platform_admin_cannot_request_clinical_reports(
        self, client_factory, world
    ):
        admin = UserFactory(email="rp-platform@example.test", is_platform_admin=True)
        client = client_factory(admin)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 403


class TestIndividualLogbook:
    def test_trainee_exports_own_logbook(self, client_factory, world):
        client = client_factory(world.trainee)
        response = request_report(
            client,
            base_payload(
                world,
                "individual_logbook",
                target_user=str(world.trainee.pk),
            ),
        )
        assert response.status_code == 201, response.data
        assert response.data["row_count"] == 1
        job = response.data
        assert "download_url" in job

    def test_manager_exports_colleague_logbook(self, client_factory, world):
        client = client_factory(world.manager)
        response = request_report(
            client,
            base_payload(
                world,
                "individual_logbook",
                fmt="pdf",
                target_user=str(world.trainee.pk),
            ),
        )
        assert response.status_code == 201, response.data
        assert response.data["format"] == "pdf"

    def test_supervisor_cannot_export_colleague_logbook(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(
            client,
            base_payload(
                world,
                "individual_logbook",
                target_user=str(world.trainee.pk),
            ),
        )
        assert response.status_code == 403

    def test_target_outside_institution_is_rejected(self, client_factory, world):
        stranger = UserFactory(email="rp-stranger@example.test")
        RoleAssignmentFactory(
            user=stranger,
            role=UserRole.TRAINEE,
            institution=InstitutionFactory(name="Report Stranger Institute"),
        )
        client = client_factory(world.manager)
        response = request_report(
            client,
            base_payload(world, "individual_logbook", target_user=str(stranger.pk)),
        )
        assert response.status_code == 400
        assert "target_user" in response.data["error"]["details"]

    def test_report_never_contains_patient_reference_codes(
        self, client_factory, world
    ):
        reference = PatientReferenceFactory(institution=world.institution)
        world.procedure.patient_reference = reference
        world.procedure.save()
        client = client_factory(world.trainee)
        response = request_report(
            client,
            base_payload(
                world, "individual_logbook", target_user=str(world.trainee.pk)
            ),
        )
        assert response.status_code == 201
        job = response.data
        artifact = read_artifact(ReportJob.objects.get(pk=job["id"]))
        text = artifact.decode("utf-8-sig")
        assert reference.code not in text
        assert world.procedure.reference in text


class TestAggregates:
    def test_date_range_filter(self, client_factory, world):
        world.procedure.procedure_date = date(2020, 1, 1)
        world.procedure.save()
        other = SurgicalProcedureFactory(
            institution=world.institution,
            author=world.trainee,
            procedure_date=date(2026, 10, 1),
        )
        client = client_factory(world.supervisor)
        response = request_report(
            client,
            base_payload(
                world, "activity_by_date", date_from="2026-01-01", date_to="2026-12-31"
            ),
        )
        assert response.status_code == 201
        assert response.data["row_count"] == 1
        job = ReportJob.objects.get(pk=response.data["id"])
        text = read_artifact(job).decode("utf-8-sig")
        assert other.procedure_date.isoformat() in text
        assert world.procedure.procedure_date.isoformat() not in text

    def test_inverted_dates_rejected(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(
            client,
            base_payload(world, "activity_by_date", date_from="2026-12-31", date_to="2026-01-01"),
        )
        assert response.status_code == 400

    def test_foreign_institution_rows_never_appear(self, client_factory, world):
        foreign_institution = InstitutionFactory(name="Report Other Institute")
        foreign_procedure = SurgicalProcedureFactory(
            institution=foreign_institution,
            author=UserFactory(email="rp-other@example.test"),
            procedure_name="Should not appear",
        )
        client = client_factory(world.supervisor)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 201
        text = read_artifact(ReportJob.objects.get(pk=response.data["id"])).decode(
            "utf-8-sig"
        )
        assert "Should not appear" not in text
        assert foreign_procedure.reference not in text

    def test_participation_roles_counts_author_and_participant(
        self, client_factory, world
    ):
        ProcedureParticipantFactory(
            procedure=world.procedure, user=world.supervisor, role="assistant"
        )
        client = client_factory(world.supervisor)
        response = request_report(client, base_payload(world, "participation_roles"))
        assert response.status_code == 201
        text = read_artifact(ReportJob.objects.get(pk=response.data["id"])).decode(
            "utf-8-sig"
        )
        assert "author" in text
        assert "Assistant" in text


class TestFormatsAndSafety:
    def test_csv_formula_injection_is_neutralized(self, client_factory, world):
        world.procedure.procedure_name = "=HYPERLINK(\"http://evil\")"
        world.procedure.save()
        client = client_factory(world.trainee)
        response = request_report(
            client,
            base_payload(
                world, "individual_logbook", target_user=str(world.trainee.pk)
            ),
        )
        assert response.status_code == 201
        text = read_artifact(ReportJob.objects.get(pk=response.data["id"])).decode(
            "utf-8-sig"
        )
        assert "'=HYPERLINK" in text

    def test_pdf_artifact_is_a_real_pdf(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(client, base_payload(world, "activity_by_date", fmt="pdf"))
        assert response.status_code == 201
        artifact = read_artifact(ReportJob.objects.get(pk=response.data["id"]))
        assert artifact.startswith(b"%PDF-")

    def test_row_limit_fails_clearly(self, client_factory, world, settings):
        settings.REPORT_SYNC_ROW_LIMIT = 0
        client = client_factory(world.supervisor)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 400
        job = ReportJob.objects.filter(status=ReportStatus.FAILED).first()
        assert job is not None
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.REPORT_FAILED
        ).exists()


class TestDownloadAndIsolation:
    @pytest.fixture
    def job(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = request_report(client, base_payload(world, "activity_by_date"))
        assert response.status_code == 201
        return response.data

    def test_owner_downloads_artifact(self, client_factory, world, job):
        client = client_factory(world.supervisor)
        response = client.get(job["download_url"])
        assert response.status_code == 200
        assert "attachment" in response["Content-Disposition"]
        assert b"Activity by date" in b"".join(response.streaming_content)

    def test_another_user_gets_404(self, client_factory, world, job):
        client = client_factory(world.trainee)
        response = client.get(job["download_url"])
        assert response.status_code == 404

    def test_expired_link_returns_410(self, client_factory, world, job):
        record = ReportJob.objects.get(pk=job["id"])
        record.expires_at = timezone.now() - timedelta(hours=1)
        record.save(update_fields=["expires_at"])
        client = client_factory(world.supervisor)
        response = client.get(job["download_url"])
        assert response.status_code == 410
        assert response.data["error"]["code"] == "download_expired"

    def test_pending_job_cannot_be_downloaded(self, client_factory, world):
        client = client_factory(world.supervisor)
        pending = ReportJob.objects.create(
            requester=world.supervisor,
            institution=world.institution,
            report_type="activity_by_date",
            format="csv",
            status="pending",
        )
        response = client.get(f"/api/v1/reports/{pending.pk}/download/")
        assert response.status_code == 400

    def test_detail_and_list_are_owner_scoped(self, client_factory, world, job):
        client = client_factory(world.trainee)
        assert client.get(f"/api/v1/reports/{job['id']}/").status_code == 404
        listing = client.get("/api/v1/reports/").data
        assert listing["count"] == 0

    def test_download_is_audited(self, client_factory, world, job):
        client = client_factory(world.supervisor)
        client.get(job["download_url"])
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.REPORT_DOWNLOADED, object_pk=job["id"]
        ).exists()
