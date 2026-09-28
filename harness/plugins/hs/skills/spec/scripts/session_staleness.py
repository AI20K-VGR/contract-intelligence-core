#!/usr/bin/env python3
"""
session_staleness — reconcile `docs/product/.session.md` against the spec's own
edit clock and the Decision Register.

`.session.md` is BOTH a legitimate resume source AND an authorised assume-source:
GATE-NEVER-ASSUME lets the skill assume a value the PO already gave in `.session.md`.
That dual role is the hazard. A session frozen at date D keeps asserting facts that
artifacts edited after D — or decisions ruled after D — have since moved past, so a
new session that assumes from a stale `.session.md` can silently reverse an approved
fact. This module is the deterministic detector behind the staleness guard.

SCRIPT-vs-LLM split (CLAUDE.md): it owns NO prose judgment. It compares committed
DATES only and lists candidates; the LLM/PO judges whether a session line actually
contradicts a ruling. Two signals:

  - staleness: `.session.md` `updated` < the newest artifact `updated`. The session
    predates a spec edit, so its facts may be stale.
  - supersede candidates: active DEC records dated AFTER `.session.md` `updated` —
    rulings the session snapshot could not have reflected. Per Q5, decisions.md is
    the authority when the two diverge; the session is NEVER auto-rewritten — the
    conflict is surfaced (no-silent-reversal).

Fail-soft everywhere: an absent `.session.md`, an absent/unparseable `updated`, or an
empty register all yield "nothing to flag", never a crash. All findings are `warn`
(an advisory nudge, never a hard gate).

CLI:
    session_staleness.py --root <project-dir>
        Prints the sweep JSON {session_updated, stale, newest_artifact,
        superseding_decisions, authoritative_source}. Always exits 0.
"""

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from encoding_utils import configure_utf8_console, emit_json
from frontmatter_parser import parse_text
from spec_graph import build_graph
from check_consistency_time import parse_iso_date
from dec_ledger import list_decisions

configure_utf8_console()


def list_active(root) -> List[Dict[str, Any]]:
    """Records with `status: active` in the per-workspace DEC ledger
    (`dec_ledger.list_decisions`) — the rulings still in force.

    Deviation from the harness's own `decision_register.list_active`: this
    workspace has no `decision_register.py` module (superseded by
    `dec_ledger.py`'s per-workspace grep+1-under-flock ledger), so the active-status
    filter is applied here instead of imported. `dec_ledger.list_decisions`
    parses only the YAML frontmatter block (id/status/date/actor/ts/affects);
    it carries no `title` field (that lives in the `## DEC-n — <title>`
    heading, which this ledger's reader does not parse), so a record's
    `title` here is always empty — the superseding-decisions surface degrades
    to id+date+affects, which is enough to name the candidate for review."""
    return [r for r in list_decisions(root) if r.get("status") == "active"]

# decisions.md is the authority when a session line and a ruling diverge (Q5). Named
# once here so the sweep payload and the validate-gate finding speak with one voice.
AUTHORITATIVE_SOURCE = "decisions.md"


def _session_path(root: Path) -> Path:
    return Path(root) / "docs" / "product" / ".session.md"


def parse_session_updated(root: Path) -> Optional[dt.date]:
    """Return the `.session.md` frontmatter `updated` as a date, or None.

    None when the file is absent/unreadable, has no YAML frontmatter, or carries an
    absent/unparseable `updated`. Routed through `frontmatter_parser.parse_text` —
    the ONE hardened reader that fail-softs on the whole PyYAML exception family
    (not just `yaml.YAMLError`/`ValueError`: an explicit-tag scalar like
    `updated: !!timestamp 'not a ts'` raises a bare `AttributeError` that a
    narrower catch here would let escape and crash the sweep). Best-effort: a
    malformed session never crashes the detector (the staleness nudge degrades
    to silence)."""
    path = _session_path(root)
    # A committed .session.md that is a FIFO/socket/device -- or a symlink to one
    # (git object mode 120000) -- would block read_text forever, hanging the
    # staleness sweep (wired into the validate gate). is_file() follows the symlink
    # but only stats, so it flags a non-regular file without reading. Fail soft to
    # None (unknown session date), the same as a missing/malformed session.
    if path.exists() and not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    parsed = parse_text(text, file_label=str(path))
    if not parsed["ok"]:
        return None
    fm = parsed["frontmatter"]  # parse_text guarantees a dict when ok is True
    updated = fm.get("updated")
    # Pass the raw value: parse_iso_date coerces a native date/datetime (PyYAML
    # parses `updated: 2026-07-14 09:00:00` to a datetime) and returns None for any
    # other type. Wrapping in str() defeated that branch — a normal timestamped
    # `updated` stringified to "2026-07-14 09:00:00", missed the ^\d{4}-..$ regex,
    # and silently dropped the artifact from the staleness sweep.
    return parse_iso_date(updated) if updated is not None else None


