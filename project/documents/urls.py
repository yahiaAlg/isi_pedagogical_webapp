from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    # Document dashboard
    path(
        "sessions/<int:session_pk>/documents/",
        views.document_dashboard,
        name="dashboard",
    ),
    path(
        "sessions/<int:session_pk>/documents/history/",
        views.document_history,
        name="history",
    ),
    # Pre-session document generation
    path(
        "sessions/<int:session_pk>/generate/candidate-list/",
        views.generate_candidate_list_view,
        name="generate_candidate_list",
    ),
    path(
        "sessions/<int:session_pk>/generate/attendance-sheet/",
        views.generate_attendance_sheet_view,
        name="generate_attendance_sheet",
    ),
    path(
        "sessions/<int:session_pk>/generate/mission-order/",
        views.generate_mission_order_view,
        name="generate_mission_order",
    ),
    path(
        "sessions/<int:session_pk>/generate/nominal-list/",
        views.generate_nominal_list_view,
        name="generate_nominal_list",
    ),
    # Post-session document generation
    path(
        "sessions/<int:session_pk>/generate/evaluation-list/",
        views.generate_evaluation_list_view,
        name="generate_evaluation_list",
    ),
    path(
        "sessions/<int:session_pk>/generate/deliberation-report/",
        views.generate_deliberation_report_view,
        name="generate_deliberation_report",
    ),
    path(
        "sessions/<int:session_pk>/committee/",
        views.set_committee_view,
        name="set_committee",
    ),
    # Individual participant documents
    path(
        "participants/<int:participant_pk>/generate/evaluation-sheet/",
        views.generate_evaluation_sheet_view,
        name="generate_evaluation_sheet",
    ),
    path(
        "participants/<int:participant_pk>/generate/attestation/",
        views.generate_attestation_view,
        name="generate_attestation",
    ),
    # Batch operations
    path(
        "sessions/<int:session_pk>/generate/batch-attestations/",
        views.generate_batch_attestations_view,
        name="generate_batch_attestations",
    ),
    # Download
    path("documents/<int:pk>/download/", views.download_document, name="download"),
]
