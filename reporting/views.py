from collections import defaultdict
from decimal import Decimal

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Avg, Q, Sum, F
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone

from formations.models import Formation, Session, Participant
from resources.models import (
    Trainer,
    Room,
    Equipment,
    EquipmentAllocation,
    PedagogicalAsset,
    AssetMovement,
)
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
    An optional date-range filter narrows every KPI and the mini
    charts to the selected period; with no filter, KPIs default to
    "this month" / "year-to-date" windows as before.
    """
    _require_reporting(request)

    now = timezone.now()
    year = now.year
    month = now.month

    form = DateRangeForm(request.GET or None)
    date_from = date_to = None
    if form and form.is_valid():
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
    is_filtered = bool(date_from or date_to)

    if is_filtered:
        # --- Period-scoped KPIs when a date range is applied
        period_sessions_qs = Session.objects.exclude(status="cancelled")
        if date_from:
            period_sessions_qs = period_sessions_qs.filter(date_start__gte=date_from)
        if date_to:
            period_sessions_qs = period_sessions_qs.filter(date_start__lte=date_to)
        period_sessions = list(period_sessions_qs)

        sessions_this_month = len(period_sessions)

        period_participants_qs = Participant.objects.filter(
            session__in=period_sessions_qs
        )
        participants_this_month = period_participants_qs.count()

        attestations_ytd = period_participants_qs.filter(
            certificate_issued=True
        ).count()

        active_sessions = period_sessions_qs.filter(
            status__in=["planned", "in_progress"]
        ).count()

        non_cancelled = [s for s in period_sessions if s.capacity]
        avg_fill_rate = 0
        if non_cancelled:
            avg_fill_rate = round(
                sum(s.fill_rate for s in non_cancelled) / len(non_cancelled), 1
            )

        period_participants = list(
            period_participants_qs.select_related("session__formation")
        )
        total_participants = len(period_participants)
        overall_pass_rate = 0
        if total_participants:
            passed = sum(1 for p in period_participants if p.result == "passed")
            overall_pass_rate = round(passed / total_participants * 100, 1)
    else:
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
        "form": form,
        "is_filtered": is_filtered,
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

    # --- Mini sessions trend + status snapshot for the dashboard's overview
    # chart (spec §14.1 landing page enrichment). Uses the same date range
    # as the KPIs when filtered; otherwise defaults to the trailing 6 months.
    from dateutil.relativedelta import relativedelta

    trend_qs = Session.objects.exclude(status="cancelled")
    status_qs = Session.objects.all()
    if is_filtered:
        if date_from:
            trend_qs = trend_qs.filter(date_start__gte=date_from)
            status_qs = status_qs.filter(date_start__gte=date_from)
        if date_to:
            trend_qs = trend_qs.filter(date_start__lte=date_to)
            status_qs = status_qs.filter(date_start__lte=date_to)
    else:
        trend_from = now.date() - relativedelta(months=6)
        trend_qs = trend_qs.filter(date_start__gte=trend_from)

    sessions_trend = list(
        trend_qs.annotate(month=TruncMonth("date_start"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )
    status_labels = dict(Session.STATUS_CHOICES)
    status_counts = (
        status_qs.values("status").annotate(count=Count("pk")).order_by("-count")
    )
    status_snapshot_chart = [
        {"label": status_labels.get(s["status"], s["status"]), "value": s["count"]}
        for s in status_counts
        if s["count"]
    ]
    context["sessions_trend"] = sessions_trend
    context["status_snapshot_chart"] = status_snapshot_chart

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

    # ---- Threshold distribution (spec §14.2 color buckets)
    full_count = sum(1 for r in rows if r["available_spots"] == 0)
    high_count = sum(1 for r in rows if r["color_class"] == "success")
    mid_count = sum(1 for r in rows if r["color_class"] == "warning")
    low_count = sum(1 for r in rows if r["color_class"] == "secondary")
    distribution_chart = [
        {"label": "≥ 90%", "value": high_count},
        {"label": "60–89%", "value": mid_count},
        {"label": "< 60%", "value": low_count},
    ]
    total_available_spots = sum(r["available_spots"] for r in rows)
    total_participants = sum(r["participant_count"] for r in rows)

    return render(
        request,
        "reporting/fill_rate.html",
        {
            "form": form,
            "rows": rows,
            "avg_fill_rate": avg,
            "full_count": full_count,
            "distribution_chart": distribution_chart,
            "total_available_spots": total_available_spots,
            "total_participants": total_participants,
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
    sessions_qs = Session.objects.exclude(status="cancelled").select_related(
        "formation__category"
    )
    sessions_qs = _apply_date_filter(sessions_qs, form)
    sessions_list = list(sessions_qs)

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
        f_sessions = [s for s in sessions_list if s.formation_id == f.pk]
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

    # ---- KPI strip
    total_sessions = len(sessions_list)
    total_formations_active = len(rows)
    overall_avg_fill = (
        round(sum(s.fill_rate for s in sessions_list) / total_sessions, 1)
        if total_sessions
        else 0
    )
    top_formation_row = rows[0] if rows else None

    # ---- Category distribution (session count per formation category)
    category_counts = defaultdict(int)
    for s in sessions_list:
        cat = s.formation.category.name if s.formation.category_id else "Sans catégorie"
        category_counts[cat] += 1
    category_chart = sorted(
        ({"label": k, "value": v} for k, v in category_counts.items()),
        key=lambda r: r["value"],
        reverse=True,
    )

    # ---- Fill-rate ranking for top formations (by session volume)
    ranking_chart = [
        {"label": r["formation"].code or r["formation"].title, "value": r["avg_fill_rate"]}
        for r in rows[:10]
    ]

    return render(
        request,
        "reporting/by_formation.html",
        {
            "form": form,
            "rows": rows,
            "total_sessions": total_sessions,
            "total_formations_active": total_formations_active,
            "overall_avg_fill": overall_avg_fill,
            "top_formation_row": top_formation_row,
            "category_chart": category_chart,
            "ranking_chart": ranking_chart,
        },
    )


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

    # ---- Breakdown by formation (top 8 by certificate volume)
    by_formation_counts = (
        certs_qs.values(
            "session__formation__title", "session__formation__code"
        )
        .annotate(count=Count("pk"))
        .order_by("-count")[:8]
    )
    formation_chart = [
        {
            "label": row["session__formation__code"]
            or row["session__formation__title"],
            "value": row["count"],
        }
        for row in by_formation_counts
    ]

    # ---- Breakdown by attestation type (diplôme vs certificat)
    attestation_labels = dict(Formation.ATTESTATION_TYPE_CHOICES)
    by_type_counts = (
        certs_qs.values("session__formation__attestation_type")
        .annotate(count=Count("pk"))
        .order_by("-count")
    )
    attestation_chart = [
        {
            "label": attestation_labels.get(
                row["session__formation__attestation_type"],
                row["session__formation__attestation_type"] or "—",
            ),
            "value": row["count"],
        }
        for row in by_type_counts
    ]

    return render(
        request,
        "reporting/certificate_volume.html",
        {
            "form": form,
            "by_month": list(by_month),
            "by_year": list(by_year),
            "total": total,
            "formation_chart": formation_chart,
            "attestation_chart": attestation_chart,
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


# ---------------------------------------------------------------------------
# §14.4  Costs & resource utilization — business decision report
# ---------------------------------------------------------------------------


@login_required
def cost_utilization_report(request):
    """
    Cross-app report combining resource costs (equipment, pedagogical
    assets) with their utilization, plus the revenue/margin those
    resources produced in the selected period. Intended to support
    business decisions: what's costing money, what's idle, what needs
    restocking, and which formations/rooms are most profitable.
    """
    _require_reporting(request)

    form = DateRangeForm(request.GET or None)
    date_from = date_to = None
    if form and form.is_valid():
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")

    # ------------------------------------------------------------ sessions
    sessions_qs = Session.objects.exclude(status="cancelled").select_related(
        "formation", "room"
    )
    if date_from:
        sessions_qs = sessions_qs.filter(date_start__gte=date_from)
    if date_to:
        sessions_qs = sessions_qs.filter(date_start__lte=date_to)
    sessions_list = list(sessions_qs)
    session_ids = [s.pk for s in sessions_list]

    # ------------------------------------------------ costs tied to a session
    alloc_cost_by_session = dict(
        EquipmentAllocation.objects.filter(session_id__in=session_ids)
        .values("session_id")
        .annotate(c=Sum("total_price"))
        .values_list("session_id", "c")
    )
    move_cost_by_session = dict(
        AssetMovement.objects.filter(
            session_id__in=session_ids, movement_type="delivery"
        )
        .values("session_id")
        .annotate(c=Sum("total_price"))
        .values_list("session_id", "c")
    )

    # ------------------------------------------- revenue / cost by formation
    # Spec §new — price now lives on the session cycle (primary session),
    # not the formation, so revenue is read from each cycle's own
    # total_price (which already applies that cycle's price_mode) instead
    # of a flat formation.base_price × participants. Only primary sessions
    # are counted for revenue — child (day 2-N) sessions are the same
    # cycle and would otherwise double/triple-count it — while costs are
    # still summed across every session (equipment/assets can be
    # allocated to any day).
    revenue_by_formation = defaultdict(lambda: Decimal("0"))
    cost_by_formation = defaultdict(lambda: Decimal("0"))
    for s in sessions_list:
        if s.is_primary:
            revenue_by_formation[s.formation] += s.total_price or Decimal("0")
        session_cost = (alloc_cost_by_session.get(s.pk) or Decimal("0")) + (
            move_cost_by_session.get(s.pk) or Decimal("0")
        )
        cost_by_formation[s.formation] += session_cost

    revenue_cost_rows = []
    for f, revenue in revenue_by_formation.items():
        cost = cost_by_formation.get(f, Decimal("0"))
        revenue_cost_rows.append(
            {"formation": f, "revenue": revenue, "cost": cost, "margin": revenue - cost}
        )
    revenue_cost_rows.sort(key=lambda r: r["revenue"], reverse=True)
    top_revenue_rows = revenue_cost_rows[:8]

    total_revenue = sum((r["revenue"] for r in revenue_cost_rows), Decimal("0"))
    total_attributed_cost = sum((r["cost"] for r in revenue_cost_rows), Decimal("0"))
    estimated_margin = total_revenue - total_attributed_cost

    # ---------------------------------------------------------- equipment
    equipment_list = list(Equipment.objects.all())
    equipment_total_value = sum(
        (e.total_price or Decimal("0") for e in equipment_list), Decimal("0")
    )
    total_qty = sum(e.quantity for e in equipment_list)
    total_reserved = sum(e.quantity_reserved for e in equipment_list)
    equipment_avg_utilization = (
        round(total_reserved / total_qty * 100, 1) if total_qty else 0
    )

    cat_labels = dict(Equipment.CATEGORY_CHOICES)
    equipment_value_by_cat = defaultdict(lambda: Decimal("0"))
    for e in equipment_list:
        equipment_value_by_cat[cat_labels.get(e.category, e.category)] += (
            e.total_price or Decimal("0")
        )
    equipment_category_chart = sorted(
        (
            {"label": label, "value": float(value)}
            for label, value in equipment_value_by_cat.items()
            if value
        ),
        key=lambda r: r["value"],
        reverse=True,
    )

    status_labels = dict(Equipment.STATUS_CHOICES)
    equipment_qty_by_status = defaultdict(int)
    for e in equipment_list:
        equipment_qty_by_status[status_labels.get(e.status, e.status)] += e.quantity
    equipment_status_chart = [
        {"label": label, "value": qty}
        for label, qty in equipment_qty_by_status.items()
        if qty
    ]

    equipment_rows = []
    for e in equipment_list:
        util = round(e.quantity_reserved / e.quantity * 100, 1) if e.quantity else 0
        equipment_rows.append({"equipment": e, "utilization": util})
    equipment_rows.sort(
        key=lambda r: (r["equipment"].total_price or Decimal("0")), reverse=True
    )
    top_equipment_by_value = equipment_rows[:10]
    top_equipment_by_utilization = sorted(
        [r for r in equipment_rows if r["equipment"].quantity],
        key=lambda r: r["utilization"],
        reverse=True,
    )[:8]

    allocation_qs_period = EquipmentAllocation.objects.all()
    if date_from:
        allocation_qs_period = allocation_qs_period.filter(
            allocated_at__date__gte=date_from
        )
    if date_to:
        allocation_qs_period = allocation_qs_period.filter(
            allocated_at__date__lte=date_to
        )
    allocation_cost_period = (
        allocation_qs_period.aggregate(v=Sum("total_price"))["v"] or Decimal("0")
    )

    # ---------------------------------------------------- pedagogical assets
    asset_qs = PedagogicalAsset.objects.filter(is_active=True).select_related(
        "category"
    )
    asset_list = list(asset_qs)
    asset_stock_value = sum(
        (a.total_price or Decimal("0") for a in asset_list), Decimal("0")
    )

    asset_value_by_cat = defaultdict(lambda: Decimal("0"))
    for a in asset_list:
        asset_value_by_cat[a.category.name] += a.total_price or Decimal("0")
    asset_category_chart = sorted(
        (
            {"label": label, "value": float(value)}
            for label, value in asset_value_by_cat.items()
            if value
        ),
        key=lambda r: r["value"],
        reverse=True,
    )

    low_stock_assets = [a for a in asset_list if a.is_low_stock or a.is_exhausted]
    low_stock_assets.sort(key=lambda a: a.quantity_in_stock)

    movement_qs_period = AssetMovement.objects.filter(movement_type="delivery")
    if date_from:
        movement_qs_period = movement_qs_period.filter(
            performed_at__date__gte=date_from
        )
    if date_to:
        movement_qs_period = movement_qs_period.filter(
            performed_at__date__lte=date_to
        )
    consumption_cost_period = (
        movement_qs_period.aggregate(v=Sum("total_price"))["v"] or Decimal("0")
    )

    consumed_map = {
        row["asset_id"]: row
        for row in movement_qs_period.values("asset_id").annotate(
            qty=Sum("quantity"), cost=Sum("total_price")
        )
    }
    asset_rows = []
    for a in asset_list:
        c = consumed_map.get(a.pk, {})
        asset_rows.append(
            {
                "asset": a,
                "consumed_qty": c.get("qty") or 0,
                "consumed_cost": c.get("cost") or Decimal("0"),
            }
        )
    asset_rows.sort(key=lambda r: r["consumed_cost"], reverse=True)
    top_consumed_assets = [r for r in asset_rows if r["consumed_cost"]][:8]

    # Monthly consumption cost trend — rolling 6 months, independent of the
    # date-range filter so the trend line always gives useful context.
    from dateutil.relativedelta import relativedelta

    now_date = timezone.now().date()
    trend_from = now_date - relativedelta(months=6)
    trend_qs = (
        AssetMovement.objects.filter(
            movement_type="delivery", performed_at__date__gte=trend_from
        )
        .annotate(month=TruncMonth("performed_at"))
        .values("month")
        .annotate(cost=Sum("total_price"))
        .order_by("month")
    )
    consumption_trend = list(trend_qs)

    # -------------------------------------------------------------- rooms
    room_session_counts = {
        row["room_id"]: row["c"]
        for row in sessions_qs.values("room_id").annotate(c=Count("pk"))
    }
    room_rows = []
    for r in Room.objects.filter(is_active=True):
        r_sessions = [s for s in sessions_list if s.room_id == r.pk]
        avg_fill = (
            round(sum(s.fill_rate for s in r_sessions) / len(r_sessions), 1)
            if r_sessions
            else 0
        )
        room_rows.append(
            {
                "room": r,
                "session_count": room_session_counts.get(r.pk, 0),
                "avg_fill_rate": avg_fill,
                "equipment_count": r.equipment_set.count(),
            }
        )
    room_rows.sort(key=lambda r: r["session_count"], reverse=True)

    context = {
        "form": form,
        # KPIs
        "equipment_total_value": equipment_total_value,
        "equipment_avg_utilization": equipment_avg_utilization,
        "asset_stock_value": asset_stock_value,
        "consumption_cost_period": consumption_cost_period,
        "allocation_cost_period": allocation_cost_period,
        "total_resource_cost_period": consumption_cost_period + allocation_cost_period,
        "estimated_revenue_period": total_revenue,
        "estimated_margin_period": estimated_margin,
        "low_stock_count": len(low_stock_assets),
        # Charts
        "equipment_category_chart": equipment_category_chart,
        "equipment_status_chart": equipment_status_chart,
        "asset_category_chart": asset_category_chart,
        "consumption_trend": consumption_trend,
        "top_revenue_rows": top_revenue_rows,
        "top_consumed_assets": top_consumed_assets,
        "top_equipment_by_utilization": top_equipment_by_utilization,
        "room_rows": room_rows,
        # Tables
        "equipment_rows": top_equipment_by_value,
        "asset_rows": asset_rows,
        "low_stock_assets": low_stock_assets,
    }
    return render(request, "reporting/cost_utilization.html", context)


# ---------------------------------------------------------------------------
# §14.5  Client activity & revenue report
# ---------------------------------------------------------------------------


@login_required
def client_activity_report(request):
    """
    Client-facing business report: sessions, participants, revenue and
    average fill rate per client, plus city distribution and a top-10
    revenue ranking chart.
    """
    _require_reporting(request)

    from clients.models import Client

    form = DateRangeForm(request.GET or None)
    sessions_qs = Session.objects.exclude(status="cancelled").select_related(
        "formation", "client"
    )
    sessions_qs = _apply_date_filter(sessions_qs, form)
    sessions_list = list(sessions_qs)

    # Spec §new — same switch as cost_utilization_report: revenue now
    # comes from each cycle's own total_price (primary session only, to
    # avoid counting the same cycle once per day).
    revenue_by_client = defaultdict(lambda: Decimal("0"))
    sessions_by_client_map = defaultdict(list)
    for s in sessions_list:
        if s.is_primary:
            revenue_by_client[s.client_id] += s.total_price or Decimal("0")
        sessions_by_client_map[s.client_id].append(s)

    client_ids = list(sessions_by_client_map.keys())
    clients = Client.objects.filter(pk__in=client_ids)

    rows = []
    for c in clients:
        c_sessions = sessions_by_client_map.get(c.pk, [])
        total_participants = sum(s.participant_count for s in c_sessions)
        avg_fill = (
            round(sum(s.fill_rate for s in c_sessions) / len(c_sessions), 1)
            if c_sessions
            else 0
        )
        rows.append(
            {
                "client": c,
                "session_count": len(c_sessions),
                "total_participants": total_participants,
                "revenue": revenue_by_client.get(c.pk, Decimal("0")),
                "avg_fill_rate": avg_fill,
            }
        )
    rows.sort(key=lambda r: r["revenue"], reverse=True)

    total_revenue = sum((r["revenue"] for r in rows), Decimal("0"))
    total_clients_active = len(rows)
    top_clients_chart = [
        {"label": r["client"].name, "value": float(r["revenue"])}
        for r in rows[:10]
        if r["revenue"]
    ]

    # City distribution (by number of active clients in the result set)
    city_counts = defaultdict(int)
    for r in rows:
        city_counts[r["client"].city or "—"] += 1
    city_chart = sorted(
        ({"label": city, "value": n} for city, n in city_counts.items()),
        key=lambda r: r["value"],
        reverse=True,
    )[:8]

    return render(
        request,
        "reporting/client_activity.html",
        {
            "form": form,
            "rows": rows,
            "total_revenue": total_revenue,
            "total_clients_active": total_clients_active,
            "avg_revenue_per_client": (
                round(total_revenue / total_clients_active, 0)
                if total_clients_active
                else 0
            ),
            "top_clients_chart": top_clients_chart,
            "city_chart": city_chart,
        },
    )


# ---------------------------------------------------------------------------
# §14.6  Room / space utilization report
# ---------------------------------------------------------------------------


@login_required
def room_utilization_report(request):
    """
    Occupancy and capacity-usage report per room: session count, average
    fill rate, average capacity usage (participants vs. room capacity),
    plus a 6-month bookings trend across all rooms.
    """
    _require_reporting(request)

    from dateutil.relativedelta import relativedelta

    form = DateRangeForm(request.GET or None)
    sessions_qs = Session.objects.exclude(status="cancelled").select_related(
        "formation", "room"
    )
    sessions_qs = _apply_date_filter(sessions_qs, form)
    sessions_list = [s for s in sessions_qs if s.room_id]

    by_room = defaultdict(list)
    for s in sessions_list:
        by_room[s.room_id].append(s)

    rooms = Room.objects.filter(is_active=True)
    rows = []
    for r in rooms:
        r_sessions = by_room.get(r.pk, [])
        session_count = len(r_sessions)
        avg_fill = (
            round(sum(s.fill_rate for s in r_sessions) / session_count, 1)
            if session_count
            else 0
        )
        avg_capacity_use = (
            round(
                sum(
                    (s.participant_count / r.capacity * 100 if r.capacity else 0)
                    for s in r_sessions
                )
                / session_count,
                1,
            )
            if session_count
            else 0
        )
        rows.append(
            {
                "room": r,
                "session_count": session_count,
                "avg_fill_rate": avg_fill,
                "avg_capacity_use": avg_capacity_use,
                "equipment_count": r.equipment_set.count(),
            }
        )
    rows.sort(key=lambda r: r["session_count"], reverse=True)

    total_sessions_with_room = sum(r["session_count"] for r in rows)
    busiest_room = rows[0] if rows and rows[0]["session_count"] else None
    idle_rooms = [r for r in rows if r["session_count"] == 0]

    usage_chart = [
        {"label": r["room"].name, "value": r["session_count"]}
        for r in rows
        if r["session_count"]
    ]

    # 6-month booking trend across all rooms (context, independent of filter)
    now_date = timezone.now().date()
    trend_from = now_date - relativedelta(months=6)
    trend_qs = (
        Session.objects.exclude(status="cancelled")
        .filter(room__isnull=False, date_start__gte=trend_from)
        .annotate(month=TruncMonth("date_start"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )
    booking_trend = list(trend_qs)

    return render(
        request,
        "reporting/room_utilization.html",
        {
            "form": form,
            "rows": rows,
            "total_sessions_with_room": total_sessions_with_room,
            "busiest_room": busiest_room,
            "idle_room_count": len(idle_rooms),
            "usage_chart": usage_chart,
            "booking_trend": booking_trend,
        },
    )


# ---------------------------------------------------------------------------
# §14.7  Activity trends — sessions & participants over time
# ---------------------------------------------------------------------------


@login_required
def activity_trends_report(request):
    """
    12-month activity trend: sessions and participants volume per month,
    plus the current status breakdown of all sessions — gives a quick
    read on institute momentum and pipeline health.
    """
    _require_reporting(request)

    from dateutil.relativedelta import relativedelta

    now_date = timezone.now().date()
    default_from = now_date - relativedelta(months=12)

    form = DateRangeForm(request.GET or None)
    if form and form.is_valid() and form.cleaned_data.get("date_from"):
        trend_from = form.cleaned_data["date_from"]
    else:
        trend_from = default_from
    if form and form.is_valid() and form.cleaned_data.get("date_to"):
        trend_to = form.cleaned_data["date_to"]
    else:
        trend_to = now_date

    sessions_qs = Session.objects.filter(
        date_start__gte=trend_from, date_start__lte=trend_to
    )

    sessions_trend = list(
        sessions_qs.exclude(status="cancelled")
        .annotate(month=TruncMonth("date_start"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )
    participants_trend = list(
        Participant.objects.filter(
            session__date_start__gte=trend_from,
            session__date_start__lte=trend_to,
        )
        .exclude(session__status="cancelled")
        .annotate(month=TruncMonth("session__date_start"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )

    status_labels = dict(Session.STATUS_CHOICES)
    status_counts = (
        sessions_qs.values("status").annotate(count=Count("pk")).order_by("-count")
    )
    status_chart = [
        {"label": status_labels.get(s["status"], s["status"]), "value": s["count"]}
        for s in status_counts
    ]

    location_labels = dict(Session.LOCATION_CHOICES)
    location_counts = (
        sessions_qs.exclude(status="cancelled")
        .values("location_type")
        .annotate(count=Count("pk"))
        .order_by("-count")
    )
    location_chart = [
        {
            "label": location_labels.get(l["location_type"], l["location_type"]),
            "value": l["count"],
        }
        for l in location_counts
    ]

    total_sessions_period = sessions_qs.exclude(status="cancelled").count()
    total_participants_period = sum(t["count"] for t in participants_trend)
    cancelled_period = sessions_qs.filter(status="cancelled").count()

    return render(
        request,
        "reporting/activity_trends.html",
        {
            "form": form,
            "date_from": trend_from,
            "date_to": trend_to,
            "sessions_trend": sessions_trend,
            "participants_trend": participants_trend,
            "status_chart": status_chart,
            "location_chart": location_chart,
            "total_sessions_period": total_sessions_period,
            "total_participants_period": total_participants_period,
            "cancelled_period": cancelled_period,
        },
    )
