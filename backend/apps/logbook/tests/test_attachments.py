import pytest
from django.test import override_settings

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import RoleAssignmentFactory, UserFactory
from apps.logbook.models import Attachment
from apps.logbook.tests.factories import (
    ProcedureParticipantFactory,
    SurgicalProcedureFactory,
)
from apps.organizations.tests.factories import InstitutionFactory

from .helpers import error_details

pytestmark = pytest.mark.django_db

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR" + b"\x00" * 17
    + b"STAR-DEMO-SYNTHETIC-IMAGE"
)
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture
def world(tmp_path):
    institution = InstitutionFactory(name="Attachment General Hospital")
    author = UserFactory(email="att-author@example.test")
    RoleAssignmentFactory(
        user=author, role=UserRole.TRAINEE, institution=institution
    )
    supervisor = UserFactory(email="att-supervisor@example.test")
    RoleAssignmentFactory(
        user=supervisor, role=UserRole.SUPERVISOR, institution=institution
    )
    procedure = SurgicalProcedureFactory(institution=institution, author=author)
    with override_settings(PRIVATE_MEDIA_ROOT=tmp_path):
        yield SimpleWorld(institution, author, supervisor, procedure, tmp_path)


class SimpleWorld:
    def __init__(self, institution, author, supervisor, procedure, tmp_path):
        self.institution = institution
        self.author = author
        self.supervisor = supervisor
        self.procedure = procedure
        self.tmp_path = tmp_path


