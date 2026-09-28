#!/usr/bin/env python3
"""
memory_gap — the deterministic SCRIPT detector for "memory that looks unrecorded".

SCRIPT-only: it correlates persisted disk/graph state and emits structured
signals — it makes NO judgment (the LLM decides what to do about each). It NEVER
re-implements a detector it can import: fence detection is `check_fence.scan`; the
graph + `body_hash` + parse-error surface are `spec_graph`. One home per fact —
this module only correlates.

Signals at THIS tier (each `{type, severity, subject, evidence, suggested_writer}`):
  - `fence_breach` — a working-tree change landed OUTSIDE the declared ownership
    zones. Reuses `check_fence.scan` verbatim; the suggested writer is the
    in-zone move, not a memory write. Severity `warn`.
  - `parse_error` — an artifact the graph could not parse. Surfaced advisory so a
    malformed file is visible, never a crash. Severity `warn`.

The wider source funnel (validate_no_marker / approved_changed_no_dec /
judged_not_stored, plus the `--ack-no-dec` suppression) is deferred: those rest
on a validated-snapshot marker, a decision register `affects` set, and a verdict
cache this tier does not yet stand up. `REGISTERED_SIGNAL_TYPES` is the explicit
tier-1 contract — the presence-closure test asserts it, so a later tier widens it
in one place and a silent trim is caught.

Deterministic: same disk state → same `signals` list (sorted, no wall-clock in the
body). ALWAYS exits 0 (advisory) — any failure surfaces as a `parse_error` signal,
never a traceback.

CLI:
    memory_gap.py --root <project-dir>          # emit {signals:[...]}, exit 0
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from encoding_utils import configure_utf8_console
import check_fence
from spec_graph import build_graph

configure_utf8_console()


# The signal types this detector is wired to emit at this tier. Declared as DATA
# (not just implied by behavior) so the presence-closure test can assert the exact
# tier-1 set: a silent trim — dropping a signal without breaking an import — still
# fails that test. A later tier appends to this tuple in ONE place.
REGISTERED_SIGNAL_TYPES = ("fence_breach", "parse_error")


# ----------------------------------------------------------------------------
# Signal builders
# ----------------------------------------------------------------------------

def _signal(stype: str, severity: str, subject: Optional[str], evidence: str,
            suggested_writer: str) -> Dict[str, Any]:
    return {
        "type": stype,
        "severity": severity,
        "subject": subject,
        "evidence": evidence,
        "suggested_writer": suggested_writer,
    }


# Cap on individually-listed fence breaches before they collapse into one aggregate
# signal. A session that legitimately touches many out-of-zone files must never flood
# the advisory into an over-report — so the tail is summarized, not enumerated, with
# the full count preserved. This cap is the tier's flood-control (check_fence reports
# every breach faithfully; the cap lives here, one layer up).
_FENCE_SIGNAL_CAP = 10


def _fence_signals(root) -> List[Dict[str, Any]]:
    """One `fence_breach` per file `check_fence.scan` reports outside the declared
    zones, up to `_FENCE_SIGNAL_CAP`; any overflow collapses into a single aggregate
    signal carrying the total count. Reuses the imported scan verbatim — no
    re-implementation of the porcelain walk."""
    breaches = check_fence.scan(Path(root))
    out: List[Dict[str, Any]] = []
    for f in breaches[:_FENCE_SIGNAL_CAP]:
        out.append(_signal(
            "fence_breach", "warn", f["file"],
            f.get("detail") or f"{f['file']} touched outside the declared ownership zones.",
            "review the out-of-zone change; move it under a declared zone if it belongs there",
        ))
    extra = len(breaches) - _FENCE_SIGNAL_CAP
    if extra > 0:
        out.append(_signal(
            "fence_breach", "warn", None,
            f"+{extra} more files touched outside the declared zones ({len(breaches)} total).",
            "review the out-of-zone changes; move any that belong under a declared zone",
        ))
    return out


# ----------------------------------------------------------------------------
# Correlate → signals
# ----------------------------------------------------------------------------

def collect(root, include_parse_errors: bool = True) -> List[Dict[str, Any]]:
    """Build every tier-1 memory-gap signal for `root`, deterministically sorted.

    Order key = (type, subject) so the output is stable across runs (same disk
    state → same list). A malformed artifact surfaces as a `parse_error` signal
    (from the graph's `parse_errors`) — never a crash.

    `include_parse_errors` gates the SPEC-GRAPH parse (`build_graph`, which walks
    and parses every `docs/product/` artifact — the dominant cost). A caller that
    knows this turn cannot have introduced a docs/product parse error (it touched
    no artifact under that tree) passes False to skip the parse entirely and pay
    only the cheap fence scan. Default True preserves the CLI + every existing
    caller. The `parse_error` signal is a function of DISK state, so a standing
    breakage is caught by the docs-validation pipeline; this hot-path scoping only
    declines to re-derive it on turns that provably could not have caused one."""
    root = Path(root).resolve()

    signals: List[Dict[str, Any]] = []

    # Surface any artifact the graph could not parse (advisory — never block).
    # Skipped when the caller excludes parse errors — build_graph is the 220ms
    # cost, and it contributes ONLY these signals to this collector.
    if include_parse_errors:
        graph = build_graph(root)
        for pe in graph.get("parse_errors") or []:
            signals.append(_signal(
                "parse_error", "warn", pe.get("file"),
                f"{pe.get('file')} could not be parsed: {pe.get('error')}",
                "fix the artifact frontmatter (no memory write applies until it parses)",
            ))

    signals.extend(_fence_signals(root))

    signals.sort(key=lambda s: (s["type"], s.get("subject") or ""))
    return signals


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    try:
        signals = collect(root)
        print(json.dumps({"signals": signals}, indent=2, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001 — advisory contract: never crash
        # Advisory: any unexpected failure surfaces as a parse_error signal + exit 0,
        # never a bare traceback.
        print(json.dumps(
            {"signals": [_signal("parse_error", "warn", None, str(exc),
                                 "investigate the spec state")]},
            ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
