#!/usr/bin/env python3
"""persona_me.py — the per-user RELATIONSHIP (PII) tier.

RELATIONSHIP is the data a user self-declares about themselves — name, role,
relationship, occupation, a one-line trait — so the terminal voice can address
them as a known person. It is PII: it is NEVER committed and NEVER injected into a
subagent surface (the injection split lives in voice_inject; this module only
provides the loader + the auto-.gitignore).

Storage: a gitignored per-user JSON file. Path resolves as
env HARNESS_PERSONA_ME > ~/.claude/persona-me.json (~/.claude is NOT a git repo
today; the sibling .gitignore is defence against a future dotfile repo). JSON
because it is machine-written data (code-standards §3), though the read path
tolerates a hand-edited file.

Read path (load) NEVER raises: a missing file, corrupt JSON, or a non-mapping top
level degrades to None; an over-maxlen field is dropped (clamped out) rather than
raising. Write path (save) validates maxlen (raises PersonaMeError) and enforces
the F9 ordering: the sibling .gitignore is written BEFORE the JSON, so a gitignore
failure raises and leaves NO un-ignored PII on disk.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Shared maxlen mechanism (F5) — imported from the registry module so the length
# check has one home. name reuses the bundle name cap (40); every other
# RELATIONSHIP field caps at 150 (locked at plan validate, the "deeper" tier).
import persona_bundle

_ENV = "HARNESS_PERSONA_ME"
_DEFAULT = Path.home() / ".claude" / "persona-me.json"

RELATIONSHIP_MAXLEN: Dict[str, int] = {"name": persona_bundle.MAXLEN["name"]}
_DEFAULT_MAXLEN = 150


class PersonaMeError(ValueError):
    """Raised by save() when a field exceeds maxlen or the sibling .gitignore
    cannot be written (fail-closed BEFORE the PII JSON). The read path is tolerant
    and never raises."""


def me_path() -> Path:
    """Resolve the PII file path: env HARNESS_PERSONA_ME > ~/.claude/persona-me.json."""
    raw = os.environ.get(_ENV)
    if raw:
        return Path(raw)
    return _DEFAULT


def _limit_for(field: str) -> int:
    return RELATIONSHIP_MAXLEN.get(field, _DEFAULT_MAXLEN)


def load() -> Optional[Dict[str, Any]]:
    """Return the RELATIONSHIP dict, or None. A missing file, corrupt JSON, or a
    non-mapping top level → None. An over-maxlen field is DROPPED (tolerant read),
    never raised — a note is recorded under `_diag`."""
    p = me_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    out: Dict[str, Any] = {}
    dropped = []
    for field, value in raw.items():
        if isinstance(value, str) and len(value) > _limit_for(field):
            dropped.append(field)
            continue  # clamp out the over-limit field rather than raise
        out[field] = value
    if dropped:
        out.setdefault("_diag", []).append(
            "dropped over-maxlen field(s): " + ", ".join(sorted(dropped)))
    return out


def _ensure_gitignore(pii_path: Path) -> None:
    """Ensure a sibling .gitignore lists the PII filename. Creates it, or appends
    the line if absent (never duplicating). Raises OSError on any I/O failure —
    the caller turns that into a fail-closed PersonaMeError BEFORE writing JSON."""
    gi = pii_path.parent / ".gitignore"
    name = pii_path.name
    existing = ""
    if gi.is_file():
        existing = gi.read_text(encoding="utf-8")
        lines = {ln.strip() for ln in existing.splitlines()}
        if name in lines:
            return  # already ignored, no duplicate
    prefix = "" if (existing == "" or existing.endswith("\n")) else "\n"
    with open(gi, "a", encoding="utf-8") as fh:
        fh.write(prefix + name + "\n")


def save(fields: Dict[str, Any]) -> Path:
    """Write the RELATIONSHIP JSON. Order (F9), fail-closed:
      1. validate maxlen on every field (raise PersonaMeError on violation);
      2. ensure the sibling .gitignore lists the PII filename — BEFORE the JSON;
         a gitignore failure raises PersonaMeError and no JSON is written;
      3. only then write the JSON.
    This ordering guarantees a PII file never lands on disk un-ignored."""
    p = me_path()

    # (1) maxlen validation — reuse the shared helper, surface as PersonaMeError
    for field, value in fields.items():
        try:
            persona_bundle.check_maxlen(field, value, _limit_for(field))
        except persona_bundle.PersonaBundleError as exc:
            raise PersonaMeError(str(exc)) from exc

    p.parent.mkdir(parents=True, exist_ok=True)

    # (2) .gitignore BEFORE the JSON — fail-closed if it cannot be written.
    # UnicodeDecodeError (a hand-edited / other-tool .gitignore in a non-UTF-8
    # encoding) is a ValueError, not an OSError, so catch it explicitly — else it
    # would bypass the PersonaMeError contract the write path promises.
    try:
        _ensure_gitignore(p)
    except (OSError, UnicodeDecodeError) as exc:
        raise PersonaMeError(
            f"refusing to write PII: could not update sibling .gitignore ({exc})") from exc

    # (3) JSON last, only once the ignore is in place
    p.write_text(json.dumps(fields, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
