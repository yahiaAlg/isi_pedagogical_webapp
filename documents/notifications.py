"""
Email notifications for document generation events.

Currently handles: notifying a configurable recipients list whenever a
session's deliberation report (PV de délibération) is generated.
Recipients are configured globally in Core > Paramètres
(InstituteInfo.pv_notification_recipients).
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from core.models import InstituteInfo

logger = logging.getLogger(__name__)


def notify_pv_generated(session, generated_by=None, request=None):
    """
    Send an email notification to the configured recipients list when a
    session's deliberation report (PV) is generated.

    Silently no-ops if no institute settings exist or no recipients are
    configured. Any send failure is logged rather than raised, so a mail
    outage never blocks the document-generation flow.

    Returns True if an email was sent, False otherwise.
    """
    institute = InstituteInfo.get_instance()
    if not institute:
        return False

    recipients = institute.get_pv_notification_recipients_list()
    if not recipients:
        return False

    subject = f"PV de délibération généré — {session.reference}"

    pv_url = ""
    if request is not None:
        try:
            path = reverse(
                "documents:print_deliberation_report", kwargs={"session_pk": session.pk}
            )
            pv_url = request.build_absolute_uri(path)
        except Exception:
            pv_url = ""

    lines = [
        "Bonjour,",
        "",
        f"Le PV de délibération de la session « {session.reference} » vient d'être généré.",
        "",
        f"Formation : {session.formation}",
        f"Client : {session.client}",
        f"Période : {session.date_start:%d/%m/%Y} au {session.date_end:%d/%m/%Y}",
    ]
    if generated_by is not None:
        lines.append(f"Généré par : {generated_by.get_full_name() or generated_by.username}")
    if pv_url:
        lines += ["", f"Consulter / imprimer le PV : {pv_url}"]
    lines += ["", "— Notification automatique, merci de ne pas répondre à cet email."]

    message = "\n".join(lines)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or institute.email or None

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send PV-generated notification for session %s", session.pk
        )
        return False
