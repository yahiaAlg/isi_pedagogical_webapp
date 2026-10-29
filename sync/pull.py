"""Website -> ISI: new clients, their participants, and roster updates."""

import logging
import re
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from clients.models import Client

from . import transport
from .models import RemoteClient, RosterEntry, SyncState
from .seeding import (
    PARTICIPANT_FIELDS,
    participant_is_pristine,
    resolve_formation,
    seed_client,
)

log = logging.getLogger(__name__)
CURSOR_KEY = "feed_cursor"
LAST_PULL_KEY = "last_pull"
ARABIC = re.compile(r"[\u0600-\u06FF]")


def particuliers_name():
    return getattr(settings, "SYNC_PARTICULIERS_CLIENT_NAME", "Particuliers")


def get_particuliers_client():
    """The shared 'Particuliers' client every website individual is filed under."""
    client = Client.objects.filter(name__iexact=particuliers_name()).first()
    if client is None:
        client = Client.objects.create(
            name=particuliers_name(), name_ar="أفراد", address="Sétif", city="Sétif", is_active=True
        )
    return client


def split_name(full_name):
    """'Mohamed Amine Benali' -> first='Mohamed Amine', last='Benali' (prénom(s) + nom).
    Arabic script fills the AR pair. Returns {} when a full name can't be derived."""
    tokens = (full_name or "").split()
    if len(tokens) < 2:
        return {}
    first, last = " ".join(tokens[:-1])[:50], tokens[-1][:50]
    if ARABIC.search(full_name):
        return {"first_name_ar": first, "last_name_ar": last}
    return {"first_name": first, "last_name": last}


# --------------------------------------------------------------------- clients
def _enterprise_values(s):
    city = (s.get("city") or s.get("wilaya") or "").strip()
    return {
        "name": (s.get("company_name") or "").strip()[:200],
        "address": (s.get("address") or city or "-").strip(),
        "city": city[:100],
        "phone": (s.get("phone") or "")[:20],
        "email": s.get("email") or "",
        "contact_person": ((s.get("responsible_name") or s.get("main_contact_name") or ""))[:100],
        "nif": (s.get("nif") or "")[:20],
        "nis": (s.get("nis") or "")[:20],
        "rc": (s.get("trade_register_number") or "")[:20],
    }


def _find_existing_client(values):
    q = Q()
    for field in ("rc", "nif"):
        if values[field]:
            q |= Q(**{f"{field}__iexact": values[field]})
    hit = Client.objects.filter(q).first() if q else None
    return hit or Client.objects.filter(name__iexact=values["name"]).first()


def _resolve_enterprise_client(snap, remote):
    values = _enterprise_values(snap)
    client = remote.client if remote else None
    if client is None:
        client = _find_existing_client(values)
        if client:  # adopt: only fill what ISI has blank
            changed = []
            for f, v in values.items():
                if v and not (getattr(client, f) or "").strip():
                    setattr(client, f, v)
                    changed.append(f)
            if changed:
                client.save()
            return client, False
        return Client.objects.create(is_active=True, **values), True
    # known client: apply only what the website changed since last time
    old = _enterprise_values(remote.last_snapshot) if remote.last_snapshot else {}
    changed = [f for f, v in values.items() if old.get(f) != v and v]
    for f in changed:
        setattr(client, f, values[f])
    if changed:
        client.save()
    return client, remote.created_client


def _apply_tombstone(ext_id, remote):
    """Website client removed / no longer active: drop its not-yet-used roster;
    never delete the ISI client itself (it may carry sessions and history)."""
    if remote is None:
        return {"ext_id": ext_id, "action": "ignored"}
    _reconcile_roster(remote.client, {"roster": []}, remote)
    if remote.client and remote.created_client and not remote.is_individual:
        if not remote.client.session_set.exists():
            remote.client.is_active = False
            remote.client.save(update_fields=["is_active", "updated_at"])
    remote.last_snapshot = {}
    remote.save()
    return {"ext_id": ext_id, "action": "deactivated"}


