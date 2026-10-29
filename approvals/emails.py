"""E-mail side of the approval notifications.

Mails are sent after the DB transaction commits and (by default) in a daemon
thread, so a slow or unreachable SMTP server never blocks the request nor
rolls anything back — failures are only logged, like documents/notifications.py.
"""

import logging
import threading
from urllib.parse import urlsplit

from django.conf import settings
from django.core import mail
from django.db import transaction

logger = logging.getLogger(__name__)


def absolute_url(path, request=None):
    """Absolute link for a path produced by reverse() (already script-prefixed)."""
    if not path:
        return ""
    if request is not None:
        return request.build_absolute_uri(path)
    site = urlsplit(getattr(settings, "SITE_URL", ""))
    if site.scheme and site.netloc:
        return f"{site.scheme}://{site.netloc}{path}"
    return path


def _deliver(messages):
    try:
        connection = mail.get_connection(fail_silently=False)
        connection.send_messages(messages)
    except Exception:
        logger.exception("Approval notification e-mail failed (%d message(s))", len(messages))


def send_emails(users, subject, lines):
    """Send the same text to each user that has an e-mail address (one mail each,
    so recipients never see each other)."""
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    body = "\n".join(lines)
    messages = [
        mail.EmailMessage(subject=subject, body=body, from_email=from_email, to=[u.email])
        for u in users
        if u.email
    ]
    if not messages:
        return

    def _go():
        if getattr(settings, "APPROVAL_MAIL_ASYNC", True):
            threading.Thread(target=_deliver, args=(messages,), daemon=True).start()
        else:
            _deliver(messages)

    transaction.on_commit(_go)
