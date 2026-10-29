"""ISI Formation -> website Offering (outbox + immediate best-effort flush)."""

import logging
import threading

from django.conf import settings
from django.db import close_old_connections

from . import transport
from .fiche import generate_fiche
from .models import SyncJob

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 20
_flush_lock = threading.Lock()


def formation_payload(f):
    spec = f.specialty if f.specialty_id else None
    return {
        "isi_formation_id": f.pk,
        "code": f.code,
        "website_code": f.website_code or f.code,
        "title": f.title,
        "title_ar": f.title_ar,
        "category": f.category.name if f.category_id else "",
        "specialty": (
            {
                "branch_abbr": spec.branch.abbreviation,
                "branch_name": spec.branch.name,
                "branch_name_ar": spec.branch.name_ar,
                "code": spec.code,
                "title": spec.title,
                "title_ar": spec.title_ar,
            }
            if spec
            else None
        ),
        "attestation_type": f.attestation_type,
        "duration_days": f.duration_days,
        "duration_hours": f.duration_hours,
        "min_participants": f.min_participants,
        "max_participants": f.max_participants,
        "evaluation_type": f.evaluation_type,
        "produces_certificate": f.produces_certificate,
        "is_active": f.is_active,
        "fiche": generate_fiche(f),
    }


def enqueue_formation(formation_id):
    job = SyncJob.objects.filter(
        kind=SyncJob.KIND_FORMATION, object_id=formation_id, status=SyncJob.PENDING
    ).first()
    if job is None:
        job = SyncJob.objects.create(kind=SyncJob.KIND_FORMATION, object_id=formation_id)
    return job


def enqueue_formation_deleted(formation_id):
    """A formation was deleted here: tell the website to hide (never delete) its offering.
    Any still-pending upsert for it is obsolete."""
    SyncJob.objects.filter(
        kind=SyncJob.KIND_FORMATION, object_id=formation_id, status=SyncJob.PENDING
    ).update(status=SyncJob.DONE, last_error="remplacé par une suppression")
    job = SyncJob.objects.filter(
        kind=SyncJob.KIND_FORMATION_DELETED, object_id=formation_id, status=SyncJob.PENDING
    ).first()
    return job or SyncJob.objects.create(kind=SyncJob.KIND_FORMATION_DELETED, object_id=formation_id)


def _push_deletion(job):
    job.attempts += 1
    try:
        resp = transport.call(
            "POST", "formations/deactivate/", payload={"isi_formation_ids": [job.object_id]}
        )
        job.status, job.last_error, job.result = SyncJob.DONE, "", resp
    except transport.SyncError as exc:
        job.status = SyncJob.PENDING if job.attempts < MAX_ATTEMPTS else SyncJob.FAILED
        job.last_error = str(exc)[:1000]
    job.save()


def push_job(job):
    from formations.models import Formation

    if job.kind == SyncJob.KIND_FORMATION_DELETED:
        return _push_deletion(job)

    formation = (
        Formation.objects.select_related("category", "specialty__branch").filter(pk=job.object_id).first()
    )
    job.attempts += 1
    if formation is None:  # deleted before it was sent
        job.status, job.last_error = SyncJob.DONE, "formation supprimée"
        job.save()
        return
    if not (formation.website_code or formation.code):
        # no specialty -> no code: nothing the website can use. Fail once, visibly; saving the
        # formation again after choosing a specialty queues a fresh job.
        job.status = SyncJob.FAILED
        job.last_error = "Formation sans code (choisissez une spécialité) : non envoyée au site."
        job.save()
        return
    try:
        resp = transport.call("POST", "formations/", payload=formation_payload(formation))
        if resp.get("errors"):
            raise transport.SyncError(resp["errors"][0].get("error", "erreur inconnue"))
        job.status, job.last_error = SyncJob.DONE, ""
        job.result = (resp.get("results") or [None])[0]
    except transport.SyncError as exc:
        job.status = SyncJob.PENDING if job.attempts < MAX_ATTEMPTS else SyncJob.FAILED
        job.last_error = str(exc)[:1000]
    job.save()


def flush_jobs(limit=100):
    """Send pending jobs. Returns (sent, remaining)."""
    if not transport.is_configured():
        return 0, SyncJob.objects.filter(status=SyncJob.PENDING).count()
    sent = 0
    for job in SyncJob.objects.filter(status=SyncJob.PENDING).order_by("created_at")[:limit]:
        push_job(job)
        sent += job.status == SyncJob.DONE
        if job.status != SyncJob.DONE and "injoignable" in job.last_error:
            break  # site down: no point hammering it with the rest
    return sent, SyncJob.objects.filter(status=SyncJob.PENDING).count()


def flush_in_background():
    """Fire-and-forget flush so saving a formation never waits on the network.
    One flusher at a time; the cron command is the safety net."""
    if not getattr(settings, "SYNC_AUTOFLUSH", True) or not transport.is_configured():
        return

    def _run():
        if not _flush_lock.acquire(blocking=False):
            return
        try:
            close_old_connections()
            flush_jobs()
        except Exception:  # never let a background thread die noisily
            log.exception("background formation sync failed")
        finally:
            close_old_connections()
            _flush_lock.release()

    threading.Thread(target=_run, daemon=True, name="isi-sync-flush").start()
