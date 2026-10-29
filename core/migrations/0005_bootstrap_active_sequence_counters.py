# Generated manually — bootstraps `is_active` on the counter that was
# implicitly "current" before this field existed (today's calendar
# month for "pv", today's calendar year for "certificate" /
# "mission_order"), so existing installs keep numbering exactly where
# they left off. From here on an admin can pin a different period via
# the "Définir comme période active" action; until they do, this
# bootstrapped row stays authoritative.

from django.db import migrations
from django.utils import timezone


def bootstrap_active_periods(apps, schema_editor):
    SequenceCounter = apps.get_model('core', 'SequenceCounter')
    today = timezone.localdate()

    for kind in ('pv', 'certificate', 'mission_order'):
        if kind == 'pv':
            period_key = f"{today.year:04d}-{today.month:02d}"
        else:
            period_key = f"{today.year:04d}"

        # Nothing to bootstrap if this kind was never used yet — it'll be
        # created and activated lazily on first access
        # (SequenceCounter.get_active_period_key).
        if not SequenceCounter.objects.filter(kind=kind).exists():
            continue

        counter, _ = SequenceCounter.objects.get_or_create(
            kind=kind, period_key=period_key
        )
        if not counter.is_active:
            SequenceCounter.objects.filter(kind=kind).update(is_active=False)
            counter.is_active = True
            counter.save(update_fields=['is_active'])


def noop_reverse(apps, schema_editor):
    # Reversing just clears the pin — nothing else depended on it before
    # this migration existed.
    SequenceCounter = apps.get_model('core', 'SequenceCounter')
    SequenceCounter.objects.update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_sequencecounter_is_active'),
    ]

    operations = [
        migrations.RunPython(bootstrap_active_periods, noop_reverse),
    ]
