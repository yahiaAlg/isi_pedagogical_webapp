"""
manage.py sync_main_site

Two-way sync with the main website. Run from cron every 2-5 minutes:

    */3 * * * * cd /path/to/isi_pedagogical_webapp && venv/bin/python manage.py sync_main_site >> logs/sync.log 2>&1

  push : formations created/edited here -> website offerings (+ fiche technique)
  pull : new/updated website clients and their participants -> clients + roster

Options
  --push-only / --pull-only
  --full       walk EVERY website client and import all of them (one-off import of existing ones)
  --backfill   same as --full (also valid on a first run)
  --repair     walk every website client but only apply ones ISI knows / created after the first sync
(plain runs already do a --repair walk automatically every SYNC_AUTO_FULL_HOURS, default 24 h)
"""

from django.core.management.base import BaseCommand, CommandError

from sync import transport
from sync.pull import pull, pull_auto
from sync.push import flush_jobs


class Command(BaseCommand):
    help = "Two-way sync with the main website (formations out, clients/participants in)."

    def add_arguments(self, parser):
        parser.add_argument("--push-only", action="store_true")
        parser.add_argument("--pull-only", action="store_true")
        parser.add_argument("--full", action="store_true")
        parser.add_argument("--backfill", action="store_true")
        parser.add_argument("--repair", action="store_true")

    def handle(self, *args, **opts):
        if not transport.is_configured():
            raise CommandError("SYNC_SHARED_SECRET (ou INSTITUTE_PING_SECRET) n'est pas défini.")
        if not opts["pull_only"]:
            sent, left = flush_jobs()
            self.stdout.write(f"push: {sent} formation(s) envoyée(s), {left} en attente")
        if not opts["push_only"]:
            try:
                if opts["full"] or opts["backfill"] or opts["repair"]:
                    s = pull(full=opts["full"], backfill=opts["backfill"], repair=opts["repair"])
                else:
                    s = pull_auto()
            except transport.SyncError as exc:
                raise CommandError(str(exc))
            if "initialised_at" in s:
                self.stdout.write(f"pull: curseur initialisé (événement {s['initialised_at']}); "
                                  "les prochains clients du site seront importés.")
            else:
                self.stdout.write(f"pull: {s['applied']} client(s) traité(s) {s['actions']}")
            for err in s["errors"]:
                self.stderr.write(self.style.WARNING(f"  ! {err}"))
