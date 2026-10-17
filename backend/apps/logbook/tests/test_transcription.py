from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.core.models import AuditEvent
from apps.logbook.tests.factories import SurgicalProcedureFactory
from apps.logbook.tests.helpers import error_details
from apps.organizations.tests.factories import InstitutionFactory

pytestmark = pytest.mark.django_db


def wav_bytes() -> bytes:
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 24


@pytest.fixture
def world():
    institution = InstitutionFactory(name="Voice Institute")
    trainee = UserFactory(email="vo-trainee@example.test")
    RoleAssignmentFactory(user=trainee, role=UserRole.TRAINEE, institution=institution)
    supervisor = UserFactory(email="vo-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    procedure = SurgicalProcedureFactory(
        institution=institution, author=trainee, procedure_name="Dictated case"
    )
    return SimpleNamespace(
        institution=institution,
        trainee=trainee,
        supervisor=supervisor,
        procedure=procedure,
    )


def _post(client, procedure, data):
    audio = data.get("audio")
    if isinstance(audio, bytes):
        data = {
            **data,
            "audio": SimpleUploadedFile(
                "dictation.wav", audio, content_type="audio/wav"
            ),
        }
    return client.post(f"/api/v1/procedures/{procedure.pk}/transcribe/", data, format="multipart")


class TestTranscriptionSuccess:
    def test_author_receives_labelled_simulated_transcript(self, client_factory, world):
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes(), "language": "en"})
        assert response.status_code == 200, response.data
        assert response.data["simulated"] is True
        assert response.data["uncertain"] is True
        assert response.data["confidence"] == 0.0
        assert response.data["provider"] == "mock"
        assert "SIMULATED" in response.data["text"]

    def test_french_language_returns_french_mock(self, client_factory, world):
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes(), "language": "fr"})
        assert response.status_code == 200, response.data
        assert response.data["language"] == "fr"
        assert "TRANSCRIPTION SIMULEE" in response.data["text"]

    def test_success_is_audited_without_transcript_text(self, client_factory, world):
        client = client_factory(world.trainee)
        _post(client, world.procedure, {"audio": wav_bytes(), "language": "en"})
        event = AuditEvent.objects.get(action=AuditEvent.Action.TRANSCRIPTION_COMPLETED)
        flat = " ".join(str(value) for value in event.metadata.values())
        assert "SIMULATED" not in flat
        assert "text" not in event.metadata

    def test_record_content_and_status_untouched(self, client_factory, world):
        client = client_factory(world.trainee)
        before = (world.procedure.summary, world.procedure.status, world.procedure.version)
        _post(client, world.procedure, {"audio": wav_bytes()})
        world.procedure.refresh_from_db()
        assert (world.procedure.summary, world.procedure.status, world.procedure.version) == before

    def test_audio_is_not_persisted(self, client_factory, world, settings, tmp_path):
        settings.PRIVATE_MEDIA_ROOT = tmp_path
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes()})
        assert response.status_code == 200
        assert list(tmp_path.rglob("*")) == []


class TestTranscriptionPermissions:
    def test_non_author_cannot_dictate(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = _post(client, world.procedure, {"audio": wav_bytes()})
        assert response.status_code == 403

    def test_out_of_scope_record_is_404(self, client_factory, world):
        outsider = UserFactory(email="vo-outsider@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.SUPERVISOR,
            institution=InstitutionFactory(name="Voice Foreign Institute"),
        )
        client = client_factory(outsider)
        response = _post(client, world.procedure, {"audio": wav_bytes()})
        assert response.status_code == 404

    @pytest.mark.parametrize("status_value", ["submitted", "under_review", "archived"])
    def test_locked_records_reject_dictation(self, client_factory, world, status_value):
        world.procedure.status = status_value
        world.procedure.save()
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes()})
        assert response.status_code == 400
        assert "status" in error_details(response)


class TestTranscriptionValidation:
    def test_missing_audio(self, client_factory, world):
        client = client_factory(world.trainee)
        response = client.post(f"/api/v1/procedures/{world.procedure.pk}/transcribe/")
        assert response.status_code == 400
        assert "audio" in error_details(response)

    def test_unsupported_language(self, client_factory, world):
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes(), "language": "de"})
        assert response.status_code == 400
        assert "language" in error_details(response)

    def test_content_must_match_extension(self, client_factory, world):
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": b"just some plain text"})
        assert response.status_code == 400
        assert "audio" in error_details(response)

    def test_extension_enforced(self, client_factory, world):
        client = client_factory(world.trainee)
        upload = SimpleUploadedFile("clip.mp4", wav_bytes(), content_type="video/mp4")
        response = _post(client, world.procedure, {"audio": upload})
        assert response.status_code == 400
        assert "audio" in error_details(response)

    def test_oversized_audio_rejected(self, client_factory, world, settings):
        settings.AUDIO_MAX_SIZE_MB = 0
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes()})
        assert response.status_code == 400
        assert "audio" in error_details(response)


class TestTranscriptionFailureScenarioH:
    @override_settings(TRANSCRIPTION_MOCK_FAILURE=True)
    def test_provider_failure_reports_error_and_keeps_draft(
        self, client_factory, world
    ):
        world.procedure.summary = "Draft text that must survive a failure."
        world.procedure.save()
        client = client_factory(world.trainee)
        response = _post(client, world.procedure, {"audio": wav_bytes()})
        assert response.status_code == 503
        assert response.data["error"]["code"] == "transcription_unavailable"
        world.procedure.refresh_from_db()
        assert world.procedure.summary == "Draft text that must survive a failure."
        assert world.procedure.status == "draft"
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.TRANSCRIPTION_FAILED
        ).exists()
