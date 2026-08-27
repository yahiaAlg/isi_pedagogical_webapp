from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from formations.models import Session, Participant
from formations.utils import (
    compute_session_reference_renumbering,
    apply_session_reference_renumbering,
)
from .models import InstituteInfo, PVDefaultSignatory, SequenceCounter
from .forms import (
    InstituteInfoForm,
    PVDefaultSignatoryForm,
    SequenceCounterForm,
    SequencePeriodForm,
)
from .sequencing import PV_KIND, CERTIFICATE_KIND, MISSION_ORDER_KIND


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


@login_required
def sequence_counter_list(request):
    """
    Numbering counters (PV monthly / certificate yearly / ordre de mission
    yearly) — Admin only.

    Shows the ACTIVE counter of each kind (the one currently handing out
    the next number — see SequenceCounter.get_active_period_key, bootstrapped
    to today's calendar period the first time a kind is touched) plus recent
    history, with a link to manually override the active counter's value
    for edge cases — e.g. resuming a series that was numbered on paper
    before this app existed, or correcting a mistake. Any OTHER period can
    be picked up via "Autre période" and, from its edit form, explicitly
    activated — pinning numbering to it indefinitely, regardless of the
    real date, until an admin activates a different period.
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    # Display order: Attestation/Certificat (année) — PV (mois), avec
    # codification {BRANCH}{SPECIALITE} — Ordre de mission (année).
    kind_order = [CERTIFICATE_KIND, PV_KIND, MISSION_ORDER_KIND]
    kind_labels = dict(SequenceCounter.KIND_CHOICES)

    counters = {}
    for kind in kind_order:
        active_period_key = SequenceCounter.get_active_period_key(kind)
        current = SequenceCounter.objects.get(kind=kind, period_key=active_period_key)
        history = (
            SequenceCounter.objects.filter(kind=kind)
            .exclude(pk=current.pk)
            .order_by("-period_key")[:12]
        )
        counters[kind] = {
            "label": kind_labels[kind],
            "current": current,
            "history": history,
            "is_monthly": kind == PV_KIND,
            "period_form": SequencePeriodForm(
                prefix=kind,
                initial={
                    "year": timezone.localdate().year,
                    "month": timezone.localdate().month,
                },
            ),
        }

    return render(request, "core/sequence_counter_list.html", {"counters": counters})


@login_required
def sequence_counter_period(request, kind):
    """
    Jump to (auto-creating if needed) the counter for an arbitrary period
    of `kind` — a past month for the PV sequencer, a past year for the
    certificate/ordre de mission sequencers — and go straight to its edit
    form. This is how older entries predating the app's current period
    (e.g. a series resumed mid-year, or historical data entry) get
    backfilled: the admin picks the period they need instead of only ever
    seeing/editing the current one.
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    if kind not in dict(SequenceCounter.KIND_CHOICES):
        messages.error(request, "Type de compteur inconnu.")
        return redirect("core:sequence_counter_list")

    form = SequencePeriodForm(request.GET or None, prefix=kind)
    if not form.is_valid():
        messages.error(
            request, "Période invalide — vérifiez l'année (et le mois pour un PV)."
        )
        return redirect("core:sequence_counter_list")

    year = form.cleaned_data["year"]
    if kind == PV_KIND:
        month = form.cleaned_data["month"] or timezone.localdate().month
        period_key = f"{year:04d}-{month:02d}"
    else:
        period_key = f"{year:04d}"

    counter, _ = SequenceCounter.objects.get_or_create(kind=kind, period_key=period_key)
    return redirect("core:sequence_counter_edit", pk=counter.pk)


@login_required
def sequence_counter_edit(request, pk):
    """
    Override a single counter's last_value. Saving does not touch any
    document already printed — it only changes where the NEXT allocation
    starts counting from. Session.assign_pv_number() /
    assign_certificate_number() keep working exactly as before and will
    simply continue incrementing from whatever is saved here — provided
    this counter's period is the ACTIVE one for its kind (see
    SequenceCounter.is_active / the "Définir comme période active" button
    below, for periods that aren't).
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


@login_required
def sequence_counter_activate(request, pk):
    """
    Pin `counter`'s period as the ACTIVE one for its kind — i.e. the
    period that numbers the NEXT document of that kind — regardless of
    whether it matches today's real month/year. Stays active indefinitely
    (manual control), until an admin activates another period for the
    same kind. POST-only to avoid accidental activation via a stray GET
    (crawler, browser prefetch, etc.).
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    counter = get_object_or_404(SequenceCounter, pk=pk)

    if request.method != "POST":
        return redirect("core:sequence_counter_list")

    SequenceCounter.set_active_period(counter.kind, counter.period_key)
    messages.success(
        request,
        f"Période « {counter.period_key} » définie comme période active pour "
        f"« {counter.get_kind_display()} ». Les prochains numéros seront "
        f"attribués sous cette période jusqu'à activation d'une autre.",
    )
    return redirect("core:sequence_counter_list")


@login_required
def session_reference_maintenance(request):
    """
    Settings quick action — "Corriger les références de session".

    GET shows a dry-run preview of what `compute_session_reference_renumbering`
    would change (nothing is written yet): every session whose reference
    would move, old → new, grouped and counted. POST actually applies it
    (see `apply_session_reference_renumbering`).

    A preview-then-confirm flow, rather than a single-click action, is
    deliberate — session references appear on already-printed/signed
    documents (PV, attestations, ordres de mission…), so silently
    reshuffling them on every click would be surprising and hard to
    reason about; the admin sees exactly what will move before it does.
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    changes = compute_session_reference_renumbering()

    if request.method == "POST":
        count = apply_session_reference_renumbering(changes)
        if count:
            messages.success(
                request,
                f"{count} référence(s) de session corrigée(s) — numérotation "
                f"remise à plat par ordre chronologique.",
            )
        else:
            messages.info(request, "Aucune correction nécessaire — la numérotation était déjà cohérente.")
        return redirect("core:settings")

    return render(
        request,
        "core/session_reference_maintenance.html",
        {
            "changes": changes,
            "changes_count": len(changes),
        },
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
