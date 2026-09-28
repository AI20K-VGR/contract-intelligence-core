#!/usr/bin/env python3
"""rule_audit_cache.py — content-hash cache over the rule conflict audit.

The conflict audit (user_override.detect_conflicts of the layer-b new rules vs
the shipped operational std rules) is advisory, but re-running it on every review
load is wasteful. This cache re-audits ONLY when a rule actually changed:

  - a layer-b override added/removed/edited (per-rule fingerprint of each
    override entry + the id set),
  - a shipped operational rule's content_hash changed,
  - an override-SOURCE file changed (a folder file or the legacy root file) even
    if the merged override set looks identical.

A cache hit returns the stored conflicts without calling detect_conflicts. The
cache record lives at harness/state/rule-audit-cache.json (gitignored runtime
state). This is a REVIEW/author-time helper — it is never wired into the gate
hot-path (artifact_check._coverage_check), which loads rules conflict-free.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import standards_graph
import user_override
from graph_core import _content_fingerprint

import harness_paths
import rule_view

CACHE_NAME = "rule-audit-cache.json"


def _shipped_rules(root) -> List[Dict[str, Any]]:
    """Every shipped operational rule-leaf (pre-override), each carrying its
    content_hash — the drift signal for a shipped-rule edit."""
    graph = standards_graph.build_graph(Path(root))
    return rule_view._all_operational_rule_nodes(graph)


def _user_rules(shipped: List[Dict[str, Any]],
                overrides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The layer-b NEW-id rules (an override that adds a rule, not one that
    modifies a shipped rule in place) as rule-like dicts for detect_conflicts."""
    shipped_ids = {r.get("id") for r in shipped}
    out: List[Dict[str, Any]] = []
    for o in overrides:
        rid = o.get("rule_id") or o.get("id")
        if rid and rid not in shipped_ids:
            out.append({"id": rid, "scope": o.get("scope") or [],
                        "severity": o.get("severity"),
                        "relates_to_std": o.get("relates_to_std") or []})
    return out


def _per_rule_hashes(shipped: List[Dict[str, Any]],
                     overrides: List[Dict[str, Any]]) -> Dict[str, str]:
    """Per-rule fingerprints: a shipped rule keyed by its id -> content_hash, a
    layer-b override keyed `override:<id>` -> fingerprint of its entry. Add/
    remove shifts the key set; an edit shifts exactly that key's value."""
    h: Dict[str, str] = {}
    for r in shipped:
        rid = r.get("id")
        if rid:
            h[rid] = r.get("content_hash")
    for o in overrides:
        rid = o.get("rule_id") or o.get("id")
        if rid:
            h["override:%s" % rid] = _content_fingerprint([o])
    return h


def _source_digest(root) -> List[List[str]]:
    """A (name, sha256) pair per override-source file so a file add/remove/edit
    is detected even when the merged override set is unchanged."""
    pairs: List[List[str]] = []
    for p in user_override._override_sources(root):
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        except (FileNotFoundError, OSError):
            continue
        pairs.append([p.name, digest])
    return sorted(pairs)


def _cache_path() -> Path:
    """Where the audit record lives — the state dir, unless told otherwise.

    HARNESS_RULE_AUDIT_CACHE_DIR exists for one caller: a test suite that gives
    every test its own state dir. The audit costs 17.0s cold against 0.07s warm,
    so a cache keyed to a per-test directory is never warm and every test pays
    the full price — measured at 16.8s per test, which crossed the coverage
    cell's 120s per-test ceiling.

    Safe to share because this record is a pure function of committed rule FILES
    (their content hashes plus the override sources' digests). It carries no
    actor, no session and nothing one test could leak into another — unlike the
    audit ledger the isolation exists to protect, which is exactly why the two
    are separated here rather than by loosening that isolation.
    """
    override = os.environ.get("HARNESS_RULE_AUDIT_CACHE_DIR")
    if override:
        return Path(override) / CACHE_NAME
    return harness_paths.state_dir() / CACHE_NAME


def _read_cache(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _write_cache(path: Path, rec: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8")


def audit_or_cached(root) -> Dict[str, Any]:
    """Return the conflict-audit record, re-running detect_conflicts only when a
    rule changed. Record shape: {agg_hash, per_rule, conflicts, ts}."""
    shipped = _shipped_rules(root)
    overrides = user_override.load(root)
    per_rule = _per_rule_hashes(shipped, overrides)
    agg = _content_fingerprint([per_rule, _source_digest(root)])

    path = _cache_path()
    cached = _read_cache(path)
    if cached.get("agg_hash") == agg and "conflicts" in cached:
        return cached

    conflicts = user_override.detect_conflicts(_user_rules(shipped, overrides), shipped)
    rec = {"agg_hash": agg, "per_rule": per_rule, "conflicts": conflicts,
           "ts": datetime.now(timezone.utc).isoformat()}
    _write_cache(path, rec)
    return rec