def _upload(client, procedure, name, data, content_type="application/octet-stream"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    file = SimpleUploadedFile(name, data, content_type=content_type)
    return client.post(
        f"/api/v1/procedures/{procedure.pk}/attachments/",
        {"file": file},
        format="multipart",
    )


class TestUploadValidation:
    def test_author_can_upload_verified_pdf(self, client_factory, world):
        client = client_factory(world.author)
        response = _upload(client, world.procedure, "op-note.pdf", PDF_BYTES, "application/pdf")
        assert response.status_code == 201, response.data
        assert response.data["detected_kind"] == "application/pdf"
        assert response.data["size_bytes"] == len(PDF_BYTES)
        assert response.data["original_name"] == "op-note.pdf"
        attachment = Attachment.objects.get(pk=response.data["id"])
        assert attachment.sha256
        # Stored under an opaque name in the private root, not web-served.
        assert attachment.file.storage.exists(attachment.file.name)
        with pytest.raises(ValueError):
            attachment.file.storage.url(attachment.file.name)

    def test_extension_not_in_allowlist_rejected(self, client_factory, world):
        client = client_factory(world.author)
        response = _upload(client, world.procedure, "payload.exe", b"MZ\x90\x00")
        assert response.status_code == 400
        assert "file" in error_details(response)
        assert not Attachment.objects.exists()

    def test_content_extension_mismatch_rejected(self, client_factory, world):
        client = client_factory(world.author)
        response = _upload(client, world.procedure, "photo.png", PDF_BYTES, "application/pdf")
        assert response.status_code == 400
        assert "content" in str(response.data).lower()
        assert not Attachment.objects.exists()

    def test_forged_content_rejected(self, client_factory, world):
        client = client_factory(world.author)
        response = _upload(
            client, world.procedure, "malware.png", b"GARBAGE-NOT-AN-IMAGE" * 4
        )
        assert response.status_code == 400
        assert not Attachment.objects.exists()

    def test_oversized_file_rejected(self, client_factory, world):
        client = client_factory(world.author)
        big = b"%PDF-" + b"A" * (2 * 1024 * 1024)
        with override_settings(ATTACHMENT_MAX_SIZE_MB=1):
            response = _upload(client, world.procedure, "huge.pdf", big)
        assert response.status_code == 400
        assert "limit" in str(response.data).lower()
        assert not Attachment.objects.exists()

    def test_disallowed_extension_rejected_by_policy(self, client_factory, world):
        client = client_factory(world.author)
        with override_settings(ATTACHMENT_ALLOWED_EXTENSIONS=[".pdf"]):
            response = _upload(client, world.procedure, "pic.png", PNG_BYTES, "image/png")
        assert response.status_code == 400

    def test_missing_file_field_rejected(self, client_factory, world):
        client = client_factory(world.author)
        response = client.post(
            f"/api/v1/procedures/{world.procedure.pk}/attachments/", {}, format="json"
        )
        assert response.status_code == 400
        assert "file" in error_details(response)


class TestUploadAuthorization:
    def test_non_author_cannot_upload(self, client_factory, world):
        client = client_factory(world.supervisor)
        response = _upload(client, world.procedure, "note.pdf", PDF_BYTES)
        assert response.status_code == 403
        assert not Attachment.objects.exists()

    def test_out_of_scope_user_gets_404(self, client_factory, world):
        outsider = UserFactory(email="att-outsider@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.TRAINEE,
            institution=InstitutionFactory(name="Elsewhere Hospital"),
        )
        client = client_factory(outsider)
        response = _upload(client, world.procedure, "note.pdf", PDF_BYTES)
        assert response.status_code == 404

    def test_anonymous_cannot_list_or_upload(self, api, world):
        listing = api.get(f"/api/v1/procedures/{world.procedure.pk}/attachments/")
        assert listing.status_code in (401, 403)
        response = api.post(
            f"/api/v1/procedures/{world.procedure.pk}/attachments/", {}, format="json"
        )
        assert response.status_code in (401, 403)


class TestDownload:
    @pytest.fixture
    def stored(self, client_factory, world):
        client = client_factory(world.author)
        response = _upload(client, world.procedure, "op-note.pdf", PDF_BYTES)
        assert response.status_code == 201
        return response.data["id"]

    def test_author_can_download_content(self, client_factory, world, stored):
        client = client_factory(world.author)
        url = f"/api/v1/procedures/{world.procedure.pk}/attachments/{stored}/download/"
        response = client.get(url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == PDF_BYTES
        assert response["X-Content-Type-Options"] == "nosniff"
        assert "no-store" in response["Cache-Control"]

    def test_institution_supervisor_can_download(self, client_factory, world, stored):
        client = client_factory(world.supervisor)
        url = f"/api/v1/procedures/{world.procedure.pk}/attachments/{stored}/download/"
        assert client.get(url).status_code == 200

    def test_out_of_scope_download_is_404(self, client_factory, world, stored):
        outsider = UserFactory(email="att-out2@example.test")
        RoleAssignmentFactory(
            user=outsider,
            role=UserRole.TRAINEE,
            institution=InstitutionFactory(name="Remote Hospital"),
        )
        client = client_factory(outsider)
        url = f"/api/v1/procedures/{world.procedure.pk}/attachments/{stored}/download/"
        response = client.get(url)
        assert response.status_code == 404
        assert PDF_BYTES not in getattr(response, "content", b"")

    def test_anonymous_download_is_rejected(self, api, world, stored):
        url = f"/api/v1/procedures/{world.procedure.pk}/attachments/{stored}/download/"
        assert api.get(url).status_code in (401, 403)


class TestAttachmentLifecycle:
    def test_author_can_delete_before_archive(self, client_factory, world):
        client = client_factory(world.author)
        uploaded = _upload(client, world.procedure, "op-note.pdf", PDF_BYTES)
        attachment = Attachment.objects.get(pk=uploaded.data["id"])
        stored_name = attachment.file.name

        url = (
            f"/api/v1/procedures/{world.procedure.pk}/attachments/{attachment.pk}/"
        )
        response = client.delete(url)
        assert response.status_code == 204
        assert not Attachment.objects.filter(pk=attachment.pk).exists()
        assert not attachment.file.storage.exists(stored_name)

    def test_non_author_cannot_delete(self, client_factory, world):
        author_client = client_factory(world.author)
        uploaded = _upload(author_client, world.procedure, "op-note.pdf", PDF_BYTES)
        supervisor_client = client_factory(world.supervisor)
        url = (
            f"/api/v1/procedures/{world.procedure.pk}/attachments/{uploaded.data['id']}/"
        )
        assert supervisor_client.delete(url).status_code == 403
        assert Attachment.objects.filter(pk=uploaded.data["id"]).exists()

    def test_archived_record_rejects_upload_and_delete(self, client_factory, world):
        author_client = client_factory(world.author)
        uploaded = _upload(author_client, world.procedure, "kept.pdf", PDF_BYTES)
        assert uploaded.status_code == 201

        base = f"/api/v1/procedures/{world.procedure.pk}/"
        author_client.post(f"{base}submit/")
        reviewer = client_factory(world.supervisor)
        reviewer.post(f"{base}reviews/", {"decision": "approve"})
        archive = reviewer.post(f"{base}archive/")
        assert archive.status_code == 200

        late_upload = _upload(author_client, world.procedure, "late.pdf", PDF_BYTES)
        assert late_upload.status_code == 400

        delete = author_client.delete(
            f"{base}attachments/{uploaded.data['id']}/"
        )
        assert delete.status_code == 400
        assert Attachment.objects.filter(pk=uploaded.data["id"]).exists()

    def test_participant_does_not_gain_upload_rights(self, client_factory, world):
        colleague = UserFactory(email="att-colleague@example.test")
        RoleAssignmentFactory(
            user=colleague, role=UserRole.TRAINEE, institution=world.institution
        )
        ProcedureParticipantFactory(
            procedure=world.procedure, user=colleague, role="assistant"
        )
        client = client_factory(colleague)
        response = _upload(client, world.procedure, "note.pdf", PDF_BYTES)
        assert response.status_code == 403
