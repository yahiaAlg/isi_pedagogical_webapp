from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from formations.models import Session, Participant
from .models import InstituteInfo, PVDefaultSignatory, SequenceCounter
from .forms import InstituteInfoForm, PVDefaultSignatoryForm, SequenceCounterForm
from .sequencing import PV_KIND, CERTIFICATE_KIND


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_avg_fill_rate():
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
    participants = list(Participant.objects.select_related("session__formation").all())
    total = len(participants)
    if not total:
        return 0
    passed = sum(1 for p in participants if p.result == "passed")
    return round(passed / total * 100, 1)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@login_required
def dashboard(request):
    now = timezone.now()
    context = {
        "sessions_this_month": Session.objects.filter(
            date_start__month=now.month,
            date_start__year=now.year,
        ).count(),
        "participants_this_month": Participant.objects.filter(
            session__date_start__month=now.month,
            session__date_start__year=now.year,
        ).count(),
        "attestations_ytd": Participant.objects.filter(
            certificate_issued=True,
            session__date_start__year=now.year,
        ).count(),
        "active_sessions": Session.objects.filter(
            status__in=["planned", "in_progress"]
        ).count(),
        "avg_fill_rate": _compute_avg_fill_rate(),
        "overall_pass_rate": _compute_pass_rate(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def settings_view(request):
    """Institut singleton settings — Admin only."""
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    instance = InstituteInfo.get_instance()

    if request.method == "POST":
        form = InstituteInfoForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Paramètres de l'institut enregistrés.")
            return redirect("core:settings")
    else:
        form = InstituteInfoForm(instance=instance)

    return render(
        request,
        "core/settings.html",
        {
            "form": form,
            "instance": instance,
        },
    )


@login_required
def pv_signatory_list(request):
    """Spec — default PV (محضر مداولات) committee members, e.g. institute
    director(s). Configured once here; the trainer and the client's company
    representative are always entered fresh on each PV, never here."""
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    signatories = PVDefaultSignatory.objects.all()
    return render(
        request,
        "core/pv_signatory_list.html",
        {"signatories": signatories},
    )


@login_required
def pv_signatory_form(request, pk=None):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    instance = get_object_or_404(PVDefaultSignatory, pk=pk) if pk else None

    if request.method == "POST":
        form = PVDefaultSignatoryForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Membre par défaut du PV enregistré.")
            return redirect("core:pv_signatory_list")
    else:
        form = PVDefaultSignatoryForm(instance=instance)

    return render(
        request,
        "core/pv_signatory_form.html",
        {"form": form, "instance": instance},
    )


@login_required
def pv_signatory_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    signatory = get_object_or_404(PVDefaultSignatory, pk=pk)
    if request.method == "POST":
        signatory.delete()
        messages.success(request, "Membre par défaut du PV supprimé.")
        return redirect("core:pv_signatory_list")
    return render(
        request,
        "core/pv_signatory_confirm_delete.html",
        {"signatory": signatory},
    )


def _current_period_key(kind):
    """Same period-key scheme as core.sequencing: monthly for PV, yearly
    for certificates."""
    today = timezone.localdate()
    if kind == PV_KIND:
        return f"{today.year:04d}-{today.month:02d}"
    return f"{today.year:04d}"


@login_required
def sequence_counter_list(request):
    """
    Numbering counters (PV monthly / certificate yearly) — Admin only.

    Shows the counter for the current period of each kind (auto-created
    on first view if it doesn't exist yet, starting at 0) plus recent
    history, with a link to manually override the current value for
    edge cases — e.g. resuming a series that was numbered on paper
    before this app existed, or correcting a mistake. Past periods are
    shown read-only; only the counter that governs the NEXT number to be
    handed out (the current period) is meant to be edited in practice,
    though any row can be opened and adjusted if truly needed.
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    counters = {}
    for kind, label in SequenceCounter.KIND_CHOICES:
        period_key = _current_period_key(kind)
        current, _ = SequenceCounter.objects.get_or_create(
            kind=kind, period_key=period_key
        )
        history = (
            SequenceCounter.objects.filter(kind=kind)
            .exclude(pk=current.pk)
            .order_by("-period_key")[:12]
        )
        counters[kind] = {"label": label, "current": current, "history": history}

    return render(request, "core/sequence_counter_list.html", {"counters": counters})


@login_required
def sequence_counter_edit(request, pk):
    """
    Override a single counter's last_value. Saving does not touch any
    document already printed — it only changes where the NEXT allocation
    starts counting from. Session.assign_pv_number() /
    assign_certificate_number() keep working exactly as before and will
    simply continue incrementing from whatever is saved here.
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    counter = get_object_or_404(SequenceCounter, pk=pk)

    if request.method == "POST":
        form = SequenceCounterForm(request.POST, instance=counter)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Compteur « {counter.get_kind_display()} — {counter.period_key} » "
                f"réglé sur {counter.last_value}. Le prochain numéro attribué "
                f"sera le n° {counter.last_value + 1}.",
            )
            return redirect("core:sequence_counter_list")
    else:
        form = SequenceCounterForm(instance=counter)

    return render(
        request,
        "core/sequence_counter_form.html",
        {"form": form, "counter": counter, "next_preview": counter.last_value + 1},
    )


def verify_attestation(request, token):
    """
    Spec §11.6 — public landing page for the attestation QR code.
    `token` is the participant's pk (certificate numbers contain "/" and
    spaces, so they can't be used directly as a URL path segment). No
    login required — the QR is meant to be scanned by anyone holding the
    physical document.
    """
    participant = Participant.objects.filter(
        pk=token, certificate_issued=True
    ).exclude(certificate_number="").first()
    return render(
        request,
        "core/verify_attestation.html",
        {"participant": participant, "token": token},
    )
