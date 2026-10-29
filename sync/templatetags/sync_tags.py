from django import template

from sync.models import RosterEntry
from sync.seeding import UNVALIDATED_STATUSES, seedable_statuses

register = template.Library()

STATE_LABELS = {
    "seeded": ("green", "Ajouté à une session"),
    "pending": ("amber", "En attente d'une session"),
    "awaiting_validation": ("gray", "Inscription non validée"),
    "removed": ("red", "Retiré du site — à vérifier"),
}


@register.simple_tag
def roster_for_client(client):
    """Website participants announced for this client (for the client page)."""
    entries = list(
        RosterEntry.objects.filter(client=client)
        .select_related("formation", "participant__session")
        .order_by("offering_title", "last_name", "first_name")
    )
    for e in entries:
        e.badge, e.badge_label = STATE_LABELS[e.state]
    return entries


@register.simple_tag
def waiting_roster_count(session):
    """Website participants ready to be added to this session."""
    if session.parent_session_id:
        return 0
    return RosterEntry.objects.filter(
        client_id=session.client_id,
        formation_id=session.formation_id,
        participant__isnull=True,
        removed_on_site=False,
        enrollment_status__in=seedable_statuses(),
    ).count()


@register.simple_tag
def waiting_unvalidated_count(session):
    """Website people with a not-yet-validated enrollment (pending/contacted) for this session."""
    if session.parent_session_id:
        return 0
    return RosterEntry.objects.filter(
        client_id=session.client_id,
        formation_id=session.formation_id,
        participant__isnull=True,
        removed_on_site=False,
        enrollment_status__in=[s for s in UNVALIDATED_STATUSES if s not in seedable_statuses()],
    ).count()
