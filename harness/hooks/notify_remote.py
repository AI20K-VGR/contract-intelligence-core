#!/usr/bin/env python3
"""notify_remote.py — Notification-event hook: relay Claude's notification to a
user-configured webhook so an UNATTENDED run (AFK loop, /goal until-429) reaches the
operator's phone/chat the moment something needs them.

Ships OFF. With no HARNESS_NOTIFY_WEBHOOK set it is a no-op. When set, it POSTs ONLY
the notification text Claude already surfaced to the user — never command output,
never a secret — as {"text": <msg>} to that URL. The webhook is read from the env
and is NEVER logged or echoed. Fail-open telemetry: any network/parse error is
swallowed and a short timeout bounds the delay; it never blocks the session.

SSRF posture (this is the first sanctioned external-egress surface, so it is
conservative): https-only; the host is RESOLVED and rejected unless every address is
globally-routable (blocks loopback / private / link-local / cloud-metadata, whether
spelled as an IP or a DNS name that resolves to one); and redirects are NOT followed
(a 30x to an internal target cannot bypass the resolve check). Fail-CLOSED on the
guard: if the host cannot be resolved/verified, nothing is sent.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_HERE)
sys.path.append(os.path.join(os.path.dirname(_HERE), "scripts"))

import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"
_STEM = "notify_remote"
_TIMEOUT = 4
_MAX = 1000


def _host_is_safe(host, port=443) -> bool:
    """True iff `host` resolves at `port` and EVERY resolved address is globally routable.
    Fail-closed: a resolution error or any non-global address (loopback / private /
    link-local / metadata / reserved / multicast) returns False."""
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0]).is_global:
                return False
        except ValueError:
            return False
    return True


def _webhook():
    """The configured relay URL, or None — https-only + SSRF-guarded host."""
    import urllib.parse
    url = (os.environ.get("HARNESS_NOTIFY_WEBHOOK") or "").strip()
    if not url.startswith("https://"):
        return None
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    port = parts.port or 443
    if not host or not _host_is_safe(host, port):
        return None
    return url


def _post(url, payload) -> None:
    """Imported HERE, not at module scope: a hook pays its imports on every matching
    event, and this one ships OFF. `import httpx` measures +66.2 ms against a 12.8 ms
    baseline (urllib.request was +29.5 ms), so the ~37 ms delta lands only on runs
    where an operator has deliberately configured a webhook AND a notification fires
    — where it is already dwarfed by the _TIMEOUT-second network budget.

    `follow_redirects=False` replaces the urllib no-redirect opener and is stated
    rather than inherited: a 30x to an internal target must NOT bypass _host_is_safe,
    so a library default-flip cannot silently open that hole.
    """
    import httpx

    httpx.post(url, json=payload, timeout=_TIMEOUT, follow_redirects=False)


def core(data: dict) -> None:
    url = _webhook()
    if not url:
        return  # default-off or SSRF-guarded out
    msg = data.get("message")
    if not isinstance(msg, str) or not msg.strip():
        return
    try:
        _post(url, {"text": msg.strip()[:_MAX]})
    except Exception:  # noqa: BLE001 — fail-open: a relay error never breaks the run
        pass


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
