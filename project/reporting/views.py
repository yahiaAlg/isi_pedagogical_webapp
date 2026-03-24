from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone

from formations.models import Formation, Session, Participant
from resources.models import Trainer
from .forms import DateRangeForm, SessionFilterForm


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------


def _require_reporting(request):
    """Spec §9.2 — analytics/reports: Admin + Staff only."""
    if not request.user.profile.is_staff_or_admin():
        raise PermissionDenied()


# ---------------------------------------------------------------------------
# Shared queryset helper
# ---------------------------------------------------------------------------


def _apply_date_filter(qs, form, date_field="date_start"):
    """Apply date_from / date_to from a validated DateRangeForm."""
    if not (form and form.is_valid()):
        return qs
    date_from = form.cleaned_data.get("date_from")
    date_to = form.cleaned_data.get("date_to")
    if date_from:
        qs = qs.filter(**{f"{date_field}__gte": date_from})
    if date_to:
        qs = qs.filter(**{f"{date_field}__lte": date_to})
    return qs


# ---------------------------------------------------------------------------
# §14.1  Reporting dashboard — KPI summary
# ---------------------------------------------------------------------------


@login_required
def reporting_dashboard(request):
    """
    High-level KPI summary page for the reporting module.
    The six KPIs from spec §14.1 are also shown on core/dashboard;
    this view adds context for the reporting section's landing page.
    """
    _require_reporting(request)

    now = timezone.now()
    year = now.year
    month = now.month

    # --- KPI 1: sessions this month
    sessions_this_month = Session.objects.filter(
        date_start__year=year, date_start__month=month
    ).count()

    # --- KPI 2: participants this month
    participants_this_month = Participant.objects.filter(
        session__date_start__year=year,
        session__date_start__month=month,
    ).count()

    # --- KPI 3: attestations YTD
    attestations_ytd = Participant.objects.filter(
        certificate_issued=True,
        session__date_start__year=year,
    ).count()

    # --- KPI 4: active sessions
    active_sessions = Session.objects.filter(
        status__in=["planned", "in_progress"]
    ).count()

    # --- KPI 5: average fill rate (non-cancelled, non-zero capacity)
    non_cancelled = list(
        Session.objects.exclude(status="cancelled").exclude(capacity=0)
    )
    avg_fill_rate = 0
    if non_cancelled:
        avg_fill_rate = round(
            sum(s.fill_rate for s in non_cancelled) / len(non_cancelled), 1
        )

    # --- KPI 6: overall pass rate (result is a @property, must compute in Python)
    all_participants = list(
        Participant.objects.select_related("session__formation").all()
    )
    total_participants = len(all_participants)
    overall_pass_rate = 0
    if total_participants:
        passed = sum(1 for p in all_participants if p.result == "passed")
        overall_pass_rate = round(passed / total_participants * 100, 1)

    # --- Quick links: counts per report section
    context = {
        "sessions_this_month": sessions_this_month,
        "participants_this_month": participants_this_month,
        "attestations_ytd": attestations_ytd,
        "active_sessions": active_sessions,
        "avg_fill_rate": avg_fill_rate,
        "overall_pass_rate": overall_pass_rate,
        # totals for report cards
        "total_sessions": Session.objects.count(),
        "total_formations": Formation.objects.filter(is_active=True).count(),
        "total_trainers": Trainer.objects.filter(is_active=True).count(),
        "total_certs_ever": Participant.objects.filter(certificate_issued=True).count(),
    }
    return render(request, "reporting/dashboard.html", context)


# ---------------------------------------------------------------------------
# §14.2  Fill-rate report
# ---------------------------------------------------------------------------


