"""
documents/views_print.py

Print-ready HTML views for all document types.
Each view renders a standalone print template — no docx generation.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now

from formations.models import Session, Participant
from core.models import InstituteInfo


def _get_institute():
    return InstituteInfo.get_instance()


@login_required
def print_candidate_list(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    participants = session.participant_set.order_by("last_name", "first_name")
    return render(
        request,
        "documents/print/candidate_list.html",
        {
            "session": session,
            "participants": participants,
            "institute": _get_institute(),
        },
    )


@login_required
def print_attendance_sheet(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    try:
        day_number = int(request.GET.get("day", 1))
    except (ValueError, TypeError):
        day_number = 1
    day_number = max(1, min(day_number, session.duration_days))

    from datetime import timedelta

    day_date = session.date_start + timedelta(days=day_number - 1)

    participants = session.participant_set.order_by("last_name", "first_name")
    return render(
        request,
        "documents/print/attendance_sheet.html",
        {
            "session": session,
            "participants": participants,
            "day_number": day_number,
            "day_date": day_date,
            "institute": _get_institute(),
        },
    )


@login_required
def print_nominal_list(request, session_pk):
    """Nominal list reuses the candidate_list template (same structure)."""
    return print_candidate_list(request, session_pk)


@login_required
def print_evaluation_list(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    participants = session.participant_set.order_by("last_name", "first_name")
    return render(
        request,
        "documents/print/evaluation_list.html",
        {
            "session": session,
            "participants": participants,
            "institute": _get_institute(),
        },
    )


@login_required
def print_mission_order(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    return render(
        request,
        "documents/print/mission_order.html",
        {
            "session": session,
            "institute": _get_institute(),
        },
    )


@login_required
def print_deliberation_report(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    return render(
        request,
        "documents/print/deliberation_report.html",
        {
            "session": session,
            "institute": _get_institute(),
        },
    )


@login_required
def print_attestation(request, participant_pk):
    participant = get_object_or_404(Participant, pk=participant_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    # Auto-assign certificate number if not yet set
    if not participant.certificate_number and participant.can_receive_certificate():
        from formations.utils import assign_certificate_number

        assign_certificate_number(participant)
        participant.refresh_from_db()
        participant.certificate_issued = True
        participant.save(update_fields=["certificate_issued"])

    return render(
        request,
        "documents/print/attestation.html",
        {
            "participant": participant,
            "session": participant.session,
            "institute": _get_institute(),
        },
    )


@login_required
def print_batch_attestations(request, session_pk):
    """
    Renders all passed participants' attestations on consecutive pages
    using CSS page-break-after so a single CTRL+P prints them all.
    """
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    passed = [
        p
        for p in session.participant_set.order_by("last_name", "first_name")
        if p.result == "passed" and session.formation.produces_certificate
    ]

    # Assign certificate numbers in bulk
    for p in passed:
        if not p.certificate_number:
            from formations.utils import assign_certificate_number

            assign_certificate_number(p)
            p.refresh_from_db()
        if not p.certificate_issued:
            p.certificate_issued = True
            p.save(update_fields=["certificate_issued"])

    return render(
        request,
        "documents/print/batch_attestations.html",
        {
            "participants": passed,
            "session": session,
            "institute": _get_institute(),
        },
    )
