#!/usr/bin/env python3
"""feature_checklist.py — serialize + FREEZE a feature/risk checklist.

Deterministic, 0-token CLI leaf. The checklist VALUES come from elsewhere —
an independent ``@independent-revalidator`` re-derivation, spawned in a later
step — this module only persists them and stamps a self-referential
``content_sha256`` so a later hand-edit of the on-disk record is detectable
(``load_checklist`` recomputes the digest and fails loud on a mismatch).

HONEST LIMITATION (do not oversell): the checklist is MODEL-authored, and
this freeze is not cryptographic proof of anything about its CONTENT — it
proves only that the record was not silently BACK-EDITED after
materialization. It does not attest completeness or human review. Its
strength is structural independence (a different agent, re-derived before a
plan's own feature list exists), not a human-proof guarantee.

Deliberately decoupled from ``grid/provenance.py``: the freeze here is a
plain ~10-line inline hash, not an import of the grid engine's provenance
module — this producer has nothing to do with the coverage-grid gate.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
if _THIS not in sys.path:
    sys.path.insert(0, _THIS)
import artifact_io  # noqa: E402

KIND = "feature-risk-checklist"

# Excluded from the digest: content_sha256 cannot hash itself, and run_seq is
# injected by artifact_io.stamp_and_write AFTER the digest is computed — a
# reader that recomputes over the on-disk record (which DOES carry run_seq)
# must exclude it too, or every legitimate round-trip would falsely "detect"
# a back-edit.
_VOLATILE_KEYS = ("content_sha256", "run_seq")


def _digest(record: dict) -> str:
    """sha256 hex over the canonical JSON of ``record``'s stable content
    (volatile keys excluded, keys sorted, tight separators) — the same
    payload shape on both the emit side and the load side, so a
    write→serialize→read round-trip hashes identically."""
    payload = {k: v for k, v in record.items() if k not in _VOLATILE_KEYS}
    blob = json.dumps(
        payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_checklist(features, risks=None, stakeholders=None,
                     source="discover-pass-1", now=None) -> dict:
    """Build + freeze a checklist record. Raises ``ValueError`` if
    ``features`` is empty (mirrors the fail-loud style of
    ``grid.axes.build_planner_axes``: values must come from a real
    re-derivation, never be hand-typed as a placeholder)."""
    features = [f for f in (features or []) if f]
    if not features:
        raise ValueError(
            "feature_checklist: at least one --feature is required "
            "(features must come from an independent re-derivation, not be "
            "hand-typed as a placeholder)."
        )
    record = {
        "kind": KIND,
        "features": list(features),
        "risks": list(risks or []),
        "stakeholders": list(stakeholders or []),
        "source": source,
        "created_at": now or datetime.now(timezone.utc).isoformat(),
    }
    record["content_sha256"] = _digest(record)
    return record


def load_checklist(path) -> dict:
    """Read + validate a checklist record, failing LOUD (``ValueError``) on
    any of: unreadable file, invalid JSON, non-object document, wrong
    ``kind``, empty/missing ``features``, or a ``content_sha256`` that does
    not match a fresh recomputation over the record's own stable content
    (the back-edit / tamper-detection arm)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("checklist %r unreadable: %s" % (path, exc)) from exc
    try:
        record = json.loads(raw)
    except ValueError as exc:
        raise ValueError("checklist %r is not valid JSON: %s" % (path, exc)) from exc

    if not isinstance(record, dict):
        raise ValueError("checklist %r is not a JSON object" % (path,))
    if record.get("kind") != KIND:
        raise ValueError(
            "checklist %r has kind=%r, expected %r"
            % (path, record.get("kind"), KIND))
    features = record.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("checklist %r: 'features' must be a non-empty list" % (path,))

    recorded_digest = record.get("content_sha256")
    if not recorded_digest:
        raise ValueError("checklist %r is missing content_sha256 — not a frozen checklist" % (path,))
    recomputed = _digest(record)
    if recomputed != recorded_digest:
        raise ValueError(
            "checklist %r failed integrity check — content_sha256 mismatch "
            "(recorded=%s recomputed=%s): the file was BACK-EDITED after "
            "it was frozen" % (path, recorded_digest, recomputed))
    return record


def _cmd_emit(args) -> int:
    try:
        record = build_checklist(
            features=args.feature,
            risks=args.risk,
            stakeholders=args.stakeholder,
            source=args.source,
            now=args.now,
        )
    except ValueError as exc:
        sys.stderr.write("feature-checklist: %s\n" % exc)
        return 2
    artifact_io.stamp_and_write(args.out, record)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Serialize + freeze a feature/risk checklist (values "
                     "supplied by the caller; this leaf only persists them).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="write a frozen checklist record")
    p_emit.add_argument("--feature", action="append", default=[],
                         help="a feature name; repeatable, at least one required")
    p_emit.add_argument("--risk", action="append", default=[],
                         help="a risk name; repeatable")
    p_emit.add_argument("--stakeholder", action="append", default=[],
                         help="a stakeholder name; repeatable")
    p_emit.add_argument("--source", default="discover-pass-1",
                         help="provenance tag for where the checklist came from")
    p_emit.add_argument("--now", default=None,
                         help="injectable ISO-8601 timestamp (deterministic tests)")
    p_emit.add_argument("--out", required=True, help="output path (.json)")

    args = ap.parse_args(argv)
    if args.cmd == "emit":
        return _cmd_emit(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
