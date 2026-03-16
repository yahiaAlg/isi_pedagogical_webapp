from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q

from formations.models import Session, Participant


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_avg_fill_rate():
    """
    Fill rate is a computed property (spec §10.3).
    Iterate over non-cancelled sessions with non-zero capacity.
    """
    sessions = list(
        Session.objects.exclude(status="cancelled")
        .exclude(capacity=0)
        .prefetch_related("participant_set")
    )
    if not sessions:
        return 0
    rates = [s.participant_count / s.capacity * 100 for s in sessions]
    return round(sum(rates) / len(rates), 1)


def _compute_pass_rate():
    total = Participant.objects.count()
    if not total:
        return 0
    passed = Participant.objects.filter(result="passed").count()
    return round(passed / total * 100, 1)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@login_required
def dashboard(request):
    """
    Dashboard with the 6 KPIs defined in spec §14.1:
      1. Sessions this month
      2. Participants this month
      3. Attestations issued YTD
      4. Active sessions (planned + in_progress)
      5. Average fill rate (non-cancelled sessions)
      6. Overall pass rate
    """
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    context = {
        # KPI 1 — Sessions this month
        "sessions_this_month": Session.objects.filter(
            date_start__month=current_month,
            date_start__year=current_year,
        ).count(),
        # KPI 2 — Participants this month
        "participants_this_month": Participant.objects.filter(
            session__date_start__month=current_month,
            session__date_start__year=current_year,
        ).count(),
        # KPI 3 — Attestations issued year-to-date
        "attestations_ytd": Participant.objects.filter(
            certificate_issued=True,
            session__date_start__year=current_year,
        ).count(),
        # KPI 4 — Active sessions
        "active_sessions": Session.objects.filter(
            status__in=["planned", "in_progress"]
        ).count(),
        # KPI 5 — Average fill rate across all non-cancelled sessions
        "avg_fill_rate": _compute_avg_fill_rate(),
        # KPI 6 — Overall pass rate
        "overall_pass_rate": _compute_pass_rate(),
    }
    return render(request, "core/dashboard.html", context)
