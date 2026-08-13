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
    # Spec — this list can be printed either auto-filled with the
    # registered candidates' data, or fully blank for on-site manual
    # completion by the trainer/candidates (?mode=blank).
    blank_mode = request.GET.get("mode") == "blank"
    if blank_mode:
        participants = []
        blank_rows = max(session.capacity or 0, 12)
    else:
        participants = session.participant_set.order_by("last_name", "first_name")
        blank_rows = 12
    return render(
        request,
        "documents/print/candidate_list.html",
        {
            "session": session,
            "participants": participants,
            "institute": _get_institute(),
            "blank_mode": blank_mode,
            "blank_rows": blank_rows,
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

    # Spec — same blank/auto-filled toggle as the candidate list, so the
    # presence sheet can be handed out empty and filled in by hand.
    blank_mode = request.GET.get("mode") == "blank"
    if blank_mode:
        participants = []
        blank_rows = max(session.capacity or 0, 12)
    else:
        participants = session.participant_set.order_by("last_name", "first_name")
        blank_rows = 12
    return render(
        request,
        "documents/print/attendance_sheet.html",
        {
            "session": session,
            "participants": participants,
            "day_number": day_number,
            "day_date": day_date,
            "institute": _get_institute(),
            "blank_mode": blank_mode,
            "blank_rows": blank_rows,
        },
    )


@login_required
def print_nominal_list(request, session_pk):
    """Spec v2.2 — post-session document carrying each participant's exam
    result; generated immediately before the deliberation report."""
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    # Nominal list and PV share the same reference (§ PV sequencer) —
    # whichever of the two is printed first allocates it.
    session.assign_pv_number()
    participants = session.participant_set.order_by("last_name", "first_name")
    return render(
        request,
        "documents/print/nominal_list.html",
        {
            "session": session,
            "participants": participants,
            "institute": _get_institute(),
        },
    )


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
    # Same PV sequencer/number as the nominal list (§ PV sequencer) —
    # no-op if the nominal list already allocated one for this session.
    session.assign_pv_number()
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

    from .certificate_layout import CANVAS_SIZE, boxes_css, column_offsets
    from .certificate_render import build_certificate_data

    context = {
        "participant": participant,
        "session": participant.session,
        "institute": _get_institute(),
        "data": build_certificate_data(participant),
        "boxes": boxes_css(),
        "canvas_w": CANVAS_SIZE[0],
        "canvas_h": CANVAS_SIZE[1],
    }
    context.update(column_offsets())

    return render(request, "documents/print/attestation.html", context)


@login_required
def print_evaluation_sheet(request, participant_pk):
    """
    « Fiche d'évaluation à chaud » — per candidate, same document in two
    modes:
    - ?mode=blank — nothing filled in, meant to be printed and handed to
      the candidate right after the session for them to tick by hand.
    - default — renders whatever has been transcribed via
      documents:evaluation_sheet_form (ticks/checkmarks placed
      programmatically instead of by hand).
    """
    participant = get_object_or_404(Participant, pk=participant_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    blank_mode = request.GET.get("mode") == "blank"
    evaluation = None if blank_mode else getattr(participant, "hot_evaluation", None)

    from .models import HotEvaluation

    criteria = (
        evaluation.graded_criteria()
        if evaluation
        else [
            {
                "number": i,
                "key": key,
                "label_fr": label_fr,
                "label_ar": label_ar,
                "grade": "",
                "points": None,
            }
            for i, (key, label_fr, label_ar) in enumerate(HotEvaluation.CRITERIA, start=1)
        ]
    )

    return render(
        request,
        "documents/print/evaluation_sheet.html",
        {
            "participant": participant,
            "session": participant.session,
            "institute": _get_institute(),
            "evaluation": evaluation,
            "criteria": criteria,
            "satisfaction_choices": HotEvaluation.SATISFACTION_CHOICES,
            "blank_mode": blank_mode,
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

    from .certificate_layout import CANVAS_SIZE, boxes_css, column_offsets
    from .certificate_render import build_certificate_data

    certificates = [
        {"participant": p, "data": build_certificate_data(p)} for p in passed
    ]

    context = {
        "participants": passed,
        "certificates": certificates,
        "session": session,
        "institute": _get_institute(),
        "boxes": boxes_css(),
        "canvas_w": CANVAS_SIZE[0],
        "canvas_h": CANVAS_SIZE[1],
    }
    context.update(column_offsets())

    return render(request, "documents/print/batch_attestations.html", context)
