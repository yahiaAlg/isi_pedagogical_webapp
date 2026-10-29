from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from formations.models import Session

from . import transport
from .models import RosterEntry, SyncJob, SyncState
from .pull import CURSOR_KEY, LAST_PULL_KEY, pull, pull_auto
from .push import flush_jobs
from .seeding import UNVALIDATED_STATUSES, seed_session, seedable_statuses


def _can_manage(request):
    return request.user.profile.can_manage_sessions()


@login_required
def status(request):
    entries = RosterEntry.objects.all()
    context = {
        "configured": transport.is_configured(),
        "cursor": SyncState.get(CURSOR_KEY, "—"),
        "last_pull": parse_datetime(SyncState.get(LAST_PULL_KEY, "")) if SyncState.get(LAST_PULL_KEY) else None,
        "last_errors": [e for e in SyncState.get("last_errors", "").splitlines() if e],
        "pending_jobs": SyncJob.objects.filter(status=SyncJob.PENDING).count(),
        "failed_jobs": SyncJob.objects.filter(status=SyncJob.FAILED).count(),
        "jobs": SyncJob.objects.all()[:15],
        "roster_total": entries.count(),
        "roster_seeded": entries.filter(participant__isnull=False).count(),
        "roster_waiting": entries.filter(
            participant__isnull=True, removed_on_site=False, enrollment_status__in=seedable_statuses()
        ).count(),
        "roster_unvalidated": entries.filter(participant__isnull=True, removed_on_site=False)
        .exclude(enrollment_status__in=seedable_statuses())
        .count(),
        "roster_removed": entries.filter(removed_on_site=True).count(),
        "can_manage": _can_manage(request),
    }
    return render(request, "sync/status.html", context)


@login_required
@require_POST
def run_now(request):
    if not _can_manage(request):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("sync:status")
    try:
        sent, left = flush_jobs()
        result = pull_auto()
    except transport.SyncError as exc:
        messages.error(request, f"Synchronisation impossible : {exc}")
        return redirect("sync:status")
    if "initialised_at" in result:
        messages.info(request, "Synchronisation initialisée : les prochains clients du site seront importés.")
    else:
        messages.success(
            request,
            f"Synchronisation terminée : {sent} formation(s) envoyée(s), {result['applied']} client(s) du site traité(s).",
        )
    for err in result["errors"][:5]:
        messages.warning(request, err)
    return redirect(request.POST.get("next") or "sync:status")


@login_required
@require_POST
def import_existing(request):
    """One-off: import EVERY client already on the website (matched to existing ISI clients
    by RC, NIF, then name), not only the ones created since the first sync."""
    if not _can_manage(request):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("sync:status")
    try:
        result = pull(full=True)
    except transport.SyncError as exc:
        messages.error(request, f"Import impossible : {exc}")
        return redirect("sync:status")
    messages.success(
        request, f"{result['applied']} client(s) du site importé(s) / mis à jour : {result['actions']}"
    )
    for err in result["errors"][:5]:
        messages.warning(request, err)
    return redirect("sync:status")


@login_required
@require_POST
def retry_failed(request):
    if not _can_manage(request):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
    else:
        n = SyncJob.objects.filter(status=SyncJob.FAILED).update(status=SyncJob.PENDING, attempts=0)
        messages.success(request, f"{n} envoi(s) remis en file d'attente.")
    return redirect("sync:status")


@login_required
@require_POST
def import_into_session(request, session_pk):
    """Manually add the website participants announced for this session's
    client + formation (the automatic path covers session creation)."""
    session = get_object_or_404(Session, pk=session_pk)
    if not _can_manage(request):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
    elif not session.can_add_participants():
        messages.error(request, "Capacité atteinte ou session non modifiable.")
    else:
        c = seed_session(session, include_pending=bool(request.POST.get("include_pending")))
        if c["seeded"] or c["linked"]:
            messages.success(
                request, f"{c['seeded']} participant(s) ajouté(s) depuis le site ({c['linked']} déjà présent(s))."
            )
        else:
            messages.info(request, "Aucun participant du site en attente pour cette session.")
    return redirect("formations:session_detail", pk=session.pk)
