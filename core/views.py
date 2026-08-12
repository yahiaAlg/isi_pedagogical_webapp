from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from formations.models import Session, Participant
from .models import InstituteInfo, CommitteeMember
from .forms import InstituteInfoForm, CommitteeMemberForm


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
            "committee_members": CommitteeMember.objects.all(),
            "committee_member_form": CommitteeMemberForm(),
        },
    )


@login_required
def committee_member_add(request):
    """Add a default PV committee member (e.g. a director) — Admin only.
    Editing reuses this same view: POST with `member_id` updates instead
    of creating."""
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")

    member_id = request.POST.get("member_id") or request.GET.get("member_id")
    instance = get_object_or_404(CommitteeMember, pk=member_id) if member_id else None

    if request.method == "POST":
        form = CommitteeMemberForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Membre du comité mis à jour." if instance else "Membre du comité ajouté.",
            )
            return redirect("core:settings")
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
        return render(
            request,
            "core/settings.html",
            {
                "form": InstituteInfoForm(instance=InstituteInfo.get_instance()),
                "instance": InstituteInfo.get_instance(),
                "committee_members": CommitteeMember.objects.all(),
                "committee_member_form": form,
                "editing_member_id": instance.pk if instance else None,
            },
        )

    return redirect("core:settings")


@login_required
def committee_member_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")
    member = get_object_or_404(CommitteeMember, pk=pk)
    if request.method == "POST":
        member.delete()
        messages.success(request, "Membre du comité supprimé.")
    return redirect("core:settings")


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
