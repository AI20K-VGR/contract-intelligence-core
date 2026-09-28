#!/usr/bin/env python3
"""decision_confirm — a hash-bound, single-use confirm token for a cross-scope
decision flip.

POSTURE (hard, do not soften in prose): this is tamper-EVIDENT + raise-the-price,
the same model as plan_approval.py — it does NOT authenticate. An agent running
this CLI can mint its own token; the token does not prove a human consented. What
it DOES guarantee: a cross-scope flip can never happen *silently* — it always
leaves a token file + a trace event, and a generic/stale token cannot cover a
different flip (the token binds (target, neighbors_digest), is TTL-bound, and is
consumed on use). The real human gate is hs:remember's AskUserQuestion; this
token is the floor against a silent direct flip. The floor is tamper-EVIDENT,
never tamper-proof; it never authenticates and never claims absolute certainty.

now is injected as an epoch-second float param (R3) — NOT HARNESS_NOW, which is
date-only (artifact_check) and cannot test a second-grained TTL.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import decision_neighbors  # noqa: E402 — sibling; reuse neighbors_digest (DRY)

# trace_log lives in harness/hooks; insert that dir BEFORE the import or the first
# run ImportErrors (R9 — the same _HOOKS_DIR dance decision_register uses).
_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import trace_log  # noqa: E402

import yaml_io  # noqa: E402

_SCHEMA = "decision-confirm/v1"
_STATE_REL = ("harness", "state", "decision-confirm")

# target is caller-supplied and becomes part of the token FILENAME, so it is
# held to the same charset claims.py applies to its own task_id. Deliberately a
# charset check, not a `DEC-<n>` shape check: containment is what is needed
# here, and the plan-local DEC-A2-* series is a legitimate target — narrowing
# the id grammar would break a real caller to buy nothing extra.
_TARGET_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_TARGET_MAX = 200


def _validate_target(target) -> str:
    """Return ``target`` if it is safe to place in a filename, else raise.
    Called from _token_path, the single choke point both the write and the
    verify side pass through."""
    if not isinstance(target, str) or not target or target in (".", "..") \
            or not _TARGET_RE.match(target) or len(target) > _TARGET_MAX:
        raise ValueError(
            "invalid target %r — allowed: 1-%d chars of [A-Za-z0-9._-], no "
            "path separators, not '.' or '..'" % (target, _TARGET_MAX))
    return target


def _state_dir(root) -> Path:
    """Confirm-token dir under the runtime state fence. Rides the shared state
    env seams (HARNESS_STATE_DIR > HARNESS_DATA_ROOT/state) so a global install
    lands tokens project-side in `.harness/state`; the explicit `root` arg is the
    legacy/test fallback honored only when no state env is set. (A bare call to
    harness_paths.state_dir() would ignore `root` and break the root-param test
    seam, so the two env tiers are mirrored here instead.)"""
    st = os.environ.get("HARNESS_STATE_DIR")
    if st:
        return Path(st) / "decision-confirm"
    data = os.environ.get("HARNESS_DATA_ROOT")
    if data:
        return Path(data) / "state" / "decision-confirm"
    return Path(root).joinpath(*_STATE_REL)


def _token_path(root, target: str, digest: str) -> Path:
    """Token file under the state fence, resolved off root (never CWD). Filename
    binds target + digest so two flips never collide."""
    return _state_dir(root) / ("%s-%s.yaml" % (_validate_target(target), digest))


def _trace(event: str, **kw) -> None:
    try:
        trace_log.append_event("decision_confirm", event, **kw)
    except Exception:  # noqa: BLE001 — tracing must never break the decision
        pass


def write_confirm(root, target: str, cross_scope_ids: List[str],
                  *, now: Optional[float] = None) -> Dict:
    """Mint a token binding (target, digest-of-cross-scope-set). Overwrites any
    prior token for the same (target, set) — a re-confirm refreshes the clock."""
    now = time.time() if now is None else now
    digest = decision_neighbors.neighbors_digest(cross_scope_ids)
    payload = {
        "schema": _SCHEMA,
        "target": target,
        "neighbors_digest": digest,
        "cross_scope": sorted(cross_scope_ids),
        "actor": _actor(),
        "ts": float(now),
    }
    p = _token_path(root, target, digest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml_io.safe_dump(payload, sort_keys=False, allow_unicode=True),
                 encoding="utf-8")
    _trace("decision_flip_confirm_written", target=target, note=digest)
    return payload


def verify_and_consume(root, target: str, cross_scope_ids: List[str],
                       *, ttl_s: int, now: Optional[float] = None) -> bool:
    """True iff a matching, unexpired token exists — and consume it (single-use).
    Match = same target AND same digest (so the token covers EXACTLY this
    cross-scope set). Any read/parse failure → False (fail-safe: no token, no
    pass). The token is deleted on a successful match so a second flip re-blocks."""
    now = time.time() if now is None else now
    digest = decision_neighbors.neighbors_digest(cross_scope_ids)
    p = _token_path(root, target, digest)
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, yaml_io.YAMLError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("target") != target or data.get("neighbors_digest") != digest:
        return False
    try:
        ts = float(data.get("ts"))
    except (TypeError, ValueError):
        return False
    if now - ts > ttl_s:
        return False  # expired — treat as absent
    # consume: a single-use token can never cover a second flip
    try:
        p.unlink()
    except OSError:
        pass
    _trace("decision_flip_confirmed", target=target, note=digest)
    return True


def _actor() -> str:
    try:
        import hook_runtime
        return hook_runtime.resolve_actor()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--confirm", action="store_true",
                    help="mint a confirm token for a cross-scope flip")
    ap.add_argument("--target", required=True, help="DEC-<n> being superseded")
    ap.add_argument("--neighbors", default="",
                    help="comma-separated cross-scope DEC ids this token covers")
    args = ap.parse_args(argv)

    cross = [s.strip() for s in args.neighbors.split(",") if s.strip()]
    if not args.confirm:
        print(json.dumps({"error": "invalid_input",
                          "message": "only --confirm is supported"}, ensure_ascii=False))
        return 0
    try:
        payload = write_confirm(args.root, args.target, cross)
    except ValueError as e:
        print(json.dumps({"error": "invalid_input", "message": str(e)},
                         ensure_ascii=False))
        return 2
    print(json.dumps({"written": True, "target": payload["target"],
                      "neighbors_digest": payload["neighbors_digest"],
                      "cross_scope": payload["cross_scope"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
