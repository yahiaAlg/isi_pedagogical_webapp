"""RosterEntry (website people) -> formations.Participant (people in a Session)."""

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q

from formations.models import Formation, Participant, Session

from .models import RosterEntry

UNVALIDATED_STATUSES = ("pending", "contacted")


def seedable_statuses(include_pending=False):
    """Website enrollment statuses that may enter a session (SYNC_SEED_STATUSES);
    include_pending=True (manual "+ non validés" button) also lets pending/contacted in."""
    base = tuple(
        x.strip() for x in str(getattr(settings, "SYNC_SEED_STATUSES", "accepted,confirmed")).split(",") if x.strip()
    )
    return tuple(dict.fromkeys(base + (UNVALIDATED_STATUSES if include_pending else ())))
# Participant fields mirrored from the website identity (employer_client is set separately)
PARTICIPANT_FIELDS = RosterEntry.IDENTITY_FIELDS


def resolve_formation(ref):
    """Find the ISI Formation for a website offering reference."""
    if not ref:
        return None
    if ref.get("isi_formation_id"):
        f = Formation.objects.filter(pk=ref["isi_formation_id"]).first()
        if f:
            return f
    code = (ref.get("code") or "").strip()
    titles = [t for t in (ref.get("title"),) if t]
    if code:
        qs = Formation.objects.filter(Q(website_code=code) | Q(code=code))
        if qs.count() == 1:
            return qs.first()
        for t in titles:
            hit = qs.filter(Q(title__iexact=t) | Q(title_ar__iexact=t)).first()
            if hit:
                return hit
    for t in titles:
        hit = Formation.objects.filter(Q(title__iexact=t) | Q(title_ar__iexact=t)).first()
        if hit:
            return hit
    return None


def _is_individuals_client(client):
    from .pull import particuliers_name

    return (client.name or "").strip().lower() == particuliers_name().lower()


def candidate_sessions(client, formation):
    """Planned primary sessions of this client for this formation, soonest first."""
    return (
        Session.objects.filter(client=client, formation=formation, status="planned", parent_session__isnull=True)
        .order_by("date_start", "pk")
    )


def _participant_values(entry):
    return {f: getattr(entry, f) for f in PARTICIPANT_FIELDS}


def seed_entry(entry, session=None, include_pending=False):
    """Put one entry into a session. Returns 'seeded' | 'linked' | 'skipped'.
    Never raises on data problems — it records why in entry.note."""
    if entry.participant_id:
        return "linked"
    if entry.removed_on_site or entry.enrollment_status not in seedable_statuses(include_pending):
        return "skipped"
    if not entry.has_complete_name:
        _note(entry, "Nom complet (prénom + nom) requis pour créer le participant")
        return "skipped"
    if not entry.formation_id:
        _note(entry, "Formation introuvable dans l'application pédagogique")
        return "skipped"

    if session is None:
        session = next((s for s in candidate_sessions(entry.client, entry.formation) if s.can_add_participants()), None)
        if session is None:
            _note(entry, "En attente d'une session planifiée avec des places disponibles")
            return "skipped"

    existing = Participant.objects.filter(
        session=session, first_name=entry.first_name, last_name=entry.last_name
    ).first()
    if existing:
        entry.participant, entry.note = existing, ""
        entry.save(update_fields=["participant", "note", "updated_at"])
        return "linked"
    if not session.can_add_participants():
        _note(entry, "Session complète ou non modifiable")
        return "skipped"

    values = _participant_values(entry)
    individual = _is_individuals_client(entry.client)
    try:
        with transaction.atomic():
            participant = Participant.objects.create(
                session=session,
                employer_client=None if individual else entry.client,
                attended=True,
                **values,
            )
    except IntegrityError:
        _note(entry, "Doublon (même nom) dans la session")
        return "skipped"
    entry.participant, entry.note = participant, ""
    entry.save(update_fields=["participant", "note", "updated_at"])
    return "seeded"


def _note(entry, text):
    if entry.note != text:
        entry.note = text
        entry.save(update_fields=["note", "updated_at"])


def re_resolve_formations(client):
    for entry in RosterEntry.objects.filter(client=client, formation__isnull=True):
        f = resolve_formation(entry.offering_ref)
        if f:
            entry.formation = f
            entry.save(update_fields=["formation", "updated_at"])


def seed_session(session, include_pending=False):
    """Seed every waiting entry of (session.client, session.formation) into this
    session until it is full. Returns {'seeded': n, 'linked': n, 'skipped': n}."""
    counts = {"seeded": 0, "linked": 0, "skipped": 0}
    if session.parent_session_id:
        return counts
    re_resolve_formations(session.client)
    entries = RosterEntry.objects.filter(
        client=session.client, formation=session.formation, participant__isnull=True, removed_on_site=False
    ).order_by("created_at", "pk")
    for entry in entries:
        counts[seed_entry(entry, session=session, include_pending=include_pending)] += 1
    return counts


def seed_client(client):
    """Seed waiting entries of a client into whatever planned sessions fit."""
    counts = {"seeded": 0, "linked": 0, "skipped": 0}
    re_resolve_formations(client)
    for entry in RosterEntry.objects.filter(client=client, participant__isnull=True):
        counts[seed_entry(entry)] += 1
    return counts


def participant_is_pristine(p):
    """No marks, no certificate: safe to remove if the website dropped the person."""
    return (
        p.score_theory is None and p.score_practice is None and p.exam_score is None
        and not p.certificate_number and not p.certificate_issued
        and p.session.status == "planned"
    )
