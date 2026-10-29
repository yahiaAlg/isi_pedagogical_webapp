from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from formations.models import Formation, Session

from .push import enqueue_formation, enqueue_formation_deleted, flush_in_background
from .seeding import seed_session


@receiver(post_save, sender=Formation)
def formation_saved(sender, instance, raw=False, **kwargs):
    """A formation was created/edited -> queue it for the website and try to
    send it right away (in the background; cron retries on failure)."""
    if raw:  # loaddata
        return
    enqueue_formation(instance.pk)
    transaction.on_commit(flush_in_background)


@receiver(post_delete, sender=Formation)
def formation_deleted(sender, instance, **kwargs):
    """Deleted here -> the website hides the matching offering (kept for its enrollments)."""
    enqueue_formation_deleted(instance.pk)
    transaction.on_commit(flush_in_background)


@receiver(post_save, sender=Session)
def session_created(sender, instance, created, raw=False, **kwargs):
    """A new session for a client/formation: fill it with the participants the
    website already announced for that pair."""
    if raw or not created or instance.parent_session_id:
        return
    transaction.on_commit(lambda: seed_session(instance))
