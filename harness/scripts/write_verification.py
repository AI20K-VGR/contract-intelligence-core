#!/usr/bin/env python3
"""write_verification.py — deterministic, preferred write path for a plan's
verification artifact.

The PostToolUse hook (phase_progress_writer.py) only snapshots a verification
written through the Write tool. A verification written from Bash never trips the
hook, so it gets no per-phase snapshot and no lifecycle flip — the plan sticks at
"not done" and the ship gate blocks. This script closes that hole: it writes the
canonical verification, drives the SAME shared snapshot + lifecycle as the hook
(verification_snapshot.py — no logic duplicated), then self-verifies, in one run.

Two input modes (mutually exclusive):
  flag-builder:  --phase p1 --stage ship --verdict PASS --check unit:PASS ...
                 (actor + ts auto-filled)
  --from FILE|-  read a composed YAML/JSON record (- = stdin); missing
                 actor/ts/plan are filled.

The phase must be a real node in the plan's plan-graph.yaml: a casing typo
(P1 vs p1) would snapshot to verification-P1.json, never match node p1, and the
plan would never reach N/N — exactly the class of bug this path exists to kill.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS = os.path.dirname(os.path.abspath(__file__))
if _THIS not in sys.path:
    sys.path.insert(0, _THIS)
_HOOKS = str(Path(__file__).resolve().parent.parent / "hooks")
if _HOOKS not in sys.path:
    sys.path.append(_HOOKS)
import verification_snapshot as vsnap  # noqa: E402
import plan_graph  # noqa: E402
import test_policy  # noqa: E402
from hook_runtime import resolve_actor  # noqa: E402

_VERDICTS = {"PASS", "PASS_WITH_RISK", "BLOCKED"}
_USAGE = (
    "usage: write_verification.py <plan_dir> "
    "(--phase ID --verdict V [--stage S] [--check name:status ...] | --from FILE|-)")


def _die(msg, code=2):
    sys.stderr.write("error: %s\n%s\n" % (msg, _USAGE))
    raise SystemExit(code)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _parse_checks(items):
    checks = []
    for it in items or []:
        name, sep, status = it.partition(":")
        if not name or not sep or not status:
            _die("bad --check %r — expected name:status" % it)
        checks.append({"name": name, "status": status})
    return checks


def _json_or_die(raw):
    """json.loads with a friendly _die on malformed input — the YAML fallback path
    must not surface a raw JSONDecodeError traceback to the caller."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        _die("--from source is not valid JSON/YAML: %s" % e)


def _read_from(src):
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    # JSON is a strict subset of YAML 1.1 for our records; one parser handles both.
    try:
        import yaml_io
        rec = yaml_io.safe_load(raw)
    except ImportError:
        rec = _json_or_die(raw)
    except (yaml_io.YAMLError, ValueError):
        # PyYAML's timestamp/int constructors raise a bare ValueError (not a
        # YAMLError subclass) on an out-of-range value like `ts: 2024-13-45`;
        # treat both as a parse failure, matching artifact_check._parse_artifact_text.
        rec = _json_or_die(raw)
    if not isinstance(rec, dict):
        _die("--from source is not a mapping/object")
    return rec


def _build_record(args, plan_name):
    if args.from_src is not None:
        if args.phase or args.stage or args.verdict or args.check:
            _die("--from is mutually exclusive with --phase/--stage/--verdict/--check")
        rec = _read_from(args.from_src)
    else:
        if not args.phase or not args.verdict:
            _die("missing --phase/--verdict (or use --from)")
        rec = {
            "stage": args.stage or "cook",
            "plan": plan_name,
            "checks": _parse_checks(args.check),
            "verdict": args.verdict,
            "phase": args.phase,
        }
    rec.setdefault("plan", plan_name)
    # Guard the CALLS, not just the result: setdefault always evaluates its arg, so
    # the bare form shells out to git (resolve_actor) even when actor is present.
    if "actor" not in rec:
        rec["actor"] = resolve_actor()
    if "ts" not in rec:
        rec["ts"] = _now_iso()
    if rec.get("verdict") not in _VERDICTS:
        _die("verdict must be one of %s" % sorted(_VERDICTS))
    if not rec.get("phase"):
        _die("record has no phase")
    return rec


