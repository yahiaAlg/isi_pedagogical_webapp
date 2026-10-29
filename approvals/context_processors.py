from .models import ApprovalRequest, Notification

BELL_SIZE = 8


def bell(request):
    """Data for the topbar bell + sidebar badge (authenticated pages only)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    qs = Notification.objects.filter(recipient=user)
    ctx = {
        "bell_unread": qs.filter(is_read=False).count(),
        "bell_items": list(qs[:BELL_SIZE]),
    }
    profile = getattr(user, "profile", None)
    if profile is not None and profile.is_admin():
        ctx["pending_requests_count"] = ApprovalRequest.objects.filter(
            status=ApprovalRequest.STATUS_PENDING
        ).count()
    return ctx