# ---------------------------------------------------------------------- roster
def _line_values(line):
    v = {f: line.get(f) or "" for f in PARTICIPANT_FIELDS if f != "date_of_birth"}
    v.update(split_name(line["full_name"]) if line.get("full_name") else {})
    dob = line.get("date_of_birth")
    v["date_of_birth"] = dob or None  # ISO string kept as-is for diffing
    for f, n in (("first_name", 50), ("last_name", 50), ("first_name_ar", 50), ("last_name_ar", 50),
                 ("place_of_birth", 100), ("place_of_birth_ar", 100), ("job_title", 100),
                 ("employer", 200), ("phone", 20)):
        v[f] = (v.get(f) or "")[:n]
    v["gender"] = (v.get("gender") or "")[:1]
    return v


def _to_date(iso):
    try:
        return date.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def _apply_line(entry, client, line, ext_client_id):
    new = _line_values(line)
    old = entry.last_values or {}
    changed = {k: v for k, v in new.items() if old.get(k) != v}

    entry.client, entry.remote_client_ext_id = client, ext_client_id
    entry.enrollment_status = line.get("enrollment_status", "")
    ref = line.get("offering") or {}
    entry.offering_ref = ref
    entry.offering_code, entry.offering_title = (ref.get("code") or "")[:30], (ref.get("title") or "")[:200]
    entry.formation = resolve_formation(ref)
    for f, v in new.items():
        setattr(entry, f, _to_date(v) if f == "date_of_birth" else v)
    entry.last_values = new
    entry.removed_on_site = False          # (re)appeared on the website roster
    entry.note = "" if entry.has_complete_name else "Nom complet (prénom + nom) requis"
    entry.save()

    # propagate to the session participant, but only fields the website changed
    p = entry.participant
    if p is not None and changed and p.session.status in ("planned", "in_progress"):
        for f, v in changed.items():
            setattr(p, f, _to_date(v) if f == "date_of_birth" else v)
        try:
            with transaction.atomic():
                p.save()
        except Exception as exc:  # e.g. new name collides with another participant
            entry.note = f"Mise à jour non appliquée : {exc}"[:200]
            entry.save(update_fields=["note", "updated_at"])


def _remove_entry(entry):
    """The website dropped this person. Never destroy pedagogical records: a person
    with no session, or a pristine one in a still-planned session, is removed; anyone
    else (marks, certificate, session started/finished) is KEPT and flagged
    'Retiré du site' so staff can decide."""
    p = entry.participant
    if p is None:
        entry.delete()
        return "deleted"
    still_used = RosterEntry.objects.filter(participant=p).exclude(pk=entry.pk).exists()
    if still_used or participant_is_pristine(p):
        entry.delete()
        if not still_used:
            p.copies.all().delete()
            p.delete()
        return "deleted"
    if not entry.removed_on_site:
        entry.removed_on_site = True
        entry.note = "Retiré de la liste sur le site — participant conservé (notes ou session commencée)"
        entry.save(update_fields=["removed_on_site", "note", "updated_at"])
    return "kept"


def _reconcile_roster(client, snap, remote):
    ext = remote.ext_id
    existing = {e.ext_id: e for e in RosterEntry.objects.filter(remote_client_ext_id=ext)}
    seen = set()
    if client is not None:
        for line in snap.get("roster", []):
            seen.add(line["ext_id"])
            entry = existing.get(line["ext_id"]) or RosterEntry(ext_id=line["ext_id"])
            _apply_line(entry, client, line, ext)
    if client is not None:
        seed_client(client)  # before removals, so a re-keyed person is re-linked, not dropped
    for ext_id, entry in existing.items():
        if ext_id not in seen:
            _remove_entry(entry)


@transaction.atomic
def apply_snapshot(snap):
    ext = snap["ext_id"]
    remote = RemoteClient.objects.filter(ext_id=ext).first()
    if snap.get("deleted"):
        return _apply_tombstone(ext, remote)

    individual = snap.get("type") == "individual"
    if remote is None:
        remote = RemoteClient(ext_id=ext, is_individual=individual)
    if individual:
        client, created = get_particuliers_client(), False
    else:
        client, created = _resolve_enterprise_client(snap, remote if remote.pk else None)
    if individual:
        action = "individual"
    elif remote.pk is None:
        action = "created" if created else "linked"
    else:
        action = "updated"
    remote.client, remote.created_client = client, created
    remote.save()
    _reconcile_roster(client, snap, remote)
    remote.last_snapshot = {k: v for k, v in snap.items() if k != "roster"}
    remote.save()
    return {"ext_id": ext, "action": action, "roster": len(snap.get("roster", []))}