def _check_phase_is_node(plan_dir, phase):
    """Reject a phase that is not a plan-graph node. Degrade (warn + allow) only
    when the graph itself can't be parsed — never silently accept a bad phase
    against a graph that parsed fine."""
    graph = plan_graph.parse_phase_graph(plan_dir)
    if "error" in graph:
        sys.stderr.write("[advisory] plan-graph unparsable (%s) — skipping phase "
                         "node check\n" % graph["error"])
        return
    nodes = plan_graph._all_nodes(graph)
    if phase not in nodes:
        _die("phase %r is not a plan-graph node; valid nodes: %s"
             % (phase, sorted(nodes)))


_LEGAL_STATUSES = ("PASS", "FAIL", "SKIP", "BLOCKED")


def _invalid_statuses(rec) -> list:
    """Check statuses outside the schema enum, as human-readable strings.

    The enum used to be {PASS, FAIL, SKIP}, and nothing enforced it at write time
    — so six spellings appeared in live artifacts (BLOCKED, UNMEASURED, UNOWNED,
    UNPROVABLE, DEFERRED_TO_MAIN_TREE, BLOCKED_NO_LLM_NETWORK). They were not
    carelessness: FAIL means "measured, and it is wrong", and people needed a way
    to say "could not measure at all". Those are different facts and a reader has
    to tell them apart, so BLOCKED is now first-class and names the hole.

    BLOCKED is a vocabulary change, NOT a weakening: it is absent from the gate's
    PASS/SKIP allowlist, so it stops a hard stage exactly like FAIL. What it buys
    is a report that can count holes separately from defects.

    Everything else is rejected here, at write time, naming the legal set — an
    off-enum status used to travel silently until a gate blocked on it weeks later
    with no hint of what the writer had actually meant.
    """
    bad = []
    for c in rec.get("checks") or []:
        if not isinstance(c, dict):
            bad.append("a check entry is not a mapping: %r" % (c,))
            continue
        st = c.get("status")
        if st not in _LEGAL_STATUSES:
            bad.append(
                "check %r has status %r — legal values are %s. Use BLOCKED when "
                "the check could not be measured at all (missing tool, no network, "
                "not yet owned); FAIL means it ran and came back wrong."
                % (c.get("name", "?"), st, "/".join(_LEGAL_STATUSES)))
    return bad


def _validate_check_names(rec):
    """Apply the off|soft|hard ramp to check names not in test-policy test_types.
    Resolution can't be self-contradictory: the mode lives INSIDE the policy, so
    a load failure can't be classified as hard — it degrades to soft (warn, still
    write), never off (off would swallow the very signal test-policy exists for).
    Only enforce hard when the policy actually parsed and said hard."""
    try:
        policy = test_policy.load_test_policy()
    except test_policy.TestPolicyError as e:
        sys.stderr.write(
            "[advisory] write_verification: test-policy đọc-lỗi (%s) — đang chạy "
            "soft mặc định, KHÔNG kiểm được tên check. Sửa config để bật lại "
            "kiểm tên.\n" % e)
        return  # degrade to soft: do not block on a broken config

    mode = policy.get("check_name_validation", "soft")
    if mode == "off":
        return
    valid = set((policy.get("test_types") or {}).keys())
    unknown = [c.get("name") for c in (rec.get("checks") or [])
               if c.get("name") not in valid]
    if not unknown:
        return
    listing = "{%s}" % ", ".join(sorted(valid))
    msg = ("write_verification: check name(s) %s KHÔNG nằm trong test-policy "
           "test_types %s. Tên sai = DoD gate sẽ KHÔNG thấy kết quả này → ship "
           "rớt dù test xanh. Sửa tên ngay, đừng để cổng bắt sau."
           % (sorted(unknown), listing))
    if mode == "hard":
        _die(msg, code=1)
    sys.stderr.write("[advisory] %s\n" % msg)  # soft: warn loudly, still write


def _canonical_target(plan_dir):
    """The canonical file the snapshot loader will read (.yaml preferred, .json
    legacy). When neither exists, default to .json (the snapshot output form)."""
    art = plan_dir / "artifacts"
    yaml_p, json_p = art / "verification.yaml", art / "verification.json"
    if yaml_p.exists():
        return yaml_p, json_p
    return json_p, yaml_p


def _atomic_write(target, rec):
    # Route through the shared gate-artifact writer: it stamps run_seq (D1) from the
    # orchestrator-exported env and does the same-dir .tmp + same-volume assert +
    # os.replace this used to do inline. Thin wrapper so _self_verify + callers are
    # untouched; a dev without an orchestrator gets run_seq:null (back-compat).
    import artifact_io
    artifact_io.stamp_and_write(target, rec)


