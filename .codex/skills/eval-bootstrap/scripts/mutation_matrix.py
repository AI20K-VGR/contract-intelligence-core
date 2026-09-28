#!/usr/bin/env python3
"""mutation_matrix.py — deterministic 3-layer mutation matrix from eval_config.json.

Meta-tests the eval GATE itself (check_p0_gates + the maturity/threshold
verdict), not the pipeline under eval. The unit broken is a SCORED AXIS (any
field/label/measure that feeds the verdict, not just an extraction field);
the layer broken is EVIDENCE (a copy of ground truth, or a synthetic result
list fed straight into score()) — never the running system.

Three layers, each with a falsifiable expectation:
  p0        — violate one p0_rules[i] -> the gate MUST block (exit 1),
              regardless of the overall maturity score.
  threshold — push the composite maturity to exactly threshold-epsilon
              (must exit 1) and threshold+epsilon (must exit 0), for every
              key in the card's epsilon map.
  noise     — perturb a non-p0 field so it still matches after the runner's
              generic normalize (case/whitespace only) -> the gate MUST NOT
              panic (exit 0).

Coverage-first: every p0 rule must carry >=1 mutation that can kill it — a
card mutation entry (case_matrix[].mutations[] with kills == "p0:<i>") takes
priority; otherwise a rule with a `target_axis` gets a mechanically derived
gt-mutation. A rule with NEITHER is UNKILLABLE and `generate` refuses (exit
4) rather than silently under-covering — an unkillable rule is an unproven
rule.

target_axis contract (this generator's own reading, since the schema leaves it opaque):
this generator treats `target_axis` as the NAME of a `case_matrix[].expect`
field (equivalently a `ground_truth.json` items[].ground_truth key) — the
same field the generic runner (runner.py.tmpl) compares per-case. A rule
without a target_axis can still be covered via a card-declared mutation
using ANY vehicle.

Three vehicles:
  code   — break the SOURCE itself (the pipeline_mirror or the check_p0_gates
           body), from a reviewer-approved patch point on the card
           (code_mutations[]): the gt/record vehicles break EVIDENCE fed into
           the gate, this one breaks the gate's own code so a mirror/scorer
           that never actually enforces its rule is caught. Deterministic —
           the generator only COPIES the approved patch, it never invents one.
  gt     — copy ground_truth.json, patch one case's one field, run the
           stamped run_production_evals.py as a real subprocess, compare its
           exit code (same pattern as harness/e2e/run_eval_bootstrap_slice.py
           slice1: block-then-pass via subprocess, not import-cheating).
  record — for an axis with no ground-truth file (a threshold/epsilon probe,
           or a measured axis), a generated driver imports the domain's
           scorer.py and monkeypatches score_dimension to a fixed, mechanically
           derived value per dimension (uniform across dimensions works
           because DIMENSIONS weights always sum to 100 — see
           _gen_threshold_mutations), then calls score([]) and exits on
           `passed`. The driver + a copy of scorer.py/config_integrity.py run
           from a NESTED evals/eval_types/<domain>/ tree (card at
           evals/eval_config.json) inside a temp workspace, because
           config_integrity's `load_verified_config()` resolves the card via
           `Path(__file__).resolve().parents[2]` — a flat scratch dir cannot
           satisfy that.

Exit codes (generate): 0 matrix written / 2 input error (bad config, hash
mismatch, malformed matrix) / 4 coverage fail (an unkillable p0 rule).
Exit codes (run): 0 every mutation matched its expectation (and the
control-baseline case passed cleanly) / 1 a mismatch — a "blind" gate (a
kill mutation that did NOT trip the expected exit 1) or a "panicky" gate (a
noise/plus mutation that wrongly tripped a red) / 2 input error (config
drift against the matrix's card_hash, missing files, bad matrix JSON).

Determinism: no randomness, no wall-clock in the matrix bytes; iteration
order is always over explicit sorted keys or the card's own list order, so
two `generate` runs on the same config produce byte-identical output.

Rule-id attribution: the domain's check_p0_gates() must return
`(passed: bool, failures: list[dict])` where each failure carries an int
`rule_index` (pinned by test_config_conformance.py.tmpl). `run` greps
the stamped CLI's stdout ("P0 FAILURE: {'rule_index': N, ...}" from
print_report) for `rule_index` occurrences and asserts the mutation for
rule[i] actually surfaces rule_index==i, not a different rule borrowing the
kill.

Env: every subprocess gets an explicit env dict with all HARNESS_* keys
scrubbed (a leaked dev-override env would corrupt the run's own posture —
memory dev-env-leak). `run` also self-proves this via a one-line probe
subprocess whose result lands in the report's meta.

Stdlib only; paths resolve off __file__ (none used directly, but no
sibling/harness/scripts import — this script never imports outside its own
skill, same discipline as eval_scaffold.py / eval_config.py).
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

from decimal import ROUND_HALF_UP, Decimal
import tempfile

from pathlib import Path

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_INPUT_ERROR = 2
EXIT_COVERAGE_FAIL = 4

_HARNESS_ENV_PREFIX = "HARNESS_"
_RULE_INDEX_RE = re.compile(r"'rule_index':\s*(-?\d+)")

# ReDoS guard for `regex_sub`'s `anchor`: it is config-sourced from a strategy
# card's `code_mutations[]` (R7-reviewed, but still data, not a source literal —
# same exposure as claim_verify.py's `rule["match"]`/`rule["assert"]`), then
# matched via `re.subn` against the REAL source file it patches (unbounded
# size, unlike `re.error`'s compile-time check which only catches a malformed
# pattern, never a slow one). This skill is stdlib-only and never imports
# outside its own directory (module docstring), so it cannot reach for the
# `regex` module's `timeout=` kwarg the way claim_verify.py/skill_config.py
# do — instead it reuses the SIGALRM wall-clock budget technique
# `harness/scripts/mechanical_runner.py` uses for the identical problem,
# reimplemented here (not imported) for the same self-containment reason.
_ANCHOR_MATCH_TIMEOUT_SECONDS = 1.0


class _AnchorTimeoutError(RuntimeError):
    """A `regex_sub` patch's `anchor` pattern exceeded the matching time budget
    against the real source it patches — almost certainly a catastrophic-
    backtracking regex smuggled into a strategy card. Raised (never silently
    swallowed) so a bad anchor fails loud instead of hanging the run."""


def _run_with_wallclock_budget(fn, seconds):
    """Run fn() under a best-effort SIGALRM wall-clock budget. Active only on
    the main thread of a POSIX interpreter; elsewhere it runs unbounded (the
    same documented limitation as mechanical_runner.py's `_run_budgeted`).
    Raises `_AnchorTimeoutError` on timeout; restores any pre-existing alarm."""
    if (seconds <= 0 or not hasattr(signal, "SIGALRM")
            or threading.current_thread() is not threading.main_thread()):
        return fn()

    def _handler(signum, frame):
        raise _AnchorTimeoutError(
            "regex_sub: anchor pattern exceeded the %.1fs match budget -- "
            "likely a catastrophic-backtracking regex" % seconds)

    prev_handler = signal.signal(signal.SIGALRM, _handler)
    started = time.monotonic()
    prev_remaining, prev_interval = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)        # cancel ours first
        signal.signal(signal.SIGALRM, prev_handler)    # restore caller's handler
        if prev_remaining > 0:                          # re-arm caller's alarm
            elapsed = time.monotonic() - started
            signal.setitimer(signal.ITIMER_REAL,
                             max(1e-6, prev_remaining - elapsed), prev_interval)


# A vehicle setup failure (bad target, invalid regex, missing source file,
# copytree failure, a syntactically broken source fill, or a `regex_sub`
# anchor that blew its ReDoS budget) is an INPUT error (exit 2), never a gate
# verdict (exit 1). re.error, shutil.Error, SyntaxError and _AnchorTimeoutError
# are NOT OSError/ValueError subclasses, so they must be named explicitly or
# they escape as a false exit-1 "gate blind".
_SETUP_ERRORS = (ValueError, OSError, re.error, shutil.Error, SyntaxError, _AnchorTimeoutError)


# -- shared: card hash / env ----------------------------------------------

def _sidecar_for(config_path: Path) -> Path:
    return config_path.parent / "eval_config.sha256"


def _verify_and_load(config_path: Path):
    """Return (card, sha256-hex). Raises ValueError naming the problem."""
    if not config_path.is_file():
        raise ValueError("config not found: %s" % config_path)
    sidecar = _sidecar_for(config_path)
    if not sidecar.is_file():
        raise ValueError("missing sidecar: %s" % sidecar)
    body = config_path.read_bytes()
    actual = hashlib.sha256(body).hexdigest()
    expected = sidecar.read_text(encoding="utf-8").strip()
    if actual != expected:
        raise ValueError(
            "card_hash mismatch: sidecar=%s actual=%s (config edited without re-approval)"
            % (expected, actual))
    try:
        card = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("config is not valid JSON: %s" % e)
    return card, actual


def _scrubbed_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith(_HARNESS_ENV_PREFIX)}


# -- generate: control-baseline pick ---------------------------------------

def _is_control_candidate(case: dict, p0_rules: list) -> bool:
    expect = case.get("expect") or {}
    for rule in p0_rules:
        axis = rule.get("target_axis")
        if not axis:
            continue
        if axis not in expect or expect[axis] is None:
            return False
        if "violation_value" in rule and expect[axis] == rule["violation_value"]:
            return False
    return True


def _pick_control(card: dict):
    """A control-baseline sample valid on EVERY axis, so an unrelated
    rule never masks a mutation's assertion. Returns (case, warning|None)."""
    case_matrix = card["case_matrix"]
    for case in case_matrix:
        if case.get("baseline") is True:
            return case, None
    p0_rules = card["p0_rules"]
    for case in case_matrix:
        if _is_control_candidate(case, p0_rules):
            return case, None
    return case_matrix[0], (
        "no viable control baseline (no case_matrix entry passes every p0 rule cleanly) -- "
        "falling back to case_matrix[0]; mutation assertions may be unreliable")


# -- generate: P0 layer -----------------------------------------------------

def _card_mutation_for_rule(card: dict, rule_index: int):
    for case in card["case_matrix"]:
        for m in case.get("mutations") or []:
            if m.get("kills") == "p0:%d" % rule_index:
                return m
    return None


def _find_target_case(case_matrix: list, axis: str, exclude_case_name):
    """First case whose expect declares `axis`, preferring one that is not the
    control-baseline case (so the control stays untouched by this mutation)."""
    fallback = None
    for case in case_matrix:
        expect = case.get("expect") or {}
        if axis not in expect:
            continue
        if case.get("case") != exclude_case_name:
            return case
        if fallback is None:
            fallback = case
    return fallback


def _gen_p0_mutations(card: dict, control_case_name):
    mutations = []
    orphans = []
    for i, rule in enumerate(card["p0_rules"]):
        card_mutation = _card_mutation_for_rule(card, i)
        if card_mutation is not None:
            mutations.append({
                "id": "p0-%d-card" % i,
                "layer": "p0",
                "vehicle": card_mutation.get("vehicle", "gt"),
                "kills": "p0:%d" % i,
                "patch": card_mutation.get("patch") or {},
                "expected_exit": card_mutation.get("expected_exit", 1),
            })
            continue

        axis = rule.get("target_axis")
        if not axis:
            orphans.append("p0_rules[%d] (%r): no card mutation and no target_axis"
                           % (i, rule.get("rule")))
            continue

        target_case = _find_target_case(card["case_matrix"], axis, control_case_name)
        if target_case is None:
            orphans.append(
                "p0_rules[%d] (%r): target_axis %r not present in any case_matrix.expect"
                % (i, rule.get("rule"), axis))
            continue

        mutations.append({
            "id": "p0-%d" % i,
            "layer": "p0",
            "vehicle": "gt",
            "kills": "p0:%d" % i,
            "patch": {"case": target_case["case"], "field": axis,
                     "value": rule.get("violation_value")},
            "expected_exit": 1,
        })
    return mutations, orphans


# -- generate: threshold +/-epsilon layer (record vehicle) ----------------

def _r1(value: float) -> float:
    """One-decimal ROUND_HALF_UP -- identical to scorer.py's r1() so the
    generated targets land where the REAL composite score will."""
    return float(Decimal(str(value)).quantize(Decimal("0.0"), rounding=ROUND_HALF_UP))


def _uniform_maturity(dimensions: dict, x: float) -> float:
    """Maturity the shipped scorer.score() actually produces when EVERY
    dimension scores `x`: it rounds each weighted term (r1(weight*x/100))
    BEFORE summing, then rounds the sum. The old generator assumed the single
    identity r1(sum(weight*x/100)) == x, which is false once a per-dimension
    term sits on a rounding boundary (e.g. 50*79.9/100 = 39.95 -> 40.0)."""
    return _r1(sum(_r1(w * x / 100.0) for w in dimensions.values()))


def _find_uniform_target(dimensions: dict, threshold: float, epsilon: float,
                         below: bool):
    """Smallest-grain uniform per-dimension score whose ACTUAL double-rounded
    maturity is strictly below (`below`) / at-or-above the threshold. Walks in
    0.1 grains outward from threshold-/+epsilon. Returns None when no such
    score exists (e.g. threshold 0 has no maturity strictly below it) so the
    caller can skip a probe with no real boundary instead of mis-flagging a
    correct gate."""
    step = 0.1
    if below:
        x = max(0.0, min(100.0, threshold - epsilon))
        while True:
            if _uniform_maturity(dimensions, x) < threshold:
                return round(x, 1)
            if x <= 0.0:
                return None
            x = max(0.0, round(x - step, 1))
    x = max(0.0, min(100.0, threshold + epsilon))
    while True:
        if _uniform_maturity(dimensions, x) >= threshold:
            return round(x, 1)
        if x >= 100.0:
            return None
        x = min(100.0, round(x + step, 1))


def _gen_threshold_mutations(card: dict):
    """Uniform-score probe: set EVERY dimension to the same score and check the
    gate flips across the maturity threshold. The target is chosen from the
    scorer's REAL composite (per-dimension rounding then sum), not the naive
    r1(sum(w*X/100))==X identity, so a correct gate is never falsely accused of
    being 'blind'/'panicky'. A probe whose side of the threshold is
    unsatisfiable (threshold 0 minus, threshold 100 plus) is skipped."""
    mutations = []
    threshold = card["threshold"]
    dims_map = card["dimensions"]
    dims = sorted(dims_map)
    for axis in sorted(card["epsilon"]):
        epsilon = card["epsilon"][axis]
        for expected_exit, tag, below in ((1, "minus", True), (0, "plus", False)):
            target = _find_uniform_target(dims_map, threshold, epsilon, below)
            if target is None:
                continue
            mutations.append({
                "id": "threshold-%s-%s" % (axis, tag),
                "layer": "threshold",
                "vehicle": "record",
                "kills": "axis:%s" % axis,
                "patch": {"fixed_scores": {d: target for d in dims}},
                "expected_exit": expected_exit,
            })
    return mutations


# -- generate: noise layer (gt vehicle, normalize-safe) --------------------

def _gen_noise_mutations(card: dict, p0_axes: set):
    for case in card["case_matrix"]:
        expect = case.get("expect") or {}
        for field, value in expect.items():
            if field in p0_axes:
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            # padding-only: the generic runner's normalize (NFC + lower +
            # whitespace-collapse) folds this back to the same value, so the
            # gate must NOT panic; the raw bytes still differ from the
            # original so this is a REAL mutation, not a no-op.
            noisy = "  %s  " % value
            return [{
                "id": "noise-%s-%s" % (case.get("case"), field),
                "layer": "noise",
                "vehicle": "gt",
                "kills": None,
                "patch": {"case": case.get("case"), "field": field, "value": noisy},
                "expected_exit": 0,
            }]
    return []


# -- generate: code layer (code vehicle, reviewer-approved patch points) ---

def _gen_code_mutations(card: dict):
    """Emit one matrix entry per card `code_mutations` entry (DP-1: COPY the
    reviewer-approved patch point verbatim — no code-side invention, no LLM).
    Iterates the card's own list order to keep the matrix byte-deterministic.
    Absent field -> no entries (back-compat: the 3 existing layers are
    untouched)."""
    mutations = []
    for entry in card.get("code_mutations") or []:
        mutations.append({
            "id": entry["id"],
            "layer": "code",
            "vehicle": "code",
            "kills": entry.get("kills"),
            "target": entry["target"],
            "patch": entry.get("patch") or {},
            "expected_exit": entry.get("expected_exit", 1),
        })
    return mutations


def cmd_generate(config_arg: str, out_arg: str) -> int:
    config_path = Path(config_arg)
    try:
        card, card_hash = _verify_and_load(config_path)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return EXIT_INPUT_ERROR

    control_case, warning = _pick_control(card)
    if warning:
        print("WARNING: %s" % warning, file=sys.stderr)

    p0_axes = {r["target_axis"] for r in card["p0_rules"] if r.get("target_axis")}

    p0_mutations, orphans = _gen_p0_mutations(card, control_case.get("case"))
    if orphans:
        print("ERROR: unkillable P0 rule(s) -- an unkillable rule is an unproven rule:",
              file=sys.stderr)
        for orphan in orphans:
            print("  - %s" % orphan, file=sys.stderr)
        return EXIT_COVERAGE_FAIL

    noise_mutations = _gen_noise_mutations(card, p0_axes)
    if not noise_mutations:
        print("WARNING: no noise-layer mutation generated -- no non-P0 string "
              "field in any case_matrix expect, so the 'gate does not panic on "
              "sub-threshold noise' layer is NOT exercised for this card",
              file=sys.stderr)
    code_mutations = _gen_code_mutations(card)

    # R3 mutation-proven coverage (DP-2): a python (native-lane) card must break
    # BOTH the mirror AND the p0 gate body via a code vehicle, else the eval is
    # not proven to catch broken CODE (lỗ #3). Refuse at generate time, same
    # "unproven rule refuses" discipline as the P0-orphan gate above. A
    # non-python (subprocess-lane) card cannot run the code vehicle yet, so it
    # gets a NOTE, never a hard refuse (F3 lang-guard).
    mirror_code = sum(1 for m in code_mutations if m.get("target") == "pipeline_mirror")
    p0_code = sum(1 for m in code_mutations if m.get("target") == "check_p0_gates")
    if card.get("mirror_lang") == "python":
        if mirror_code < 1 or p0_code < 1:
            print("ERROR: code coverage insufficient: need >=1 pipeline_mirror + "
                  ">=1 check_p0_gates code_mutation; got mirror=%d p0=%d "
                  "(not mutation-proven -- an eval that never breaks its own code "
                  "cannot claim to catch broken code)" % (mirror_code, p0_code),
                  file=sys.stderr)
            return EXIT_COVERAGE_FAIL
    elif code_mutations:
        # A non-python card CANNOT run the code vehicle (it patches a native
        # pipeline_mirror.py / scorer.py); declaring code_mutations anyway would
        # crash at run time. Refuse rather than ship a card that cannot execute
        # its own mutations.
        print("ERROR: code_mutations declared on a non-python card (mirror_lang %r): "
              "the code vehicle is native-python only and cannot run these -- remove "
              "them or switch to the python native lane" % card.get("mirror_lang"),
              file=sys.stderr)
        return EXIT_COVERAGE_FAIL
    else:
        print("NOTE: code-vehicle coverage is enforced for native-python mirrors only; "
              "mirror_lang %r runs the subprocess lane -- code-vehicle wave is later, "
              "not refusing" % card.get("mirror_lang"), file=sys.stderr)

    mutations = p0_mutations + _gen_threshold_mutations(card) + noise_mutations + code_mutations

    matrix = {
        "card_hash": card_hash,
        "control_case": control_case.get("case"),
        "mutations": mutations,
    }
    body = json.dumps(matrix, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    Path(out_arg).write_text(body, encoding="utf-8")
    print("wrote %s (%d mutations)" % (out_arg, len(mutations)))
    return EXIT_OK


# -- run: code vehicle (patch SOURCE, run the real eval) --------------------

def _module_scope_defs(nodes, symbol: str):
    """Collect every function def named `symbol` bound at MODULE scope: descend
    through module-level control-flow containers (if/try/with/for/while, incl.
    else/finally/except bodies) but stop at ClassDef (methods) and never recurse
    into a function body (nested defs are a different scope)."""
    found = []
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == symbol:
                found.append(node)
            continue  # do not recurse into a function body
        if isinstance(node, ast.ClassDef):
            continue  # methods are not module-scope bindings
        for field in ("body", "orelse", "finalbody"):
            child = getattr(node, field, None)
            if isinstance(child, list):
                found.extend(_module_scope_defs(child, symbol))
        for handler in getattr(node, "handlers", None) or []:
            found.extend(_module_scope_defs(handler.body, symbol))
        for case in getattr(node, "cases", None) or []:  # match/case (py3.10+)
            found.extend(_module_scope_defs(case.body, symbol))
    return found


def _apply_code_patch(source: str, patch: dict) -> str:
    """Deterministically break one source file. Two kinds:

    symbol_return — insert `return <value>` at the TOP of EVERY function named
      `patch["symbol"]`. Patching every def (not just the first) is load-bearing:
      a stamped mirror/scorer keeps the template stub AND appends the real fill,
      so two same-named defs coexist and Python calls the LAST — patching only
      the shadowed stub would be a silent no-op. Refuses when the symbol is
      absent (a no-op patch that would falsely "pass").
    regex_sub — `re.subn(anchor, replacement, source, count)`; refuses unless
      EXACTLY `count` substitutions were made (0 or a wrong count is a
      non-deterministic no-op, never a legitimate mutation). `anchor` is
      config-sourced (a card field, not a source literal) matched against the
      real source file being patched, so it runs under the same ReDoS wall-
      clock budget as claim_verify.py's `match`/`assert` — a catastrophic-
      backtracking anchor raises `_AnchorTimeoutError` instead of hanging.
    """
    kind = patch.get("kind")
    if kind == "symbol_return":
        symbol = patch["symbol"]
        value = patch.get("value")
        tree = ast.parse(source)
        # repr() of a json-loaded value is a valid Python literal (dict/list/
        # bool/None/num/str) — parse it back into an expression node.
        value_node = ast.parse(repr(value), mode="eval").body
        # MODULE-SCOPE defs (the stub+fill pair): descend through module-level
        # control flow (if/try/with/for/while) so a conditionally-defined def is
        # still patched, but never into a ClassDef (methods are a different
        # scope) or a nested function body. A fresh Return per site keeps the AST
        # a strict tree (no shared node).
        targets = _module_scope_defs(tree.body, symbol)
        for node in targets:
            node.body.insert(0, ast.Return(value=copy.deepcopy(value_node)))
        patched_count = len(targets)
        if patched_count == 0:
            raise ValueError(
                "symbol_return: no function named %r found to patch (no-op)" % symbol)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    if kind == "regex_sub":
        anchor = patch["anchor"]
        replacement = patch["replacement"]
        count = patch.get("count", 1)
        new_source, n = _run_with_wallclock_budget(
            lambda: re.subn(anchor, replacement, source, count=count),
            _ANCHOR_MATCH_TIMEOUT_SECONDS)
        if n == 0 or n != count:
            raise ValueError(
                "regex_sub: expected %d substitution(s) for anchor %r, made %d "
                "(no-op / non-deterministic patch refused)" % (count, anchor, n))
        return new_source

    raise ValueError("unknown code patch kind %r" % kind)


# -- run: gt vehicle --------------------------------------------------------

def _apply_gt_patch(gt: dict, patch: dict) -> dict:
    """Patch ONE field on ONE item of a ground_truth.json copy. Matches
    case_matrix[].case to ground_truth items[].case_file by exact string
    equality -- this module's own convention (documented in the module docstring):
    a card authored for this generator names its case_matrix cases the same
    as the ground_truth.json case_file it corresponds to."""
    if not isinstance(gt, dict):
        raise ValueError("ground_truth.json must be a JSON object, got %s" % type(gt).__name__)
    patched = copy.deepcopy(gt)
    case_name = patch["case"]
    found = False
    for item in patched.get("items", []):
        if item.get("case_file") == case_name:
            item.setdefault("ground_truth", {})
            item["ground_truth"][patch["field"]] = patch.get("value")
            found = True
    if not found:
        raise ValueError("gt patch: case %r not found in ground_truth items" % case_name)
    return patched


def _run_gt_vehicle(evals_root: Path, sample_dir: str, gt_path: Path, patch, workdir: Path,
                    env: dict, tag: str):
    original = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    used = _apply_gt_patch(original, patch) if patch is not None else original
    tmp_gt = workdir / ("gt-%s.json" % tag)
    tmp_gt.write_text(json.dumps(used, ensure_ascii=False), encoding="utf-8")
    cli = evals_root / "scripts" / "run_production_evals.py"
    return subprocess.run(
        [sys.executable, str(cli), "--sample-dir", str(sample_dir), "--ground-truth", str(tmp_gt)],
        capture_output=True, text=True, env=env)


# -- run: record vehicle (nested layout so the scorer's parents[2] resolves) --

def _run_record_vehicle(evals_root: Path, domain: str, patch: dict, workdir: Path,
                        env: dict, tag: str):
    nested_evals = workdir / ("record-%s" % tag) / "evals"
    nested_domain = nested_evals / "eval_types" / domain
    nested_domain.mkdir(parents=True, exist_ok=True)
    shutil.copy2(evals_root / "eval_config.json", nested_evals / "eval_config.json")
    shutil.copy2(evals_root / "eval_config.sha256", nested_evals / "eval_config.sha256")
    shutil.copy2(evals_root / "eval_types" / domain / "scorer.py", nested_domain / "scorer.py")
    shutil.copy2(evals_root / "eval_types" / domain / "config_integrity.py",
                nested_domain / "config_integrity.py")

    fixed_scores = patch["fixed_scores"]
    driver = (
        "import json, sys\n"
        "sys.path.insert(0, '.')\n"
        "import scorer\n"
        "FIXED = %s\n"
        "scorer.score_dimension = lambda name, results: FIXED[name]\n"
        "result = scorer.score([])\n"
        "print(json.dumps({'maturity': result['maturity'], 'passed': result['passed']}))\n"
        "sys.exit(0 if result['passed'] else 1)\n"
    ) % json.dumps(fixed_scores)
    driver_path = nested_domain / "driver_record.py"
    driver_path.write_text(driver, encoding="utf-8")

    return subprocess.run([sys.executable, "driver_record.py"], cwd=str(nested_domain),
                          capture_output=True, text=True, env=env)


def _run_code_vehicle(evals_root: Path, domain: str, target, patch: dict, sample_dir: str,
                      gt_path: Path, workdir: Path, env: dict, tag: str):
    """Break the SOURCE (mirror or scorer) in a temp COPY of the WHOLE evals
    tree, then run the real run_production_evals CLI over it — the full path,
    NOT the record vehicle: only a full run with real samples lets a neutered
    p0 gate or a broken mirror actually flip the verdict (record-vehicle's
    score([]) sees no results, so a p0 patch is a false no-op). The ORIGINAL
    tree is never written — all patching lands in the copy. Raises ValueError
    on a setup error (unknown target, no-op patch) so cmd_run reports it as an
    input error (exit 2), never a gate verdict."""
    dest_root = workdir / ("code-%s" % tag) / "evals"
    shutil.copytree(evals_root, dest_root)

    domain_dir = dest_root / "eval_types" / domain
    if target == "pipeline_mirror":
        src_file = domain_dir / "pipeline_mirror.py"
    elif target == "check_p0_gates":
        src_file = domain_dir / "scorer.py"
    else:
        raise ValueError(
            "code vehicle: unknown target %r (expected pipeline_mirror|check_p0_gates)" % target)

    src_file.write_text(_apply_code_patch(src_file.read_text(encoding="utf-8"), patch),
                        encoding="utf-8")

    cli = dest_root / "scripts" / "run_production_evals.py"
    return subprocess.run(
        [sys.executable, str(cli), "--sample-dir", str(sample_dir), "--ground-truth", str(gt_path)],
        capture_output=True, text=True, env=env)


def _extract_rule_indices(stdout: str):
    return sorted({int(m) for m in _RULE_INDEX_RE.findall(stdout)})


def cmd_run(config_arg: str, matrix_arg: str, evals_root_arg: str, sample_dir: str,
           ground_truth_arg: str, report_arg=None) -> int:
    config_path = Path(config_arg)
    try:
        card, current_hash = _verify_and_load(config_path)
    except ValueError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return EXIT_INPUT_ERROR

    try:
        matrix = json.loads(Path(matrix_arg).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print("ERROR: cannot read matrix %s: %s" % (matrix_arg, e), file=sys.stderr)
        return EXIT_INPUT_ERROR

    if matrix.get("card_hash") != current_hash:
        print("ERROR: card_hash drift -- matrix was generated against a different config "
              "version (matrix=%s current=%s); re-run generate"
              % (matrix.get("card_hash"), current_hash), file=sys.stderr)
        return EXIT_INPUT_ERROR

    evals_root = Path(evals_root_arg)
    gt_path = Path(ground_truth_arg)
    domain = card["domain"]
    env = _scrubbed_env()

    harness_keys_in_caller = sorted(k for k in os.environ if k.startswith(_HARNESS_ENV_PREFIX))
    probe = subprocess.run(
        [sys.executable, "-c",
         "import os, json; print(json.dumps(sorted(k for k in os.environ "
         "if k.startswith('HARNESS_'))))"],
        capture_output=True, text=True, env=env)
    try:
        subprocess_harness_keys = json.loads(probe.stdout.strip() or "[]")
    except json.JSONDecodeError:
        subprocess_harness_keys = None

    with tempfile.TemporaryDirectory(prefix="mutation-matrix-") as tmp:
        workdir = Path(tmp)

        try:
            control = _run_gt_vehicle(evals_root, sample_dir, gt_path, None, workdir, env, "control")
        except _SETUP_ERRORS as e:
            # a missing/unreadable ground truth (or other setup failure) on the
            # clean baseline run is a SETUP error (exit 2), not a gate verdict.
            print("ERROR: control baseline: %s" % e, file=sys.stderr)
            return EXIT_INPUT_ERROR
        control_ok = control.returncode == 0

        results = []
        mismatches = []
        for mutation in matrix.get("mutations", []):
            vehicle = mutation.get("vehicle")
            if vehicle == "gt":
                try:
                    proc = _run_gt_vehicle(evals_root, sample_dir, gt_path, mutation["patch"],
                                           workdir, env, mutation["id"])
                except _SETUP_ERRORS as e:
                    # A card/ground-truth naming misalignment or a file-system
                    # failure is a setup error, not a gate mismatch -- report it
                    # as an input error (exit 2), never let it escape as an
                    # exit-1 "gate blind" traceback.
                    print("ERROR: mutation %s: %s" % (mutation.get("id"), e), file=sys.stderr)
                    return EXIT_INPUT_ERROR
            elif vehicle == "record":
                try:
                    proc = _run_record_vehicle(evals_root, domain, mutation["patch"], workdir, env,
                                               mutation["id"])
                except _SETUP_ERRORS as e:
                    print("ERROR: record mutation %s: %s" % (mutation.get("id"), e), file=sys.stderr)
                    return EXIT_INPUT_ERROR
            elif vehicle == "code":
                try:
                    proc = _run_code_vehicle(evals_root, domain, mutation.get("target"),
                                             mutation["patch"], sample_dir, gt_path, workdir, env,
                                             mutation["id"])
                except _SETUP_ERRORS as e:
                    # A bad target, a no-op/invalid patch, a missing source file, or
                    # a copytree failure is a SETUP error, not a gate verdict --
                    # surface it as input-error (exit 2), never let it masquerade as
                    # a gate mismatch (exit 1).
                    print("ERROR: code mutation %s: %s" % (mutation.get("id"), e), file=sys.stderr)
                    return EXIT_INPUT_ERROR
            else:
                print("ERROR: unknown vehicle %r in mutation %s"
                      % (vehicle, mutation.get("id")), file=sys.stderr)
                return EXIT_INPUT_ERROR

            expected = mutation["expected_exit"]
            actual = proc.returncode
            ok = actual == expected

            rule_indices = None
            if mutation.get("layer") == "p0":
                kills = mutation.get("kills") or ""
                rule_index = int(kills.split(":", 1)[1]) if kills.startswith("p0:") else None
                rule_indices = _extract_rule_indices(proc.stdout)
                if ok and rule_index is not None and rule_index not in rule_indices:
                    ok = False
                if ok and not control_ok:
                    ok = False

            record = {"id": mutation["id"], "layer": mutation["layer"], "vehicle": vehicle,
                     "kills": mutation.get("kills"), "expected_exit": expected,
                     "actual_exit": actual, "rule_indices_fired": rule_indices, "ok": ok}
            results.append(record)
            if not ok:
                if expected == 1:
                    classification = "blind"
                    print("MISMATCH %s: gate blind -- expected exit 1 (kill), got %s"
                          % (mutation["id"], actual), file=sys.stderr)
                else:
                    classification = "panicky"
                    print("MISMATCH %s: gate panicky -- expected exit 0, got %s"
                          % (mutation["id"], actual), file=sys.stderr)
                record["classification"] = classification
                mismatches.append(record)

        if not control_ok:
            print("ERROR: control-baseline failed -- the clean ground-truth run did not pass; "
                  "the mutation matrix cannot be trusted", file=sys.stderr)

        report = {
            "control_baseline_ok": control_ok,
            "results": results,
            "mismatches": [m["id"] for m in mismatches],
            "meta": {
                "harness_keys_in_caller": harness_keys_in_caller,
                "harness_keys_in_subprocess": subprocess_harness_keys,
            },
        }
        if report_arg:
            Path(report_arg).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                        encoding="utf-8")

        print("mutation matrix: %d/%d matched" % (len(results) - len(mismatches), len(results)))
        return EXIT_OK if (not mismatches and control_ok) else EXIT_MISMATCH


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate + run a deterministic 3-layer mutation matrix from an "
                    "approved eval strategy card (meta-tests the eval gate itself)")
    sub = parser.add_subparsers(dest="verb", required=True)

    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--config", required=True)
    p_gen.add_argument("--out", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--matrix", required=True)
    p_run.add_argument("--evals-root", required=True)
    p_run.add_argument("--sample-dir", required=True)
    p_run.add_argument("--ground-truth", required=True)
    p_run.add_argument("--report", default=None)

    args = parser.parse_args(argv)
    if args.verb == "generate":
        return cmd_generate(args.config, args.out)
    return cmd_run(args.config, args.matrix, args.evals_root, args.sample_dir,
                   args.ground_truth, args.report)


if __name__ == "__main__":
    sys.exit(main())
