import hashlib
import json

from .fiche import build_fiche


def build_payload(formation):
    """What the website needs to create/refresh the Offering."""
    f = formation
    category = f.category.name if f.category_id else ""
    branch = f.specialty.branch.name if f.specialty_id else ""
    return {
        "isi_id": f.pk,
        "code": (f.website_code or f.code or "").strip(),
        "specialty_code": f.specialty.reference_root if f.specialty_id else "",
        "fields": {
            "title": f.title,
            "branch_label": category or branch,
            "duration_days": f.duration_days,
            "seats_available": f.max_participants,
            "is_active": bool(f.is_active),
        },
        "fiche": build_fiche(f),
    }


def payload_hash(payload):
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