# ------------------------------------------------------------------------ pull
BASELINE_KEY = "baseline_client_id"
LAST_FULL_KEY = "last_full"


def _now_iso():
    return timezone.now().isoformat()


def pull(full=False, backfill=False, repair=False, page_size=50):
    """Fetch and apply website changes. Returns a summary dict.

    * default (events): clients changed after the stored cursor. The very first run
      starts at the feed's current head and records a *baseline* (highest website client
      id), so clients that already existed are NOT flooded in — unless
      SYNC_INITIAL_BACKFILL=1 or backfill=True.
    * full / backfill: walk EVERY website client and import all of them (matched to existing
      ISI clients by RC, NIF, then name).
    * repair: walk every website client but only apply those ISI already knows or that were
      created after the baseline (heals missed events without importing old clients).
    """
    summary = {"applied": 0, "skipped": 0, "errors": [], "actions": {}}
    SyncState.put("last_errors", "")
    cursor_raw = SyncState.get(CURSOR_KEY, "")
    first_run = cursor_raw == ""
    import_existing = bool(
        full or backfill or (first_run and getattr(settings, "SYNC_INITIAL_BACKFILL", False))
    )
    walk = import_existing or (repair and not first_run)

    def _wanted(snap):
        if import_existing or RemoteClient.objects.filter(ext_id=snap["ext_id"]).exists():
            return True
        baseline = SyncState.get(BASELINE_KEY, "")
        return baseline != "" and snap["ext_id"] > int(baseline)

    def _apply(snaps, filter_unknown=False):
        for snap in snaps:
            if filter_unknown and not _wanted(snap):
                summary["skipped"] += 1
                continue
            try:
                res = apply_snapshot(snap)
                summary["applied"] += 1
                summary["actions"][res["action"]] = summary["actions"].get(res["action"], 0) + 1
            except Exception as exc:
                log.exception("sync: client %s failed", snap.get("ext_id"))
                summary["errors"].append(f"client {snap.get('ext_id')}: {exc}")

    head = None
    if first_run:
        head = transport.call("GET", "feed/", {"mode": "head"})   # captured BEFORE any walk
        if not walk:
            SyncState.put(CURSOR_KEY, head["cursor"])
            SyncState.put(BASELINE_KEY, head.get("max_client_id", 0))
            SyncState.put(LAST_FULL_KEY, _now_iso())
            SyncState.put(LAST_PULL_KEY, _now_iso())
            summary["initialised_at"] = head["cursor"]
            return summary

    if walk:
        after = 0
        while True:
            data = transport.call("GET", "feed/", {"mode": "full", "after_id": after, "limit": page_size})
            _apply(data["clients"], filter_unknown=not import_existing)
            after = data["after_id"]
            if not data["has_more"]:
                break
        SyncState.put(LAST_FULL_KEY, _now_iso())
        if first_run:
            SyncState.put(CURSOR_KEY, head["cursor"])
            SyncState.put(BASELINE_KEY, 0)          # everything was imported: no baseline gap
    else:
        cursor = int(cursor_raw)
        while True:
            data = transport.call("GET", "feed/", {"cursor": cursor, "limit": page_size})
            _apply(data["clients"])
            cursor = data["cursor"]
            SyncState.put(CURSOR_KEY, cursor)
            if not data["has_more"]:
                break
    SyncState.put(LAST_PULL_KEY, _now_iso())
    SyncState.put("last_errors", "\n".join(summary["errors"][:20]))
    return summary


def pull_auto(page_size=50):
    """What cron / "Synchroniser maintenant" run: the cheap events pull, plus — at most every
    SYNC_AUTO_FULL_HOURS — a repair walk that re-checks every known client so a missed
    change (bulk update, restored backup…) heals itself."""
    summary = pull(page_size=page_size)
    hours = getattr(settings, "SYNC_AUTO_FULL_HOURS", 24)
    last = parse_datetime(SyncState.get(LAST_FULL_KEY, "") or "")
    due = hours and "initialised_at" not in summary and (
        last is None or timezone.now() - last > timedelta(hours=hours)
    )
    if due:
        fix = pull(repair=True, page_size=page_size)
        summary["applied"] += fix["applied"]
        summary["errors"] += fix["errors"]
        summary["repaired"] = fix["applied"]
        for k, v in fix["actions"].items():
            summary["actions"][k] = summary["actions"].get(k, 0) + v
    return summary