def _self_verify(plan_dir, rec):
    """After snapshot, confirm the per-phase snapshot reflects THIS write.
    (a) match -> OK; (b) absent + THIS write is PASS -> nonzero exit, a
    script-path regression (a PASS write must always leave a snapshot behind);
    (c) absent + THIS write is non-PASS -> nothing to compare against, silent
    (a BLOCKED phase that never earned a PASS has no snapshot by design — that
    is not a regression); (d) present but different -> first-wins kept the old
    record (or a later regression superseded it), so THIS write did not take —
    surface it loudly, not a silent OK, on EITHER a PASS or a non-PASS write."""
    phase = vsnap._safe_phase(rec.get("phase"))
    if phase is None:
        return
    snap = plan_dir / "artifacts" / ("verification-%s.json" % phase)
    if not snap.exists():
        if rec.get("verdict") in vsnap._PASS_VERDICTS:
            _die("self-verify: PASS+phase written but snapshot %s is missing — "
                 "the script write path failed to snapshot" % snap.name, code=1)
        return  # non-PASS with no prior PASS snapshot: nothing to compare
    try:
        got = json.loads(snap.read_text(encoding="utf-8"))
    except Exception:
        return
    if got.get("verdict") == rec.get("verdict") and got.get("phase") == rec.get("phase"):
        return
    sys.stderr.write(
        "[advisory] write_verification: snapshot %s already exists with a "
        "different verdict/phase — THIS write did NOT take (first-wins). Delete "
        "the old snapshot if you intend to overwrite it.\n" % snap.name)


def _write_phase_latest_marker(plan_dir, rec):
    """artifacts/phase-latest-<phase>.json — an always-overwritten marker of the
    LATEST verdict written for this phase via this script, independent of
    vsnap.snapshot()'s deliberately immutable, ratified first-wins policy for
    verification-<phase>.json. derive_plan_completion cross-checks it so a phase that
    regresses PASS -> BLOCKED after already earning its snapshot cannot still be
    counted complete, even once a LATER phase's write overwrites the plan's one
    canonical verification.json (the only other on-disk trace of the regression).
    Deliberately does not start with `verification-` (the prefix every existing
    verification-*.json glob in this codebase filters on) so it can never be
    mistaken for a snapshot by an older reader."""
    phase = vsnap._safe_phase(rec.get("phase"))
    if phase is None:
        return
    target = plan_dir / "artifacts" / ("phase-latest-%s.json" % phase)
    import artifact_io
    artifact_io.atomic_write_text(
        target, json.dumps({"phase": phase, "verdict": rec.get("verdict"),
                            "ts": rec.get("ts")}, ensure_ascii=False, indent=2))


def _trace(rec):
    try:
        import trace_log
        trace_log.append_event("write_verification", "verification_write",
                               target=rec.get("plan", ""),
                               status=rec.get("verdict", ""))
    except Exception:
        pass  # telemetry: best-effort, never blocks the write


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, usage=_USAGE)
    ap.add_argument("plan_dir")
    ap.add_argument("--from", dest="from_src")
    ap.add_argument("--phase")
    ap.add_argument("--stage")
    ap.add_argument("--verdict")
    ap.add_argument("--check", action="append", default=[])
    args = ap.parse_args(argv)

    plan_dir = Path(args.plan_dir).resolve()
    rec = _build_record(args, plan_dir.name)
    _check_phase_is_node(plan_dir, rec["phase"])
    bad_status = _invalid_statuses(rec)
    if bad_status:
        # Hard, unlike the check-NAME ramp above: a name typo degrades a gate
        # reading, an off-enum status is a record no reader can interpret at all.
        _die("write_verification: %s" % "\n  ".join(bad_status), code=1)
    _validate_check_names(rec)  # off|soft|hard ramp — hard exits before any write

    target, sibling = _canonical_target(plan_dir)
    _atomic_write(target, rec)
    # Exactly one canonical on disk: drop a stale sibling in the other format so
    # the loader can't read an older verdict than the one just written (C1).
    if sibling.exists():
        try:
            sibling.unlink()
        except OSError:
            pass  # best-effort: stale sibling is non-critical

    # Written before snapshot()/drive_lifecycle() so derive_plan_completion sees
    # THIS write's true verdict for this phase before any auto-close decision.
    _write_phase_latest_marker(plan_dir, rec)
    vsnap.snapshot(plan_dir)
    # Only drive the lifecycle of the plan this record is bound to — a record
    # whose plan field points elsewhere must not close THIS plan.
    if rec.get("plan") == plan_dir.name and vsnap.auto_finalize_enabled():
        vsnap.drive_lifecycle(plan_dir)

    _self_verify(plan_dir, rec)
    _trace(rec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
