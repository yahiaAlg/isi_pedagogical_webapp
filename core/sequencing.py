"""
core/sequencing.py

Document numbering sequencers built on core.models.SequenceCounter.

Two independent sequences live here. Neither one is, or should ever be
confused with, a Session's own `reference` (formation-code-based, generated
separately in formations/utils.py:generate_session_reference):

* PV number       — one counter per calendar MONTH ("2026-08"), format
                     "{BRANCH}{SPECIALITE}-{NNN}/{MM}/{YYYY}" (e.g.
                     "TAG0717-006/07/2026"), where {BRANCH}{SPECIALITE} is
                     the session's formation's Specialty.reference_root
                     (branch.abbreviation + specialty.code — see
                     formations/models.py:Specialty.reference_root). When no
                     specialty code is available the codification prefix is
                     simply omitted, falling back to "{NNN}/{MM}/{YYYY}".
                     The counter itself stays a single global monthly
                     sequence — NOT split per branch/specialty — so {NNN}
                     keeps incrementing across every PV printed that month
                     regardless of codification. Assigned once per session,
                     the first time either the جدول اسمي نهائي
                     (nominal list) or the محضر مداولات نهاية التكوين
                     (deliberation report / PV) is printed — see
                     Session.assign_pv_number() — and reused by both
                     documents so they always display the same reference.

* Certificate no. — one counter per calendar YEAR ("2026"), format
                     "{YYYY}/{MM} ت.ح.ط /{NNN}". MM here is only the month
                     the certificate happens to be issued in; it plays no
                     role in the counter's scope, which resets on Jan 1st.
                     Assigned once per participant, the first time their
                     attestation is printed — see
                     formations/utils.py:assign_certificate_number.

Both allocations go through SequenceCounter.next_value(), which increments
the underlying counter atomically, so concurrent requests (e.g. two staff
members printing two different attestations, or generating the nominal
list and the PV within the same second) can never collide on the same
number, and a session/month boundary crossed mid-way through can never
leak the previous period's counter into the new one.

Which period actually receives the number is NOT simply "today's
month/year" — it's whichever period an admin has pinned as ACTIVE for
that kind (Paramètres > Numérotation des documents), via
SequenceCounter.get_active_period_key(). On a fresh install, or for a
kind an admin has never touched, that resolves to today's calendar
period automatically; once an admin explicitly activates a period, it
stays authoritative indefinitely regardless of the real date, until
they activate a different one.
"""

from .models import SequenceCounter

PV_KIND = "pv"
CERTIFICATE_KIND = "certificate"
MISSION_ORDER_KIND = "mission_order"


def allocate_pv_number(code_prefix=""):
    """
    Allocate the next PV (محضر مداولات) number under the currently ACTIVE
    period for the "pv" kind (see SequenceCounter.get_active_period_key —
    defaults to the current calendar month until an admin pins another one).

    Format: "{code_prefix}-{NNN}/{MM}/{YYYY}" when `code_prefix` is given
    (e.g. "TAG0717-006/07/2026"), otherwise "{NNN}/{MM}/{YYYY}". `MM`/`YYYY`
    in the printed number come from the active period itself, not from
    today's date. `code_prefix` is purely cosmetic — it is NOT part of the
    counter's scope, which stays ONE counter per active period shared by
    every branch/specialty.
    """
    period_key = SequenceCounter.get_active_period_key(PV_KIND)
    year_str, month_str = period_key.split("-")
    seq = SequenceCounter.next_value(PV_KIND, period_key)
    number = f"{seq:03d}/{month_str}/{year_str}"
    code_prefix = (code_prefix or "").strip()
    return f"{code_prefix}-{number}" if code_prefix else number


def allocate_certificate_number():
    """
    Allocate the next certificate/attestation number under the currently
    ACTIVE period for the "certificate" kind (defaults to the current
    calendar year until an admin pins another one). Format:
    "{YYYY}/{MM} ت.ح.ط /{NNN}" — `YYYY` comes from the active period;
    `MM` is only today's month, shown for information and playing no role
    in the counter's scope.
    """
    from django.utils import timezone

    period_key = SequenceCounter.get_active_period_key(CERTIFICATE_KIND)
    seq = SequenceCounter.next_value(CERTIFICATE_KIND, period_key)
    month = timezone.localdate().month
    return f"{period_key}/{month:02d} ت.ح.ط /{seq:03d}"


def allocate_mission_order_number():
    """
    Allocate the next "ordre de mission" archival number ("N° d'Archivage")
    under the currently ACTIVE period for the "mission_order" kind
    (defaults to the current calendar year until an admin pins another
    one). Format: "{NNN}/{YYYY}". Shared by BOTH kinds of mission order —
    a session's formateur mission order (Session.assign_mission_order_number,
    one per session) and a standalone employee mission order
    (documents.EmployeeMissionOrder) — so the two never collide and
    together form a single continuous archive within the active period,
    the same way a paper "ordre de mission" registry would be kept
    regardless of who the order is for.
    """
    period_key = SequenceCounter.get_active_period_key(MISSION_ORDER_KIND)
    seq = SequenceCounter.next_value(MISSION_ORDER_KIND, period_key)
    return f"{seq:03d}/{period_key}"