def newest_artifact_update(graph: Dict[str, Any]) -> Tuple[Optional[dt.date], Optional[str]]:
    """The latest `updated` date across all artifacts → (date, artifact_id).

    Nodes with an absent/unparseable `updated` are skipped. Returns (None, None) when
    no artifact carries a parseable date."""
    best: Optional[dt.date] = None
    best_id: Optional[str] = None
    for n in graph.get("nodes", []):
        raw = n.get("updated")
        if raw is None:
            continue
        d = parse_iso_date(raw)  # raw value: parse_iso_date handles date/datetime, str-wrap defeated it
        if d is None:
            continue
        if best is None or d > best:
            best, best_id = d, n.get("id")
    return best, best_id


def superseding_decisions(root: Path, session_updated: Optional[dt.date]) -> List[Dict[str, Any]]:
    """Active DEC records dated strictly AFTER the session snapshot.

    These are rulings the session could not have reflected — supersede candidates the
    PO/LLM must check the session against. Empty when the session date is unknown (no
    anchor to compare against) or the register is empty. Sorted by id for determinism."""
    if session_updated is None:
        return []
    out: List[Dict[str, Any]] = []
    for rec in list_active(root):
        d = parse_iso_date(rec.get("date"))
        if d is None or d <= session_updated:
            continue
        rec_id = rec.get("id", "")
        if not rec_id:
            # A block missing (or carrying an empty) `id:` cannot be named as
            # a candidate for the PO to review — skip it rather than crash
            # the whole sweep on a bare KeyError.
            continue
        out.append({
            "id": rec_id,
            "date": rec.get("date", ""),
            "title": rec.get("title", ""),
            "affects": rec.get("affects", ""),
        })
    # Sort by the NUMERIC suffix, not the id string: a plain string sort
    # orders a two-digit ruling before a lower-numbered single-digit one once
    # the register passes nine active rulings (the leading-digit character
    # compares before the full value does), backwards from ruling order. A
    # ledger id that somehow fails to split on "-" (should be unreachable --
    # dec_ledger only ever emits ids matching its own id-grammar pattern)
    # falls back to the string itself rather than crashing the sweep.
    def _numeric_key(rec: Dict[str, Any]):
        rid = rec["id"]
        try:
            return (0, int(rid.split("-", 1)[1]))
        except (IndexError, ValueError):
            return (1, rid)
    out.sort(key=_numeric_key)
    return out


def sweep(root) -> Dict[str, Any]:
    """The full session↔(spec, register) reconciliation for `root`.

    The deterministic payload behind the `--validate` supersede-sweep surface. Builds the
    graph internally so the CLI is standalone. `stale` is True iff the session predates
    the newest artifact edit; `superseding_decisions` lists post-session rulings."""
    root = Path(root).resolve()
    session_updated = parse_session_updated(root)
    graph = build_graph(root)
    newest, newest_id = newest_artifact_update(graph)

    stale = bool(session_updated and newest and session_updated < newest)
    return {
        "session_updated": session_updated.isoformat() if session_updated else None,
        "stale": stale,
        "newest_artifact": (
            {"id": newest_id, "updated": newest.isoformat()} if newest else None
        ),
        "superseding_decisions": superseding_decisions(root, session_updated),
        "authoritative_source": AUTHORITATIVE_SOURCE,
    }


def staleness_findings(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate-gate `warn` findings for a stale / superseded session.

    Reads the project root from `graph["root_path"]` (same contract as the other
    session check). Emits at most two findings — one `session_stale` (session predates
    the newest artifact edit) and one `session_superseded` (post-session rulings the
    session may contradict) — so a long register never floods the gate. Returns [] when
    there is no root, no session date, or nothing to flag."""
    root_raw = graph.get("root_path")
    if not root_raw:
        return []
    root = Path(root_raw)
    session_updated = parse_session_updated(root)
    if session_updated is None:
        return []

    findings: List[Dict[str, Any]] = []
    newest, newest_id = newest_artifact_update(graph)
    if newest and session_updated < newest:
        findings.append({
            "check": "session_stale",
            "severity": "warn",
            "artifact_id": None,
            "file": "docs/product/.session.md",
            "detail": (
                f".session.md updated {session_updated.isoformat()} predates the newest "
                f"artifact edit ({newest_id} updated {newest.isoformat()}); its facts may "
                f"be stale — re-read before assuming from it."
            ),
            "context": {
                "session_updated": session_updated.isoformat(),
                "newest_artifact": newest_id,
                "newest_updated": newest.isoformat(),
            },
        })

    supersed = superseding_decisions(root, session_updated)
    if supersed:
        ids = ", ".join(d["id"] for d in supersed)
        findings.append({
            "check": "session_superseded",
            "severity": "warn",
            "artifact_id": None,
            "file": "docs/product/.session.md",
            "detail": (
                f".session.md (updated {session_updated.isoformat()}) predates "
                f"{len(supersed)} decision(s) [{ids}]; {AUTHORITATIVE_SOURCE} is "
                f"authoritative — verify the session does not contradict them."
            ),
            "context": {
                "authoritative_source": AUTHORITATIVE_SOURCE,
                "decisions": supersed,
            },
        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    emit_json({"schema_version": "1.0", **sweep(args.root)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
