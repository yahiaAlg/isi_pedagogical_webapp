from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from formations.models import Formation

from . import services
from .context_processors import BELL_SIZE
from .models import ApprovalRequest, Notification
from .services import ApprovalError

R = ApprovalRequest


def _is_admin(user):
    return user.profile.is_admin()


def _is_agent(user):
    return user.profile.is_pedagogical()


def _deny(request, msg="Accès non autorisé."):
    messages.error(request, msg)
    return redirect("core:dashboard")


# ===========================================================================
# Requests
# ===========================================================================


@login_required
def request_list(request):
    """Admin: every request (inbox). Agent: own requests."""
    user = request.user
    if not (_is_admin(user) or _is_agent(user)):
        return _deny(request)

    qs = R.objects.select_related("requester", "formation", "reviewed_by")
    if not _is_admin(user):
        qs = qs.filter(requester=user)

    status = request.GET.get("status", "pending" if _is_admin(user) else "")
    if status in dict(R.STATUS_CHOICES):
        qs = qs.filter(status=status)
    else:
        status = ""
    kind = request.GET.get("kind", "")
    if kind in dict(R.KIND_CHOICES):
        qs = qs.filter(kind=kind)
    else:
        kind = ""

    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "approvals/request_list.html",
        {
            "page_obj": page_obj,
            "status": status,
            "kind": kind,
            "status_choices": R.STATUS_CHOICES,
            "kind_choices": R.KIND_CHOICES,
            "is_admin_view": _is_admin(user),
        },
    )


@login_required
def request_detail(request, pk):
    req = get_object_or_404(
        R.objects.select_related("requester", "formation", "reviewed_by", "created_formation"),
        pk=pk,
    )
    if not (_is_admin(request.user) or req.requester_id == request.user.pk):
        return _deny(request)
    return render(
        request,
        "approvals/request_detail.html",
        {
            "req": req,
            "is_admin_view": _is_admin(request.user),
            "is_owner": req.requester_id == request.user.pk,
        },
    )


@login_required
def request_formation_create(request):
    """Agent asks the admin to create a formation in the catalogue."""
    if _is_admin(request.user):
        return redirect("formations:formation_create")
    if not _is_agent(request.user):
        return _deny(request)

    data = request.POST if request.method == "POST" else None
    if request.method == "POST":
        try:
            req = services.submit_request(
                request.user,
                R.KIND_CREATE,
                proposed_title=request.POST.get("title", ""),
                proposed_code=request.POST.get("code", ""),
                message=request.POST.get("message", ""),
                http_request=request,
            )
        except ApprovalError as e:
            messages.error(request, str(e))
        else:
            messages.success(
                request, "Demande envoyée aux administrateurs. Vous serez notifié de la suite."
            )
            return redirect("approvals:request_detail", pk=req.pk)
    return render(request, "approvals/request_formation_create.html", {"data": data})


@login_required
@require_POST
def request_formation_edit(request, formation_pk):
    """Agent asks the admin's approval to open a formation's edit form."""
    formation = get_object_or_404(Formation, pk=formation_pk)
    if not _is_agent(request.user):
        return _deny(request)
    try:
        services.submit_request(
            request.user,
            R.KIND_EDIT,
            formation=formation,
            message=request.POST.get("message", ""),
            http_request=request,
        )
    except ApprovalError as e:
        messages.error(request, str(e))
    else:
        messages.success(
            request, "Demande de modification envoyée. Vous serez notifié de la décision."
        )
    return redirect("formations:formation_detail", pk=formation.pk)


@login_required
@require_POST
def request_approve(request, pk):
    if not _is_admin(request.user):
        return _deny(request, "Accès réservé aux administrateurs.")
    req = get_object_or_404(R, pk=pk)
    try:
        services.approve_edit(req, request.user, request.POST.get("note", ""), request)
    except ApprovalError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Demande approuvée — l'agent a été notifié.")
    return redirect("approvals:request_detail", pk=pk)


@login_required
@require_POST
def request_reject(request, pk):
    if not _is_admin(request.user):
        return _deny(request, "Accès réservé aux administrateurs.")
    req = get_object_or_404(R, pk=pk)
    try:
        services.reject(req, request.user, request.POST.get("note", ""), request)
    except ApprovalError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Demande refusée — l'agent a été notifié.")
    return redirect("approvals:request_detail", pk=pk)


@login_required
@require_POST
def request_cancel(request, pk):
    req = get_object_or_404(R, pk=pk)
    try:
        services.cancel(req, request.user, request)
    except ApprovalError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Demande annulée.")
    return redirect("approvals:request_detail", pk=pk)


# ===========================================================================
# Bell
# ===========================================================================


def _bell_payload(request):
    qs = Notification.objects.filter(recipient=request.user)
    items = list(qs[:BELL_SIZE])
    return {
        "count": qs.filter(is_read=False).count(),
        "html": render_to_string(
            "approvals/_bell_items.html", {"bell_items": items}, request=request
        ),
    }


@login_required
@require_GET
def notification_feed(request):
    """Polled by base JS: unread counter + rendered dropdown list."""
    return JsonResponse(_bell_payload(request))


@login_required
@require_POST
def notification_read_all(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(_bell_payload(request))
    return redirect("approvals:notification_list")


@login_required
@require_GET
def notification_open(request, pk):
    """Mark one notification read, then go where it points."""
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.read_at = timezone.now()
        notif.save(update_fields=["is_read", "read_at"])
    target = notif.url
    if not target or not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}
    ):
        target = reverse("approvals:notification_list")
    return redirect(target)


@login_required
def notification_list(request):
    qs = Notification.objects.filter(recipient=request.user)
    only_unread = request.GET.get("unread") == "1"
    if only_unread:
        qs = qs.filter(is_read=False)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "approvals/notification_list.html",
        {"page_obj": page_obj, "only_unread": only_unread},
    )
