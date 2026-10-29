"""Business rules of the approval workflow + notification fan-out.

Views stay thin: they call these functions, which change the request state
(race-safe, via conditional UPDATEs) and create the bell entries + e-mails.
"""

from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .emails import absolute_url, send_emails
from .models import ApprovalRequest, Notification

R = ApprovalRequest
N = Notification


class ApprovalError(Exception):
    """User-facing business error (shown as a flash message)."""


# ── helpers ────────────────────────────────────────────────────────────────
def admins():
    return User.objects.filter(is_active=True, profile__role="admin")


def _name(user):
    return user.get_full_name() or user.username


def _notify(recipients, req, kind, title, body, path, http_request, mail_lines=None):
    """Bell entry + e-mail for every recipient."""
    recipients = [u for u in recipients if u.is_active]
    if not recipients:
        return
    Notification.objects.bulk_create(
        Notification(
            recipient=u, request=req, kind=kind, title=title, body=body[:500], url=path
        )
        for u in recipients
    )
    link = absolute_url(path, http_request)
    lines = ["Bonjour,", "", body]
    lines += list(mail_lines or [])
    if link:
        lines += ["", f"Consulter : {link}"]
    lines += ["", "— Notification automatique, merci de ne pas répondre à cet e-mail."]
    send_emails(recipients, f"[ISI] {title}", lines)


def _details(req):
    out = []
    if req.kind == R.KIND_CREATE and req.proposed_code:
        out.append(f"Code proposé : {req.proposed_code}")
    if req.message:
        out += ["Motif / détails :", req.message]
    return out


def _request_path(req):
    return reverse("approvals:request_detail", kwargs={"pk": req.pk})


def _clear_admin_inbox(req):
    """Once someone answered, the 'new request' bell entries of every admin are
    obsolete — mark them read so nobody chases an already-handled request."""
    Notification.objects.filter(
        request=req, kind=N.KIND_NEW_REQUEST, is_read=False
    ).update(is_read=True, read_at=timezone.now())


def _claim(req, from_status, **fields):
    """Atomically move ``req`` out of ``from_status``; False if someone else won."""
    updated = R.objects.filter(pk=req.pk, status=from_status).update(**fields)
    if updated:
        req.refresh_from_db()
    return bool(updated)


# ── submit ─────────────────────────────────────────────────────────────────
@transaction.atomic
def submit_request(
    requester,
    kind,
    *,
    formation=None,
    proposed_title="",
    proposed_code="",
    message="",
    http_request=None,
):
    from formations.models import Formation

    proposed_title = proposed_title.strip()
    proposed_code = proposed_code.strip()
    message = message.strip()

    if kind == R.KIND_CREATE:
        if not proposed_title:
            raise ApprovalError("Le titre de la formation est requis.")
        if proposed_code and Formation.objects.filter(code__iexact=proposed_code).exists():
            raise ApprovalError(f"Le code « {proposed_code} » existe déjà dans le catalogue.")
        if R.objects.filter(
            requester=requester,
            kind=R.KIND_CREATE,
            status=R.STATUS_PENDING,
            proposed_title__iexact=proposed_title,
        ).exists():
            raise ApprovalError("Une demande identique est déjà en attente.")
        req = R.objects.create(
            requester=requester,
            kind=kind,
            proposed_title=proposed_title,
            proposed_code=proposed_code,
            message=message,
        )
        headline = f"Demande de création de formation : « {req.proposed_title} »"
    elif kind == R.KIND_EDIT:
        if formation is None:
            raise ApprovalError("Formation introuvable.")
        if R.open_edit_request(requester, formation):
            raise ApprovalError("Une demande de modification est déjà en attente pour cette formation.")
        if R.usable_edit_grant(requester, formation):
            raise ApprovalError("Vous avez déjà l'autorisation de modifier cette formation.")
        req = R.objects.create(
            requester=requester,
            kind=kind,
            formation=formation,
            formation_label=str(formation)[:255],
            message=message,
        )
        headline = f"Demande de modification de la formation « {formation} »"
    else:
        raise ApprovalError("Type de demande inconnu.")

    _notify(
        admins().exclude(pk=requester.pk),
        req,
        N.KIND_NEW_REQUEST,
        "Nouvelle demande d'approbation",
        f"{_name(requester)} — {headline}.",
        _request_path(req),
        http_request,
        _details(req),
    )
    return req


