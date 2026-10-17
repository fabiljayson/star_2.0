from __future__ import annotations

import uuid as uuid_lib

from django.db import IntegrityError
from django.db.models import QuerySet
from django.http import FileResponse
from rest_framework import exceptions, generics, status, views
from rest_framework.response import Response

from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from . import services, transcription
from .models import (
    Attachment,
    PatientReference,
    ProcedureParticipant,
    ProcedureStatus,
    SurgicalProcedure,
)
from .serializers import (
    AttachmentSerializer,
    NoteVersionSerializer,
    PatientReferenceSerializer,
    ProcedureParticipantSerializer,
    ReviewActionSerializer,
    ReviewDecisionSerializer,
    SurgicalProcedureSerializer,
)
from .uploads import store_upload, validate_and_read_upload


def _parse_uuid(param: str, field: str):
    try:
        return uuid_lib.UUID(str(param))
    except ValueError:
        raise exceptions.ValidationError({field: "Invalid id."}) from None


def _get_visible_procedure(request, pk) -> SurgicalProcedure:
    """Fetch a record inside the caller's visibility scope or return 404.

    Out-of-scope identifiers are indistinguishable from missing ones so that
    probing never discloses another institution's record existence.
    """
    procedure = (
        services.visible_procedures(request.user).filter(pk=pk).select_related(
            "institution", "department", "specialty", "patient_reference", "author"
        )
        .prefetch_related("participants__user")
        .first()
    )
    if procedure is None:
        raise exceptions.NotFound()
    return procedure


# ── Patient references ─────────────────────────────────────────────────
class PatientReferenceListCreateView(generics.ListCreateAPIView):
    serializer_class = PatientReferenceSerializer
    search_fields = ["code", "label"]
    ordering_fields = ["created_at", "code"]
    ordering = ["-created_at"]

    def get_queryset(self) -> QuerySet[PatientReference]:
        return (
            services.visible_patient_references(self.request.user)
            .select_related("institution", "created_by")
        )

    def perform_create(self, serializer):
        services.ensure_can_create(self.request.user, serializer.validated_data["institution"])
        instance = serializer.save(created_by=self.request.user)
        record_audit(
            request=self.request,
            action=AuditEvent.Action.PATIENT_REF_CREATED,
            object_type="patient_reference",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"code": instance.code},
        )


class PatientReferenceDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = PatientReferenceSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[PatientReference]:
        return services.visible_patient_references(self.request.user).select_related(
            "institution", "created_by"
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        if not services.has_institution_role(
            self.request.user, instance.institution_id, services.REVIEWER_ROLES
        ):
            raise exceptions.PermissionDenied(
                "Only institution reviewers can deactivate patient references.",
                code="permission_denied",
            )
        changed = serializer.validated_data
        instance = serializer.save()
        if "is_active" in changed and not instance.is_active:
            record_audit(
                request=self.request,
                action=AuditEvent.Action.PATIENT_REF_DEACTIVATED,
                object_type="patient_reference",
                object_pk=instance.pk,
                institution=instance.institution,
                metadata={"code": instance.code},
            )


# ── Surgical procedures ────────────────────────────────────────────────
class ProcedureListCreateView(generics.ListCreateAPIView):
    serializer_class = SurgicalProcedureSerializer
    search_fields = ["reference", "procedure_name", "indication"]
    ordering_fields = ["procedure_date", "created_at", "status", "reference"]
    ordering = ["-procedure_date", "-created_at"]
    filterset_fields = [
        "institution",
        "department",
        "specialty",
        "status",
        "category",
        "author",
    ]

    def get_queryset(self) -> QuerySet[SurgicalProcedure]:
        qs = (
            services.visible_procedures(self.request.user)
            .select_related("institution", "department", "specialty", "author")
            .prefetch_related("participants__user")
        )
        params = self.request.query_params
        if params.get("date_from"):
            qs = qs.filter(procedure_date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(procedure_date__lte=params["date_to"])
        if params.get("participant_role"):
            qs = qs.filter(
                participants__user=self.request.user,
                participants__role=params["participant_role"],
            )
        if params.get("mine") in {"1", "true", "True"}:
            qs = qs.filter(author=self.request.user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        institution = serializer.validated_data["institution"]
        services.ensure_can_create(user, institution)
        if services.is_marketplace_only(user):
            raise exceptions.PermissionDenied(
                "Marketplace accounts cannot create surgical records.",
                code="permission_denied",
            )
        instance = serializer.save(author=user)
        record_audit(
            request=self.request,
            action=AuditEvent.Action.PROCEDURE_CREATED,
            object_type="surgical_procedure",
            object_pk=instance.pk,
            institution=instance.institution,
            metadata={"reference": instance.reference, "category": instance.category},
        )


class ProcedureDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SurgicalProcedureSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> SurgicalProcedure:
        return _get_visible_procedure(self.request, self.kwargs["pk"])

    def perform_update(self, serializer):
        instance = serializer.instance
        services.apply_content_edit(
            instance,
            actor=self.request.user,
            validated_data=serializer.validated_data,
            request=self.request,
        )


# ── Participants ───────────────────────────────────────────────────────
class ProcedureParticipantsView(views.APIView):
    def get(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        serializer = ProcedureParticipantSerializer(
            procedure.participants.select_related("user"), many=True
        )
        return Response(serializer.data)

    def post(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        if procedure.author_id != request.user.pk:
            raise exceptions.PermissionDenied(
                "Only the record author can manage participants.",
                code="permission_denied",
            )
        if not procedure.is_editable:
            raise exceptions.ValidationError(
                {"status": f"Participants cannot be changed in status '{procedure.status}'."}
            )
        serializer = ProcedureParticipantSerializer(
            data=request.data, context={"procedure": procedure}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if services.is_marketplace_only(user):
            raise exceptions.ValidationError(
                {"user": "Marketplace accounts cannot participate in surgical records."}
            )
        if procedure.participants.filter(user=user).exists():
            raise exceptions.ValidationError(
                {"user": "This user is already a participant."}
            )
        try:
            participant = serializer.save(procedure=procedure)
        except IntegrityError as exc:
            raise exceptions.ValidationError(
                {"user": "This user is already a participant."}
            ) from exc
        record_audit(
            request=request,
            action=AuditEvent.Action.PARTICIPANT_ADDED,
            object_type="procedure_participant",
            object_pk=participant.pk,
            institution=procedure.institution,
            metadata={"reference": procedure.reference, "role": participant.role},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProcedureParticipantDetailView(views.APIView):
    def delete(self, request, pk, participant_id):
        procedure = _get_visible_procedure(request, pk)
        if procedure.author_id != request.user.pk:
            raise exceptions.PermissionDenied(
                "Only the record author can manage participants.",
                code="permission_denied",
            )
        if not procedure.is_editable:
            raise exceptions.ValidationError(
                {"status": f"Participants cannot be changed in status '{procedure.status}'."}
            )
        participant = (
            ProcedureParticipant.objects.filter(
                pk=participant_id, procedure=procedure
            )
            .select_related("user")
            .first()
        )
        if participant is None:
            raise exceptions.NotFound()
        role = participant.role
        participant.delete()
        record_audit(
            request=request,
            action=AuditEvent.Action.PARTICIPANT_REMOVED,
            object_type="procedure_participant",
            object_pk=str(participant_id),
            institution=procedure.institution,
            metadata={"reference": procedure.reference, "role": role},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Lifecycle actions ──────────────────────────────────────────────────
class ProcedureSubmitView(views.APIView):
    def post(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        services.submit_procedure(procedure, actor=request.user, request=request)
        procedure.refresh_from_db()
        return Response(SurgicalProcedureSerializer(procedure).data)


class ProcedureReviewsView(views.APIView):
    def get(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        serializer = ReviewDecisionSerializer(
            procedure.review_decisions.select_related("reviewer"), many=True
        )
        return Response(serializer.data)

    def post(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.review_procedure(
            procedure,
            actor=request.user,
            decision=serializer.validated_data["decision"],
            reason=serializer.validated_data.get("reason", ""),
            request=request,
        )
        procedure.refresh_from_db()
        return Response(
            {
                "procedure": SurgicalProcedureSerializer(procedure).data,
                "review": ReviewDecisionSerializer(
                    procedure.review_decisions.select_related("reviewer").first()
                ).data,
            }
        )


class ProcedureArchiveView(views.APIView):
    def post(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        services.archive_procedure(procedure, actor=request.user, request=request)
        procedure.refresh_from_db()
        return Response(SurgicalProcedureSerializer(procedure).data)


class ProcedureVersionsView(views.APIView):
    def get(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        serializer = NoteVersionSerializer(
            procedure.note_versions.select_related("changed_by"), many=True
        )
        return Response(serializer.data)


# ── Attachments ────────────────────────────────────────────────────────
class ProcedureAttachmentsView(views.APIView):
    def get(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        serializer = AttachmentSerializer(
            procedure.attachments.select_related("uploaded_by"),
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

    def post(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        if procedure.author_id != request.user.pk:
            raise exceptions.PermissionDenied(
                "Only the record author can add attachments.",
                code="permission_denied",
            )
        if procedure.status == ProcedureStatus.ARCHIVED:
            raise exceptions.ValidationError(
                {"status": "Archived records no longer accept attachments."}
            )
        file = request.data.get("file")
        if file is None:
            raise exceptions.ValidationError({"file": "This field is required."})
        meta = validate_and_read_upload(file)
        attachment = Attachment(
            procedure=procedure,
            original_name=meta["original_name"],
            declared_content_type=getattr(file, "content_type", "") or "",
            detected_kind=meta["detected_kind"],
            size_bytes=meta["size_bytes"],
            sha256=meta["sha256"],
            uploaded_by=request.user,
        )
        attachment.file.save(meta["storage_name"], store_upload(meta), save=False)
        attachment.save()
        record_audit(
            request=request,
            action=AuditEvent.Action.ATTACHMENT_ADDED,
            object_type="attachment",
            object_pk=attachment.pk,
            institution=procedure.institution,
            metadata={
                "reference": procedure.reference,
                "size_bytes": attachment.size_bytes,
                "kind": attachment.detected_kind,
            },
        )
        serializer = AttachmentSerializer(
            attachment, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProcedureAttachmentDetailView(views.APIView):
    def delete(self, request, pk, attachment_id):
        procedure = _get_visible_procedure(request, pk)
        if procedure.author_id != request.user.pk:
            raise exceptions.PermissionDenied(
                "Only the record author can remove attachments.",
                code="permission_denied",
            )
        if procedure.status == ProcedureStatus.ARCHIVED:
            raise exceptions.ValidationError(
                {"status": "Attachments of archived records are retained."}
            )
        attachment = (
            Attachment.objects.filter(pk=attachment_id, procedure=procedure).first()
        )
        if attachment is None:
            raise exceptions.NotFound()
        attachment.file.delete(save=False)
        attachment.delete()
        record_audit(
            request=request,
            action=AuditEvent.Action.ATTACHMENT_REMOVED,
            object_type="attachment",
            object_pk=str(attachment_id),
            institution=procedure.institution,
            metadata={"reference": procedure.reference},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AttachmentDownloadView(views.APIView):
    """Permission-checked, short-lived access to a private clinical file.

    The download link itself is a JWT-protected endpoint (access tokens last
    15 minutes by default), so no permanent public URL ever exists.
    """

    def get(self, request, pk, attachment_id):
        procedure = _get_visible_procedure(request, pk)
        attachment = (
            Attachment.objects.filter(pk=attachment_id, procedure=procedure).first()
        )
        if attachment is None:
            raise exceptions.NotFound()
        if not attachment.file.storage.exists(attachment.file.name):
            raise exceptions.NotFound("File content is no longer available.")
        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.download_name,
            content_type=attachment.detected_kind or "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


# ── Voice dictation (transcription adapter) ────────────────────────────
class ProcedureTranscribeView(views.APIView):
    """Send dictation audio to the configured provider and return a draft
    transcript for manual review.

    The transcript is never written to the record automatically: the author
    must edit and save or submit explicitly. Raw audio stays in memory for
    the duration of the call and is not persisted by the mock provider.
    """

    def post(self, request, pk):
        procedure = _get_visible_procedure(request, pk)
        if procedure.author_id != request.user.pk:
            raise exceptions.PermissionDenied(
                "Only the record author can dictate into this record.",
                code="permission_denied",
            )
        if not procedure.is_editable:
            raise exceptions.ValidationError(
                {"status": f"Records in status '{procedure.status}' are locked for dictation."}
            )

        language = str(request.data.get("language") or "en").strip().lower()
        if language not in transcription.supported_languages():
            raise exceptions.ValidationError(
                {
                    "language": (
                        "Unsupported transcription language "
                        f"(available: {', '.join(transcription.supported_languages())})."
                    )
                }
            )

        audio = request.data.get("audio")
        if audio is None:
            raise exceptions.ValidationError({"audio": "This field is required."})
        meta = transcription.validate_and_read_audio(audio)

        provider = transcription.get_provider()
        try:
            result = provider.transcribe(
                meta["data"],
                language=language,
                filename=getattr(audio, "name", "") or "",
            )
        except transcription.TranscriptionUnavailable as exc:
            record_audit(
                request=request,
                action=AuditEvent.Action.TRANSCRIPTION_FAILED,
                object_type="surgical_procedure",
                object_pk=procedure.pk,
                institution=procedure.institution,
                metadata={
                    "reference": procedure.reference,
                    "language": language,
                    "provider": provider.name,
                    "size_bytes": meta["size_bytes"],
                },
            )
            raise exc

        record_audit(
            request=request,
            action=AuditEvent.Action.TRANSCRIPTION_COMPLETED,
            object_type="surgical_procedure",
            object_pk=procedure.pk,
            institution=procedure.institution,
            metadata={
                "reference": procedure.reference,
                "language": language,
                "provider": result.provider,
                "simulated": result.simulated,
                "size_bytes": meta["size_bytes"],
                "sha256": meta["sha256"],
            },
        )
        return Response(
            {
                "text": result.text,
                "language": result.language,
                "provider": result.provider,
                "simulated": result.simulated,
                "confidence": result.confidence,
                "uncertain": result.uncertain,
            }
        )
