from django.urls import path

from . import views

urlpatterns = [
    path(
        "patients/references/",
        views.PatientReferenceListCreateView.as_view(),
        name="patient-reference-list",
    ),
    path(
        "patients/references/<uuid:pk>/",
        views.PatientReferenceDetailView.as_view(),
        name="patient-reference-detail",
    ),
    path("procedures/", views.ProcedureListCreateView.as_view(), name="procedure-list"),
    path(
        "procedures/<uuid:pk>/",
        views.ProcedureDetailView.as_view(),
        name="procedure-detail",
    ),
    path(
        "procedures/<uuid:pk>/participants/",
        views.ProcedureParticipantsView.as_view(),
        name="procedure-participants",
    ),
    path(
        "procedures/<uuid:pk>/participants/<uuid:participant_id>/",
        views.ProcedureParticipantDetailView.as_view(),
        name="procedure-participant-detail",
    ),
    path(
        "procedures/<uuid:pk>/submit/",
        views.ProcedureSubmitView.as_view(),
        name="procedure-submit",
    ),
    path(
        "procedures/<uuid:pk>/reviews/",
        views.ProcedureReviewsView.as_view(),
        name="procedure-reviews",
    ),
    path(
        "procedures/<uuid:pk>/archive/",
        views.ProcedureArchiveView.as_view(),
        name="procedure-archive",
    ),
    path(
        "procedures/<uuid:pk>/versions/",
        views.ProcedureVersionsView.as_view(),
        name="procedure-versions",
    ),
    path(
        "procedures/<uuid:pk>/attachments/",
        views.ProcedureAttachmentsView.as_view(),
        name="procedure-attachments",
    ),
    path(
        "procedures/<uuid:pk>/attachments/<uuid:attachment_id>/",
        views.ProcedureAttachmentDetailView.as_view(),
        name="procedure-attachment-detail",
    ),
    path(
        "procedures/<uuid:pk>/attachments/<uuid:attachment_id>/download/",
        views.AttachmentDownloadView.as_view(),
        name="procedure-attachment-download",
    ),
]