@login_required
def fill_rate_report(request):
    """
    Per-session table: name, dates, participants, capacity,
    available spots, fill-rate bar, status badge.
    Color thresholds: ≥90% green, 60–89% amber, <60% muted.
    """
    _require_reporting(request)

    form = SessionFilterForm(request.GET or None)
    sessions_qs = (
        Session.objects.select_related("formation", "client", "trainer")
        .exclude(status="cancelled")
        .order_by("-date_start")
    )

    # Apply filters
    sessions_qs = _apply_date_filter(sessions_qs, form)
    if form and form.is_valid():
        if form.cleaned_data.get("formation"):
            sessions_qs = sessions_qs.filter(formation=form.cleaned_data["formation"])
        if form.cleaned_data.get("trainer"):
            sessions_qs = sessions_qs.filter(trainer=form.cleaned_data["trainer"])
        if form.cleaned_data.get("status"):
            sessions_qs = sessions_qs.filter(status=form.cleaned_data["status"])

    # Build rows with computed fill_rate (property, not stored field)
    rows = []
    for s in sessions_qs:
        rate = s.fill_rate
        if rate >= 90:
            color_class = "success"
        elif rate >= 60:
            color_class = "warning"
        else:
            color_class = "secondary"
        rows.append(
            {
                "session": s,
                "participant_count": s.participant_count,
                "available_spots": s.available_spots,
                "fill_rate": rate,
                "color_class": color_class,
            }
        )

    # Summary stats
    avg = round(sum(r["fill_rate"] for r in rows) / len(rows), 1) if rows else 0

    return render(
        request,
        "reporting/fill_rate.html",
        {
            "form": form,
            "rows": rows,
            "avg_fill_rate": avg,
        },
    )


# ---------------------------------------------------------------------------
# §14.3  Operational reports
# ---------------------------------------------------------------------------


@login_required
def sessions_by_formation(request):
    """Formation title | session count | avg fill rate."""
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)
    sessions_qs = Session.objects.exclude(status="cancelled")
    sessions_qs = _apply_date_filter(sessions_qs, form)

    # Group by formation
    formation_ids = sessions_qs.values_list("formation_id", flat=True)
    formations = (
        Formation.objects.filter(pk__in=formation_ids)
        .annotate(
            num_sessions=Count(
                "session",
                filter=~Q(session__status="cancelled"),
            )
        )
        .order_by("-num_sessions")
    )

    # Attach avg fill rate per formation (computed property, must iterate)
    rows = []
    for f in formations:
        f_sessions = [s for s in sessions_qs if s.formation_id == f.pk]
        avg_fill = 0
        if f_sessions:
            avg_fill = round(sum(s.fill_rate for s in f_sessions) / len(f_sessions), 1)
        rows.append(
            {
                "formation": f,
                "session_count": f.num_sessions,
                "avg_fill_rate": avg_fill,
            }
        )

    return render(request, "reporting/by_formation.html", {"form": form, "rows": rows})


@login_required
def sessions_by_client(request):
    """Client name | session count | total participants."""
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)
    sessions_qs = Session.objects.exclude(status="cancelled")
    sessions_qs = _apply_date_filter(sessions_qs, form)

    from clients.models import Client

    client_ids = sessions_qs.values_list("client_id", flat=True)
    clients = (
        Client.objects.filter(pk__in=client_ids)
        .annotate(
            num_sessions=Count(
                "session",
                filter=~Q(session__status="cancelled"),
            )
        )
        .order_by("-num_sessions")
    )

    # Total participants per client
    rows = []
    for c in clients:
        total_p = Participant.objects.filter(
            session__client=c,
            session__in=sessions_qs,
        ).count()
        rows.append(
            {
                "client": c,
                "session_count": c.num_sessions,
                "total_participants": total_p,
            }
        )

    return render(request, "reporting/by_client.html", {"form": form, "rows": rows})


@login_required
def sessions_by_trainer(request):
    """Trainer name | session count | avg pass rate."""
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)
    sessions_qs = Session.objects.exclude(status="cancelled")
    sessions_qs = _apply_date_filter(sessions_qs, form)

    trainer_ids = sessions_qs.values_list("trainer_id", flat=True)
    trainers = (
        Trainer.objects.filter(pk__in=trainer_ids)
        .annotate(
            num_sessions=Count(
                "session",
                filter=~Q(session__status="cancelled"),
            )
        )
        .order_by("-num_sessions")
    )

    rows = []
    for t in trainers:
        t_participants = Participant.objects.filter(
            session__trainer=t,
            session__in=sessions_qs,
        )
        t_list = list(t_participants.select_related("session__formation"))
        total = len(t_list)
        passed = sum(1 for p in t_list if p.result == "passed")
        avg_pass_rate = round(passed / total * 100, 1) if total else 0
        rows.append(
            {
                "trainer": t,
                "session_count": t.num_sessions,
                "avg_pass_rate": avg_pass_rate,
            }
        )

    return render(request, "reporting/by_trainer.html", {"form": form, "rows": rows})


