"""
core/netutils.py

Client-address helpers used to decide whether a request comes from the
institute's local network (LAN) — see core.views.verify_by_code.
"""

import ipaddress

from django.conf import settings


def _parse(value):
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def client_ip(request):
    """Best-effort client address.

    X-Forwarded-For is only honoured when the direct peer is itself a private/
    loopback address (i.e. our own reverse proxy, e.g. nginx); in that case the
    RIGHT-most entry is used, because that is the one our proxy appended — the
    left-most entries are client-controlled and can be forged.
    """
    peer = _parse(request.META.get("REMOTE_ADDR"))
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if peer is not None and (peer.is_private or peer.is_loopback) and xff:
        forwarded = _parse(xff.split(",")[-1])
        if forwarded is not None:
            return forwarded
    return peer


def is_lan_request(request):
    """True for private/loopback/link-local clients and any address inside
    settings.LAN_EXTRA_NETWORKS (e.g. the institute's public NAT address)."""
    ip = client_ip(request)
    if ip is None:
        return False
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return True
    for net in getattr(settings, "LAN_EXTRA_NETWORKS", []):
        try:
            if ip in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False
