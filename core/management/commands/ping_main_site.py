"""
manage.py ping_main_site

Announces this server's current PUBLIC IP to the main website so that the
attestation QR gateway (https://<main-site>/v/<code>/) can recognise visitors
on the institute's internet connection — the ISP changes that IP regularly,
so it cannot be configured statically.

Run it from cron every 5 minutes, e.g.:

    */5 * * * * cd /path/to/isi_pedagogical_webapp && venv/bin/python manage.py ping_main_site >> logs/ping.log 2>&1

Needs INSTITUTE_PING_SECRET (same value as on the main site) and MAIN_SITE_URL.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Announce this server's current public IP to the main website."

    def handle(self, *args, **options):
        secret = getattr(settings, "INSTITUTE_PING_SECRET", "")
        if not secret:
            raise CommandError("INSTITUTE_PING_SECRET is not set.")
        url = f"{settings.MAIN_SITE_URL.rstrip('/')}/internal/institute-ping/"
        req = urllib.request.Request(
            url,
            data=b"",
            method="POST",
            headers={"X-Ping-Secret": secret, "User-Agent": "isi-pedagogy-ping/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ip = json.loads(resp.read().decode()).get("ip", "?")
        except urllib.error.HTTPError as exc:
            raise CommandError(f"Main site refused the ping (HTTP {exc.code}).")
        except Exception as exc:  # network down, DNS, timeout…
            raise CommandError(f"Ping failed: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Main site now sees the institute at {ip}"))
