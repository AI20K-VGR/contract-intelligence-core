#!/usr/bin/env python3
"""gemini_secret_scrub.py — best-effort secret detector for the partner lane.

v1 is WARN-ONLY (accepted-risk): scan() reports what looks like a credential
in a prompt so the chokepoint can shout on stderr — it does NOT mask or block.
The detector is built now so v2 can flip the posture (secret_scrub: block|redact)
without new plumbing. Returns offsets into the raw text, never a masked copy.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretHit:
    pattern: str   # the detector name that matched
    offset: int    # start index into the scanned text


# The label-keyed patterns, the placeholder carve-out and the local-host carve-out below are
# COPIED from harness/hooks/secret_scan_before_ship.py, never imported — a plugin script must
# stay self-contained for the install slot. harness/tests/test_secret_pattern_parity.py runs
# both lists over one case set so the copy cannot drift again.
_LABEL_WORDS = (r"(?:api[_-]?key|apikey|api[_-]?secret|secret|token|credential"
                r"|password|passwd|pwd)")

# (name, compiled regex). Ordered by specificity; scan() sorts hits by offset.
_PATTERNS = [
    # A 16-char credential-alphabet floor on the VALUE, not a bare `KEY=`. Measured on the
    # 1210 prose files this lane actually ships: the label-only form matched 258 times with
    # zero real credentials among them (`password = 3;`, `key =>`, `api_key=os.getenv(...)`)
    # — a warning that fires once every eleven files is a warning nobody reads, and being
    # read is the only thing this warn-only lane does. The floor costs the weak-short case
    # (`PASSWORD=abc`), the same gap the ship gate accepts.
    ("assignment", re.compile(r"""(?i)%s\s*[:=]\s*['"][A-Za-z0-9/+=_-]{16,}['"]""" % _LABEL_WORDS)),
    ("assignment_unquoted", re.compile(
        r"""(?i)%s\s*[:=]\s*['"]?(?=[A-Za-z0-9/+=_-]*[0-9])[A-Za-z0-9/+=_-]{16,}""" % _LABEL_WORDS)),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    # `[ ]` instead of a literal space, exactly as secret_scan_before_ship spells
    # the same pattern: a detector whose source carries the marker it hunts for
    # cannot be changed, because the pre-push gate scans the DIFF with this very
    # vocabulary and refuses the commit that adds the line. Measured: adding this
    # pattern made the branch unpushable. The compiled regex is identical.
    ("pgp_private_key", re.compile(r"-----BEGIN[ ]PGP[ ]PRIVATE[ ]KEY[ ]BLOCK-----")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    # Hyphen inside the class: `sk-ant-…` and `sk-proj-…` both carry one in the key
    # body, and without it the {20,} floor is never reached — the key reads as prose
    # and the warning never fires on the one credential this lane actually handles.
    ("vendor_sk_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("gitlab_pat", re.compile(r"glpat-[A-Za-z0-9_-]{20}")),
    ("stripe_key", re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"AIza[A-Za-z0-9_-]{35}")),
    ("npm_token", re.compile(r"npm_[A-Za-z0-9]{30,}")),
    ("sendgrid_key", re.compile(r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}")),
    ("hf_token", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("do_token", re.compile(r"dop_v1_[a-f0-9]{64}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    # Any scheme, unlike the ship gate's http/https-only form: that gate owns db DSNs through
    # a separate db-uri-cred pattern and this list has none, so restricting the scheme here
    # would leave a credential-bearing `postgres://` DSN unwarned on its way to Google.
    # (Spelling that DSN out here as a literal trips the ship gate on this very file — the
    # scan reads added diff lines, comments included.)
    ("basic_auth_url", re.compile(
        r"(?i)\b[a-z][a-z0-9+.-]*://[^\s:/@]+:(?P<cred>[^\s:/@]{4,})@(?P<host>[^\s:/?#]+)")),
    # `Bearer` without the `Authorization:` prefix too — a raw header line pasted mid-prompt
    # carries the same credential — but with a value floor, so `Bearer <token>` stays prose.
    ("bearer_auth", re.compile(r"(?i)\bBearer\s+(?P<cred>[A-Za-z0-9._~+/=-]{16,})")),
]

# Label-keyed families: matched off a word rather than a vendor prefix, so a documentation
# placeholder can land inside the match. Extending this to `AKIA…`/`ghp_…` would silence
# `# example: ghp_<real key>`.
_LABEL_FAMILIES = ("assignment", "bearer_auth", "basic_auth_url")
_PLACEHOLDER_RE = re.compile(
    r"(?i)\b(?:your|example|sample|placeholder|changeme|dummy|redacted|todo)"
    r"|<[A-Za-z_]|\.\.\.|here['\"]?\s*$")

# A `cred` group narrows the carve-out to the credential. Handing it the whole match fails
# OPEN on any host-bearing family: `https://user:<real password>@example.com` carries
# `example` in the HOST, which disarms the pattern and reports a live credential as prose.
# A `host` group is likewise the opt-in to the local-dev carve-out below — no parallel name
# set to keep in sync, so a new host-bearing pattern cannot silently skip it.
_LOCAL_HOST_RE = re.compile(
    r"(?i)^(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[?::1\]?"
    r"|[a-z0-9_-]+"                       # single-label service name (no dot -> compose/dev)
    r"|[a-z0-9_-]+\.(?:local|localhost))$")


def scan(text):
    """Return a list of SecretHit (sorted by offset) for every detector match.
    Empty list = nothing suspicious. Never raises on ordinary text."""
    if not text:
        return []
    hits = []
    for name, rx in _PATTERNS:
        for m in rx.finditer(text):
            groups = m.groupdict()
            if name.startswith(_LABEL_FAMILIES) and _PLACEHOLDER_RE.search(
                    groups.get("cred") or m.group(0)):
                continue  # a real secret elsewhere still warns; a lone placeholder does not
            host = groups.get("host")
            if host and _LOCAL_HOST_RE.match(host.strip()):
                continue  # local-dev host — not remotely usable; a remote URI still warns
            hits.append(SecretHit(name, m.start()))
    return sorted(hits, key=lambda h: h.offset)
