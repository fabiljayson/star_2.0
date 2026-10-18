from __future__ import annotations

from django.http import FileResponse
from rest_framework import exceptions, generics, status
from rest_framework.response import Response

from apps.core.audit import record_audit
from apps.core.models import AuditEvent

from . import services
from .models import ReportJob, ReportStatus
from .serializers import ReportJobSerializer, ReportRequestSerializer


class DownloadExpired(exceptions.APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This download link has expired; request the report again."
    default_code = "download_expired"


class ReportListCreateView(generics.ListCreateAPIView):
    serializer_class = ReportJobSerializer
    ordering_fields = ["created_at", "report_type", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return services.visible_report_jobs(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = ReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = services.request_report(
            request.user,
            institution=serializer.validated_data["institution"],
            report_type=serializer.validated_data["report_type"],
            report_format=serializer.validated_data["format"],
            parameters=serializer.validated_data.get("parameters", {}),
            request=request,
        )
        return Response(
            ReportJobSerializer(job).data, status=status.HTTP_201_CREATED
        )


class ReportDetailView(generics.RetrieveAPIView):
    serializer_class = ReportJobSerializer
    queryset = ReportJob.objects.all()

    def get_object(self):
        job = (
            services.visible_report_jobs(self.request.user)
            .filter(pk=self.kwargs["pk"])
            .first()
        )
        if job is None:
            raise exceptions.NotFound()
        return job


class ReportDownloadView(generics.GenericAPIView):
    queryset = ReportJob.objects.all()

    def get_object(self):
        job = (
            services.visible_report_jobs(self.request.user)
            .filter(pk=self.kwargs["pk"])
            .first()
        )
        if job is None:
            raise exceptions.NotFound()
        return job

    def get(self, request, *args, **kwargs):
        job = self.get_object()
        if job.status == ReportStatus.FAILED:
            raise exceptions.ValidationError(
                {"detail": "This report failed to generate; there is nothing to download."}
            )
        if job.status != ReportStatus.SUCCEEDED:
            raise exceptions.ValidationError(
                {"detail": "This report is still being generated."}
            )
        if job.is_expired:
            raise DownloadExpired()
        record_audit(
            request=request,
            actor=request.user,
            action=AuditEvent.Action.REPORT_DOWNLOADED,
            object_type="report_job",
            object_pk=job.pk,
            institution=job.institution,
            metadata={"report_type": job.report_type, "format": job.format},
        )
        response = FileResponse(
            job.artifact.open("rb"),
            content_type="application/pdf"
            if job.format == "pdf"
            else "text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{job.artifact_name}"'
        return response