@login_required
def pass_rate_by_formation(request):
    """Formation title | total participants | passed | % passed."""
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)
    sessions_qs = Session.objects.filter(status__in=["completed", "archived"])
    sessions_qs = _apply_date_filter(sessions_qs, form)

    formation_ids = sessions_qs.values_list("formation_id", flat=True).distinct()
    formations = Formation.objects.filter(pk__in=formation_ids).order_by("title")

    rows = []
    for f in formations:
        participants = Participant.objects.filter(
            session__formation=f,
            session__in=sessions_qs,
        )
        p_list = list(participants.select_related("session__formation"))
        total = len(p_list)
        passed = sum(1 for p in p_list if p.result == "passed")
        failed = sum(1 for p in p_list if p.result == "failed")
        absent = sum(1 for p in p_list if p.result == "absent")
        pass_rate = round(passed / total * 100, 1) if total else 0
        rows.append(
            {
                "formation": f,
                "total": total,
                "passed": passed,
                "failed": failed,
                "absent": absent,
                "pass_rate": pass_rate,
            }
        )

    return render(request, "reporting/pass_rate.html", {"form": form, "rows": rows})


@login_required
def certificate_volume(request):
    """
    Certificate count grouped by month/year (spec §14.3).
    Filter: date range.
    """
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)

    certs_qs = Participant.objects.filter(certificate_issued=True)

    # Apply date filter on the session's date_start
    if form and form.is_valid():
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        if date_from:
            certs_qs = certs_qs.filter(session__date_start__gte=date_from)
        if date_to:
            certs_qs = certs_qs.filter(session__date_start__lte=date_to)

    # Group by month
    by_month = (
        certs_qs.annotate(month=TruncMonth("session__date_start"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )

    # Group by year for the summary row
    by_year = (
        certs_qs.annotate(year=TruncYear("session__date_start"))
        .values("year")
        .annotate(count=Count("pk"))
        .order_by("year")
    )

    total = certs_qs.count()

    return render(
        request,
        "reporting/certificate_volume.html",
        {
            "form": form,
            "by_month": list(by_month),
            "by_year": list(by_year),
            "total": total,
        },
    )


@login_required
def trainer_activity(request):
    """
    Trainer activity for the past 6 months (spec §14.3).
    Shows sessions delivered per trainer, click-through to session detail.
    """
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)

    # Default window: past 6 months (overridden by form if submitted)
    now = timezone.now().date()
    from dateutil.relativedelta import relativedelta

    default_from = now - relativedelta(months=6)

    sessions_qs = Session.objects.exclude(status="cancelled")

    if form and form.is_valid():
        date_from = form.cleaned_data.get("date_from") or default_from
        date_to = form.cleaned_data.get("date_to") or now
    else:
        date_from = default_from
        date_to = now

    sessions_qs = sessions_qs.filter(
        date_start__gte=date_from,
        date_start__lte=date_to,
    )

    trainer_ids = sessions_qs.values_list("trainer_id", flat=True).distinct()
    trainers = Trainer.objects.filter(pk__in=trainer_ids, is_active=True).order_by(
        "last_name", "first_name"
    )

    rows = []
    for t in trainers:
        t_sessions = sessions_qs.filter(trainer=t).select_related("formation", "client")
        rows.append(
            {
                "trainer": t,
                "session_count": t_sessions.count(),
                "sessions": list(t_sessions.order_by("-date_start")),
            }
        )

    # Sort by session count descending
    rows.sort(key=lambda r: r["session_count"], reverse=True)

    return render(
        request,
        "reporting/trainer_activity.html",
        {
            "form": form,
            "rows": rows,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
