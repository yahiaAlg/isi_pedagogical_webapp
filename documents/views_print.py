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
    mode = request.GET.get("mode", "filled").lower()
    if mode not in {"filled", "empty"}:
        mode = "filled"
    participants = session.participant_set.order_by("last_name", "first_name") if mode == "filled" else []
    return render(
        request,
        "documents/print/candidate_list.html",
        {
            "session": session,
            "participants": participants,
            "print_mode": mode,
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

    mode = request.GET.get("mode", "filled").lower()
    if mode not in {"filled", "empty"}:
        mode = "filled"
    participants = session.participant_set.order_by("last_name", "first_name") if mode == "filled" else []
    return render(
        request,
        "documents/print/attendance_sheet.html",
        {
            "session": session,
            "participants": participants,
            "print_mode": mode,
            "day_number": day_number,
            "day_date": day_date,
            "institute": _get_institute(),
        },
    )


@login_required
def print_nominal_list(request, session_pk):
    """Spec v2.2 — post-session document carrying each participant's exam
    result; generated immediately before the deliberation report."""
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    participants = session.participant_set.order_by("last_name", "first_name")

    # Arabic labels used by the official supervisory nominal-list layout.
    duration_days = session.formation.duration_days
    if duration_days == 1:
        duration_label_ar = "يوم واحد"
    elif duration_days == 2:
        duration_label_ar = "يومين"
    else:
        duration_label_ar = f"{duration_days} أيام"

    trainer_name_ar = getattr(session.trainer, "full_name_ar", "") or session.trainer.full_name

    return render(
        request,
        "documents/print/nominal_list.html",
        {
            "session": session,
            "participants": participants,
            "institute": _get_institute(),
            "duration_label_ar": duration_label_ar,
            "trainer_name_ar": trainer_name_ar,
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

    participants = list(session.participant_set.order_by("last_name", "first_name"))
    committee_members = []
    for raw in (session.committee_members or []):
        if isinstance(raw, dict):
            name = str(raw.get("name", "")).strip()
            role = str(raw.get("role", "")).strip()
            member_type = raw.get("type", "default")
        else:
            name = str(raw).strip()
            role = ""
            member_type = "default"
        if name:
            committee_members.append({"name": name, "role": role, "type": member_type})

    passed_count = sum(1 for p in participants if p.result == "passed")
    present_count = sum(1 for p in participants if p.attended)
    absent_count = len(participants) - present_count

    return render(
        request,
        "documents/print/deliberation_report.html",
        {
            "session": session,
            "participants": participants,
            "committee_members": committee_members,
            "passed_count": passed_count,
            "present_count": present_count,
            "absent_count": absent_count,
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
