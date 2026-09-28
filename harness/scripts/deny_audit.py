#!/usr/bin/env python3
"""deny_audit.py — the 3-event deny-list audit surface + the SOFT-only widen request.

Reuses trace_log's chain_hash store (no new audit store is invented): emit_* wrap
append_event with the write_deny_policy event constants; read_deny_events / verify_chain
read that store back; the widen CLI appends a widen_request ONLY for a soft-tier path
— the hard floor has no appeal, so a core / harness-binary path is refused. Applying a
widen is a HUMAN edit of the guarded write-deny-policy.yaml, never an agent self-grant.

Honesty: the keyless chain_hash is tamper-EVIDENT, not tamper-PROOF — it holds only
because harness/state/** is not agent-writeable (a shell/tool write there is blocked by
the floor), so an actor cannot rewrite its own trail. No key/HMAC is claimed.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
_HOOKS = _HERE.parent / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.append(str(_HOOKS))

import trace_log  # noqa: E402 — reuse the chain_hash store
import deny_matcher  # noqa: E402 — the widen gate reuses the matcher (one SSOT)
import write_deny_policy as wdp  # noqa: E402 — event constants + policy
import write_guard  # noqa: E402 — root resolution

_HOOK = "deny_audit"
_DENY_EVENTS = (wdp.EVENT_HARD_BLOCK, wdp.EVENT_SOFT_HIT, wdp.EVENT_WIDEN)
_POLICY_REL = "harness/data/write-deny-policy.yaml"


def _actor(session=None):
    try:
        import hook_runtime
        return hook_runtime.resolve_actor(session_id=session)
    except Exception:  # noqa: BLE001
        return None


def emit_hard_block(*, path, actor=None, session=None, tool=None, reason=None) -> None:
    """Record a hard-tier block. Fail-open — the audit must never brick the lane."""
    try:
        trace_log.append_event(
            hook=_HOOK, event=wdp.EVENT_HARD_BLOCK, actor=actor or _actor(session),
            session=session, tool=tool, status="BLOCKED", target=str(path), note=reason)
    except Exception:  # noqa: BLE001
        pass


def emit_soft_hit(*, path, actor=None, session=None, tool=None, matched_rule=None) -> None:
    """Record a soft-tier (detective) hit. Fail-open."""
    try:
        trace_log.append_event(
            hook=_HOOK, event=wdp.EVENT_SOFT_HIT, actor=actor or _actor(session),
            session=session, tool=tool, status="OBSERVED", target=str(path),
            note="soft_rule=%s" % matched_rule)
    except Exception:  # noqa: BLE001
        pass


def emit_widen_request(*, path, reason, actor=None, session=None) -> None:
    """Record a request to widen the SOFT tier. Caller gates the tier first."""
    try:
        trace_log.append_event(
            hook=_HOOK, event=wdp.EVENT_WIDEN, actor=actor or _actor(session),
            session=session, status="REQUEST", target=str(path), note=reason)
    except Exception:  # noqa: BLE001
        pass


def _policy():
    bin_root = write_guard._bin_root()
    try:
        soft = wdp.load_soft_rules(Path(bin_root) / _POLICY_REL)
    except wdp.DenyPolicyError:
        soft = []
    return bin_root, wdp.assemble_policy(soft)


def _is_hard_tier(path) -> bool:
    bin_root, policy = _policy()
    decision = deny_matcher.evaluate(path, policy, [bin_root])
    return decision.tier in (wdp.TIER_CORE, wdp.TIER_HARD_BINARY)


def _day_str(day=None) -> str:
    return day or datetime.now(timezone.utc).strftime("%Y%m%d")


def _trace_files(day):
    d = trace_log._trace_dir()
    if not d.is_dir():
        return []
    return sorted(d.glob("trace-%s*.jsonl" % day))


def read_deny_events(day=None) -> list:
    """Every deny/soft/widen record for the day, across legacy + per-session shards."""
    out = []
    for f in _trace_files(_day_str(day)):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("event") in _DENY_EVENTS:
                out.append(rec)
    return out


def verify_chain(day=None) -> bool:
    """Re-derive each trace file's chain_hash from genesis and confirm continuity.
    A per-session shard roots at None (its own genesis), so a tampered record — or a
    dropped/inserted line — breaks the chain and returns False."""
    for f in _trace_files(_day_str(day)):
        prev = None
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            return False
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                return False
            stored = rec.get("chain_hash")
            if stored is None or trace_log._chain_hash(prev, rec) != stored:
                return False
            prev = stored
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="deny_audit")
    parser.add_argument("--request-widen", metavar="PATH",
                        help="append a SOFT-tier widen request (the hard floor has no appeal)")
    parser.add_argument("--reason", default="")
    parser.add_argument("--list", action="store_true", help="print the day's deny events")
    parser.add_argument("--verify-chain", action="store_true")
    parser.add_argument("--day", help="YYYYMMDD (default: today, UTC)")
    args = parser.parse_args(argv)

    if args.request_widen:
        path = args.request_widen
        if _is_hard_tier(path):
            sys.stderr.write(
                "refused: '%s' is on the hard floor (protected core or the harness "
                "binary) — the hard floor has no appeal; only the soft tier can be "
                "widened.\n" % path)
            return 2
        emit_widen_request(path=path, reason=args.reason)
        sys.stdout.write(
            "widen_request appended for '%s'. Applying it is a human edit of "
            "harness/data/write-deny-policy.yaml (guarded config), not an agent "
            "self-grant.\n" % path)
        return 0

    if args.verify_chain:
        ok = verify_chain(args.day)
        sys.stdout.write("chain: %s\n" % ("OK" if ok else "BROKEN"))
        return 0 if ok else 1

    if args.list:
        for rec in read_deny_events(args.day):
            sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