# ── admin decisions ────────────────────────────────────────────────────────
@transaction.atomic
def approve_edit(req, admin_user, note="", http_request=None):
    if req.kind != R.KIND_EDIT:
        raise ApprovalError("Seule une demande de modification peut être approuvée.")
    if not _claim(
        req,
        R.STATUS_PENDING,
        status=R.STATUS_APPROVED,
        reviewed_by=admin_user,
        reviewed_at=timezone.now(),
        review_note=note.strip(),
    ):
        raise ApprovalError("Cette demande a déjà été traitée.")
    _clear_admin_inbox(req)
    if req.formation_id:
        path = reverse("formations:formation_edit", kwargs={"pk": req.formation_id})
    else:
        path = _request_path(req)
    hours = int(req.expires_at.timestamp() - req.reviewed_at.timestamp()) // 3600
    extra = [f"Message de l'administrateur : {req.review_note}"] if req.review_note else []
    extra.append(f"L'autorisation est valable {hours} h, jusqu'à l'enregistrement de la modification.")
    _notify(
        [req.requester],
        req,
        N.KIND_APPROVED,
        "Demande de modification approuvée",
        f"{_name(admin_user)} a approuvé votre demande de modification de « {req.subject} ». "
        "Vous pouvez maintenant ouvrir le formulaire de modification.",
        path,
        http_request,
        extra,
    )
    return req


@transaction.atomic
def reject(req, admin_user, note="", http_request=None):
    if not _claim(
        req,
        R.STATUS_PENDING,
        status=R.STATUS_REJECTED,
        reviewed_by=admin_user,
        reviewed_at=timezone.now(),
        review_note=note.strip(),
    ):
        raise ApprovalError("Cette demande a déjà été traitée.")
    _clear_admin_inbox(req)
    extra = [f"Motif du refus : {req.review_note}"] if req.review_note else []
    _notify(
        [req.requester],
        req,
        N.KIND_REJECTED,
        "Demande refusée",
        f"{_name(admin_user)} a refusé votre {req.get_kind_display().lower()} « {req.subject} ».",
        _request_path(req),
        http_request,
        extra,
    )
    return req


@transaction.atomic
def fulfill_create(req, admin_user, formation, http_request=None):
    """The admin created the formation in place of the agent."""
    if req.kind != R.KIND_CREATE:
        raise ApprovalError("Cette demande n'est pas une demande de création.")
    now = timezone.now()
    if not _claim(
        req,
        R.STATUS_PENDING,
        status=R.STATUS_FULFILLED,
        reviewed_by=admin_user,
        reviewed_at=now,
        fulfilled_at=now,
        created_formation=formation,
    ):
        raise ApprovalError("Cette demande a déjà été traitée.")
    _clear_admin_inbox(req)
    _notify(
        [req.requester],
        req,
        N.KIND_FULFILLED,
        "Formation créée",
        f"{_name(admin_user)} a créé la formation « {formation} » suite à votre demande.",
        reverse("formations:formation_detail", kwargs={"pk": formation.pk}),
        http_request,
    )
    return req


# ── agent side ─────────────────────────────────────────────────────────────
@transaction.atomic
def complete_edit(req, http_request=None):
    """Called after the agent saved the edit form: the grant is consumed."""
    now = timezone.now()
    if not _claim(req, R.STATUS_APPROVED, status=R.STATUS_FULFILLED, fulfilled_at=now):
        return req
    _notify(
        admins().exclude(pk=req.requester_id),
        req,
        N.KIND_EDIT_DONE,
        "Modification effectuée",
        f"{_name(req.requester)} a modifié la formation « {req.subject} » (demande approuvée).",
        reverse("formations:formation_detail", kwargs={"pk": req.formation_id})
        if req.formation_id
        else _request_path(req),
        http_request,
    )
    return req


@transaction.atomic
def cancel(req, user, http_request=None):
    if req.requester_id != user.pk:
        raise ApprovalError("Vous ne pouvez annuler que vos propres demandes.")
    if not _claim(req, R.STATUS_PENDING, status=R.STATUS_CANCELLED):
        raise ApprovalError("Cette demande n'est plus en attente.")
    _clear_admin_inbox(req)
    _notify(
        admins().exclude(pk=user.pk),
        req,
        N.KIND_CANCELLED,
        "Demande annulée",
        f"{_name(user)} a annulé sa {req.get_kind_display().lower()} « {req.subject} ».",
        _request_path(req),
        http_request,
    )
    return req
