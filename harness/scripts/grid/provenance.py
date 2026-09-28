"""grid/provenance.py — the coverage-grid emit provenance mark (leaf, stdlib-only).

WHY: ``grid_emit_guard.py --require`` is the hard presence gate that ``plan_approval``
and cook's Phase-DAG preflight lean on. Presence-only, it could not tell an
engine-emitted grid from one an agent HAND-WROTE to clear the gate (skipping
``grid_engine.py`` and its invariant/confab/verdict pass entirely). This module
binds an emitted artifact to the engine that produced it: ``emit`` stamps a
provenance block, and the guard recomputes + checks it.

HONEST LIMITATION (do not oversell): a file-based harness has NO secret, so this
is NOT cryptographically unforgeable. The earlier wording here claimed forging a
matching digest required "re-implementing the engine's canonical serialization"
-- that overstated the barrier. It does not: ``from grid.provenance import
stamp`` (this module, importable by anyone), build a plain dict by hand, call
``stamp()`` on it -- three lines, no engine call anywhere -- and the guard
returns ok, because ``stamp``/``verify`` only check that the payload's OWN
digest matches itself; they cannot tell a hand-built dict from one
``grid_engine.py`` actually produced through build/expand/review. What this
DOES still defeat is the observed failure mode this module was built for: an
agent that lazily SKIPS the engine and hand-writes a plausible grid WITHOUT
calling ``stamp`` at all (no ``emitted_by``/no digest, the common case), and
any post-emit hand-edit of a real artifact that does not also recompute the
digest (the digest stops matching). Against an attacker who reads this file and
calls ``stamp`` deliberately, it defeats nothing — see also
``grid_emit_guard._has_zero_cells`` (a ``cells: []`` record forged this exact
way used to pass every arm) and the ``axis_selection.src_sha256`` field below,
which is likewise never compared against anything — it is recorded, not
verified. Pure stdlib + pure functions so both the writer (``grid/artifact.py``)
and the guard (``grid_emit_guard.py``) import the SAME digest with no shared
state.
"""
import hashlib
import json

# The only value the guard accepts as proof the artifact came from the engine.
EMITTER = "grid_engine"
# The artifact CONTRACT version -- not only the digest algorithm. Bump when
# either the digest payload/algorithm changes (so an old artifact fails
# cleanly instead of silently mis-verifying) OR a new gate starts enforcing a
# requirement against every freshly-stamped record. v2: the grid_emit_guard
# axis-selection receipt is REQUIRED (not exempted) on a macro planner-shaped
# grid -- see grid_emit_guard._axis_receipt_required, decided by FILE PATH
# alone, with NO grandfather by this field or any other: `provenance` (this
# whole block, including `mark_version`) is itself in `_VOLATILE` below --
# excluded from the digest -- so a grandfather keyed on `mark_version` could
# be defeated by editing it post-emit with zero effect on `verify()` (this WAS
# the design here; it was a real hole, since closed). Named to avoid the
# record's top-level ``schema_version`` (the grid schema's own, unrelated)
# field.
MARK_VERSION = 2
# Fields excluded from the digest: volatile stamps written AFTER the digest is
# computed (``run_seq`` by stamp_and_write), the human-facing timestamp, and the
# provenance block itself (it cannot hash itself).
_VOLATILE = ("ts", "run_seq", "provenance")


def _payload(record):
    """The stable subset of ``record`` the digest covers — everything except the
    volatile stamps. ``json.dumps(sort_keys=True)`` below makes key order and
    nesting deterministic, so the writer's dict and the guard's parsed-back dict
    hash identically."""
    return {k: v for k, v in record.items() if k not in _VOLATILE}


def digest(record):
    """A hex sha256 over the canonical JSON of the record's stable content.
    ``default=str`` is belt-and-suspenders for any non-JSON-native leaf (the grid
    record is JSON-native today); ``sort_keys`` + tight separators keep it stable
    across the write→serialize→read round-trip (json and yaml both round-trip the
    native types faithfully)."""
    blob = json.dumps(
        _payload(record), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def stamp(record):
    """The provenance block for ``record`` (which must NOT already contain one —
    ``_VOLATILE`` excludes it, but compute the digest BEFORE assigning to be
    unambiguous). Returns a plain dict the caller assigns to ``record['provenance']``."""
    return {
        "emitted_by": EMITTER,
        "mark_version": MARK_VERSION,
        "content_sha256": digest(record),
    }


def verify(record):
    """True iff ``record`` carries a valid engine provenance block: ``emitted_by``
    is the engine AND ``content_sha256`` matches a fresh digest of the record's
    own stable content. Any missing/mismatched field → False (fail-closed: the
    whole point is that a non-engine artifact does not pass)."""
    prov = (record or {}).get("provenance") or {}
    if prov.get("emitted_by") != EMITTER:
        return False
    recorded = prov.get("content_sha256")
    return bool(recorded) and recorded == digest(record)
