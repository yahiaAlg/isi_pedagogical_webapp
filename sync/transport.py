"""Signed HTTP calls to the website's /internal/sync/ endpoints (stdlib only).

signature = HMAC-SHA256(secret, f"{ts}\\n{METHOD}\\n{path_with_query}\\n" + body)
— must match the website's bridge/security.py.
"""

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class SyncError(Exception):
    pass


def secret():
    return getattr(settings, "SYNC_SHARED_SECRET", "") or ""


def is_configured():
    return bool(secret() and getattr(settings, "MAIN_SITE_URL", ""))


def sign(key, timestamp, method, path, body):
    msg = f"{timestamp}\n{method.upper()}\n{path}\n".encode() + (body or b"")
    return hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()


def call(method, endpoint, params=None, payload=None, timeout=None):
    """endpoint like 'feed/' or 'formations/'. Returns the decoded JSON."""
    if not is_configured():
        raise SyncError("SYNC_SHARED_SECRET / MAIN_SITE_URL non configurés.")
    base = settings.MAIN_SITE_URL.rstrip("/")
    url = f"{base}/internal/sync/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    parsed = urllib.parse.urlparse(url)
    signed_path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    ts = str(int(time.time()))
    req = urllib.request.Request(
        url,
        data=body if method.upper() != "GET" else None,
        method=method.upper(),
        headers={
            "X-Sync-Timestamp": ts,
            "X-Sync-Signature": sign(secret(), ts, method, signed_path, body),
            "Content-Type": "application/json",
            "User-Agent": "isi-pedagogy-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or getattr(settings, "SYNC_TIMEOUT", 20)) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise SyncError(f"Le site a répondu HTTP {exc.code} {detail}".strip())
    except Exception as exc:  # DNS, timeout, TLS...
        raise SyncError(f"Site injoignable : {exc}")
