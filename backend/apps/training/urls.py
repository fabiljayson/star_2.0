from django.urls import path

from . import views

urlpatterns = [
    path(
        "training/placements/",
        views.PlacementListCreateView.as_view(),
        name="placement-list",
    ),
    path(
        "training/placements/<uuid:pk>/",
        views.PlacementDetailView.as_view(),
        name="placement-detail",
    ),
    path(
        "training/placements/<uuid:pk>/examiners/",
        views.PlacementExaminersView.as_view(),
        name="placement-examiners",
    ),
    path(
        "training/placements/<uuid:pk>/examiners/<uuid:assignment_id>/",
        views.PlacementExaminerDetailView.as_view(),
        name="placement-examiner-detail",
    ),
    path(
        "training/placements/<uuid:pk>/complete/",
        views.PlacementCompleteView.as_view(),
        name="placement-complete",
    ),
    path(
        "training/placements/<uuid:pk>/cancel/",
        views.PlacementCancelView.as_view(),
        name="placement-cancel",
    ),
    path(
        "training/placements/<uuid:pk>/progress/",
        views.PlacementProgressView.as_view(),
        name="placement-progress",
    ),
    path("competencies/", views.CompetencyListCreateView.as_view(), name="competency-list"),
    path(
        "competencies/<uuid:pk>/",
        views.CompetencyDetailView.as_view(),
        name="competency-detail",
    ),
    path(
        "competencies/<uuid:pk>/rubric-versions/",
        views.CompetencyRubricVersionsView.as_view(),
        name="competency-rubric-versions",
    ),
    path(
        "competencies/<uuid:pk>/rubric-versions/<uuid:version_id>/",
        views.CompetencyRubricVersionDetailView.as_view(),
        name="competency-rubric-version-detail",
    ),
    path("assessments/", views.AssessmentListCreateView.as_view(), name="assessment-list"),
    path(
        "assessments/<uuid:pk>/",
        views.AssessmentDetailView.as_view(),
        name="assessment-detail",
    ),
    path(
        "assessments/<uuid:pk>/submit/",
        views.AssessmentSubmitView.as_view(),
        name="assessment-submit",
    ),
    path(
        "assessments/<uuid:pk>/decide/",
        views.AssessmentDecideView.as_view(),
        name="assessment-decide",
    ),
]
