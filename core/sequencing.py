"""
core/sequencing.py

Document numbering sequencers built on core.models.SequenceCounter.

Two independent sequences live here. Neither one is, or should ever be
confused with, a Session's own `reference` (formation-code-based, generated
separately in formations/utils.py:generate_session_reference):

* PV number       — one counter per calendar MONTH ("2026-08"), format
                     "{YYYY}/{MM}/{NNN}" (e.g. "2026/08/001"). Assigned once
                     per session, the first time either the جدول اسمي نهائي
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


def allocate_pv_number(reference_date=None):
    """
    Allocate the next PV (محضر مداولات) number for the month of
    `reference_date` (defaults to today). Format: "{YYYY}/{MM}/{NNN}".
    The counter resets to 1 on the 1st of every calendar month.
    """
    ref = reference_date or timezone.localdate()
    period_key = f"{ref.year:04d}-{ref.month:02d}"
    seq = SequenceCounter.next_value(PV_KIND, period_key)
    return f"{ref.year:04d}/{ref.month:02d}/{seq:03d}"


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
