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
"""

from django.utils import timezone

from .models import SequenceCounter

PV_KIND = "pv"
CERTIFICATE_KIND = "certificate"
MISSION_ORDER_KIND = "mission_order"


def allocate_pv_number(reference_date=None, code_prefix=""):
    """
    Allocate the next PV (محضر مداولات) number for the month of
    `reference_date` (defaults to today).

    Format: "{code_prefix}-{NNN}/{MM}/{YYYY}" when `code_prefix` is given
    (e.g. "TAG0717-006/07/2026"), otherwise "{NNN}/{MM}/{YYYY}".
    `code_prefix` is purely cosmetic — it is NOT part of the counter's
    scope, which stays ONE global counter per calendar month shared by
    every branch/specialty. The counter resets to 1 on the 1st of every
    calendar month.
    """
    ref = reference_date or timezone.localdate()
    period_key = f"{ref.year:04d}-{ref.month:02d}"
    seq = SequenceCounter.next_value(PV_KIND, period_key)
    number = f"{seq:03d}/{ref.month:02d}/{ref.year:04d}"
    code_prefix = (code_prefix or "").strip()
    return f"{code_prefix}-{number}" if code_prefix else number


def allocate_certificate_number(reference_date=None):
    """
    Allocate the next certificate/attestation number for the year of
    `reference_date` (defaults to today). Format:
    "{YYYY}/{MM} ت.ح.ط /{NNN}". The counter resets to 1 on Jan 1st of
    every year (scoped by year only — the month in the printed number is
    purely informational).
    """
    ref = reference_date or timezone.localdate()
    period_key = f"{ref.year:04d}"
    seq = SequenceCounter.next_value(CERTIFICATE_KIND, period_key)
    return f"{ref.year:04d}/{ref.month:02d} ت.ح.ط /{seq:03d}"


def allocate_mission_order_number(reference_date=None):
    """
    Allocate the next "ordre de mission" archival number ("N° d'Archivage").
    Format: "{NNN}/{YYYY}". One counter per calendar YEAR, shared by BOTH
    kinds of mission order — a session's formateur mission order
    (Session.assign_mission_order_number, one per session) and a standalone
    employee mission order (documents.EmployeeMissionOrder) — so the two
    never collide and together form a single continuous yearly archive,
    the same way a paper "ordre de mission" registry would be kept
    regardless of who the order is for. The counter resets to 1 on Jan 1st
    of every year.
    """
    ref = reference_date or timezone.localdate()
    period_key = f"{ref.year:04d}"
    seq = SequenceCounter.next_value(MISSION_ORDER_KIND, period_key)
    return f"{seq:03d}/{ref.year:04d}"
