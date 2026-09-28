#!/usr/bin/env python3
"""claim_verify.py — deterministic, 0-token claim verification engine.

Verifies universal / absence / structural claims that a behavioral test cannot express
("every /admin/* route requires auth", "no PII in log calls") by full-scope enumeration
(never sampling) against a human-edited rule spec (``harness/data/claim-rules.yaml``),
asserting a condition on every match, and reporting file:line evidence.

Contract (enumerate -> assert -> report -> verdict):
    1. enumerate every match of a rule's ``match`` regex within its declared ``scope``.
    2. assert the rule's ``assert`` condition holds in the window around each match.
    3. report PASS/FAIL per match with file:line evidence.
    4. verdict: ``block`` if any FAIL has severity ``block``; ``advisory`` if the only
       FAILs are severity ``advisory``; ``pass`` otherwise (including when every rule
       enumerated zero matches — a rule with no matches is SKIPPED, never vacuously
       PASSED, so an empty scope cannot manufacture a false-positive pass).

Anti-tautology: this module imports ONLY ``re``/``regex``/``pathlib``/``ast``/``yaml``
(a config loader) — never the application code it verifies. No AI reasoning at check
time: same codebase + same rules -> same verdict, every run.

Read-only reporter (mirrors ``plan_graph.py``'s detection-only stance): stdout + exit
code only. It never writes a store, never mutates the scanned code.

ReDoS guard: both ``rule["match"]`` and ``rule["assert"]`` are regexes supplied by the
SAME human-edited rules file, then matched against arbitrary scanned source text — the
two places in this module where both the pattern AND the text it runs against are
outside this module's control (``assert`` runs against a match *window*, not a raw
scanned line, but a window is still attacker-adjacent scanned content of unbounded
size, not a fixed-length string — "smaller" is not "safe"). Measured: a
catastrophic-backtracking pattern (``(a|a)+b``) against a 28-30 char input already
hangs stdlib ``re`` past 15s and keeps growing exponentially with input length, while a
legitimate rule pattern matches in well under a microsecond. Both are compiled/matched
via ``regex`` (a drop-in ``re`` superset with a ``timeout=`` kwarg `re` lacks) with the
same 1.0s bound — ~6 orders of magnitude above real usage, ~1 order of magnitude below
where a hang becomes noticeable, and unaffected by how large the adversarial input
grows.
"""
import argparse
import sys
from pathlib import Path

import regex
import yaml_io

REQUIRED_FIELDS = ("id", "text", "scope", "match", "assert", "severity")
VALID_SCOPES = ("codebase", "module", "fileset")
VALID_SEVERITIES = ("block", "advisory")
DEFAULT_FILE_GLOB = "**/*.py"

# Generously above legitimate match latency (measured: sub-microsecond for a typical
# rule pattern against a typical source line), far below where a catastrophic pattern's
# hang becomes a problem (measured: already >15s at a 28-30 char adversarial input, and
# growing exponentially with length) — see the module docstring's ReDoS guard note.
_MATCH_TIMEOUT_SECONDS = 1.0


class RuleError(ValueError):
    """A claim-rules.yaml entry is malformed — missing/invalid field."""


class RuleTimeoutError(RuleError):
    """A rule's ``match`` pattern exceeded the matching time budget against real scan
    input — almost certainly a catastrophic-backtracking regex in claim-rules.yaml.
    Raised (never silently swallowed) so a bad rule fails loud instead of hanging."""


# --------------------------------------------------------------------------- loader ---

def load_rules(yaml_path):
    """Load + validate ``rules[]`` from a claim-rules.yaml path. Raises ``RuleError`` on
    a malformed entry (never on a merely-empty file — that yields an empty list)."""
    raw = Path(yaml_path).read_text(encoding="utf-8")
    data = yaml_io.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise RuleError("claim-rules.yaml must be a mapping with a top-level 'rules' key")
    rules = data.get("rules") or []
    if not isinstance(rules, list):
        raise RuleError("claim-rules.yaml 'rules' must be a list")
    for rule in rules:
        _validate_rule(rule)
    return rules


def _validate_rule(rule):
    if not isinstance(rule, dict):
        raise RuleError("rule entry must be a mapping, got %r" % (rule,))
    missing = [f for f in REQUIRED_FIELDS if not rule.get(f)]
    if missing:
        raise RuleError(
            "rule %r missing required field(s): %s"
            % (rule.get("id", "<unknown>"), ", ".join(missing))
        )
    if rule["scope"] not in VALID_SCOPES:
        raise RuleError(
            "rule %s: invalid scope %r (expected one of %s)"
            % (rule["id"], rule["scope"], VALID_SCOPES)
        )
    if rule["severity"] not in VALID_SEVERITIES:
        raise RuleError(
            "rule %s: invalid severity %r (expected one of %s)"
            % (rule["id"], rule["severity"], VALID_SEVERITIES)
        )
    if rule["scope"] == "fileset" and not rule.get("path"):
        raise RuleError("rule %s: scope 'fileset' requires a 'path' glob pattern" % rule["id"])
    # Test-compile both regexes at validation time via `regex` (the module both
    # _find_matches() and _check_assert() actually scan/match with — see the
    # module docstring's ReDoS guard note) so a pattern accepted here is
    # guaranteed to also compile there, and a malformed pattern surfaces as a
    # clean RuleError naming the rule, not a raw regex.error traceback out of
    # the per-file scan loop later.
    try:
        regex.compile(rule["match"])
    except regex.error as exc:
        raise RuleError(
            "rule %s: invalid match regex %r: %s" % (rule["id"], rule["match"], exc)
        )
    assertion = rule["assert"]
    if assertion.startswith("!"):
        assertion = assertion[1:]  # a leading '!' marks a negative assertion
    try:
        regex.compile(assertion)
    except regex.error as exc:
        raise RuleError(
            "rule %s: invalid assert regex %r: %s" % (rule["id"], rule["assert"], exc)
        )


# ---------------------------------------------------------------------- enumerator ---

def _iter_scope_files(rule, scope_root):
    """Full-scope enumeration (no sampling) of files a rule applies to. Returns a
    SORTED list so file order — and therefore reported evidence order — is
    deterministic regardless of filesystem iteration order."""
    root = Path(scope_root)
    scope = rule["scope"]
    file_glob = rule.get("file_glob", DEFAULT_FILE_GLOB)
    if scope == "fileset":
        paths = root.glob(rule["path"])
    elif scope == "module":
        base = (root / rule["path"]) if rule.get("path") else root
        paths = base.glob(file_glob)
    else:  # codebase
        paths = root.glob(file_glob)
    return sorted((p for p in paths if p.is_file()), key=lambda p: str(p))


def _find_matches(rule, path):
    """Enumerate every regex match of ``match`` within one file, each carrying the
    file:line and an assert window (the match line +/- ``context`` lines).

    ``rule["match"]`` is config-sourced (see the module docstring's ReDoS guard note)
    — compiled and matched via ``regex`` with a bounded ``timeout=`` instead of stdlib
    ``re``, so a catastrophic-backtracking pattern aborts loud (``RuleTimeoutError``)
    instead of hanging the scan."""
    pattern = regex.compile(rule["match"])
    context = int(rule.get("context", 0))
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = []
    for idx, line in enumerate(lines):
        try:
            hit = pattern.search(line, timeout=_MATCH_TIMEOUT_SECONDS)
        except TimeoutError:
            raise RuleTimeoutError(
                "rule %s: match pattern %r timed out (>%.1fs) scanning %s:%d — "
                "likely a catastrophic-backtracking regex"
                % (rule["id"], rule["match"], _MATCH_TIMEOUT_SECONDS, path, idx + 1)
            )
        if not hit:
            continue
        start = max(0, idx - context)
        end = min(len(lines), idx + context + 1)
        findings.append(
            {
                "path": path,
                "lineno": idx + 1,
                "window": "\n".join(lines[start:end]),
            }
        )
    return findings


# ------------------------------------------------------------------------ asserter ---

def _check_assert(rule, window_text, path, lineno):
    """Regex-positive / regex-negative assertion on the match window. A leading ``!``
    marks a negative assertion (pattern must NOT appear in the window).

    ``rule["assert"]`` is config-sourced from the SAME human-edited rules file as
    ``rule["match"]`` (see the module docstring's ReDoS guard note) — matched via
    ``regex`` with the same bounded ``timeout=`` so a catastrophic-backtracking
    assert pattern aborts loud (``RuleTimeoutError``) instead of hanging the scan,
    exactly like the already-guarded ``match`` site in ``_find_matches()``."""
    assertion = rule["assert"]
    negative = assertion.startswith("!")
    pattern = assertion[1:] if negative else assertion
    try:
        present = regex.search(pattern, window_text, timeout=_MATCH_TIMEOUT_SECONDS) is not None
    except TimeoutError:
        raise RuleTimeoutError(
            "rule %s: assert pattern %r timed out (>%.1fs) scanning %s:%d — "
            "likely a catastrophic-backtracking regex"
            % (rule["id"], rule["assert"], _MATCH_TIMEOUT_SECONDS, path, lineno)
        )
    return (not present) if negative else present


# ------------------------------------------------------------------ rule evaluation ---

def evaluate_rule(rule, scope_root):
    """Enumerate -> assert -> report for one rule. Zero matches -> SKIP (never a
    vacuous PASS — an empty scope must not manufacture a false-positive pass)."""
    findings = []
    for path in _iter_scope_files(rule, scope_root):
        for match in _find_matches(rule, path):
            ok = _check_assert(rule, match["window"], match["path"], match["lineno"])
            findings.append(
                {
                    "rule_id": rule["id"],
                    "file": str(match["path"]),
                    "line": match["lineno"],
                    "status": "PASS" if ok else "FAIL",
                    "severity": rule["severity"],
                    "text": rule["text"],
                }
            )
    if not findings:
        return {"rule_id": rule["id"], "text": rule["text"], "status": "SKIP", "findings": []}
    status = "FAIL" if any(f["status"] == "FAIL" for f in findings) else "PASS"
    return {"rule_id": rule["id"], "text": rule["text"], "status": status, "findings": findings}


def verdict_for(results):
    """Aggregate verdict across all rule results — semantics per
    ``docs/product/_refs/frankcode-src/qa/methodology/qa/rule-based-verification.md:44-48``:
    ``block`` if any FAIL is severity=block; ``advisory`` if the only FAILs are
    severity=advisory; ``pass`` otherwise (clean or all-SKIP)."""
    has_block_fail = any(
        f["status"] == "FAIL" and f["severity"] == "block"
        for r in results
        for f in r["findings"]
    )
    if has_block_fail:
        return "block"
    has_advisory_fail = any(
        f["status"] == "FAIL" and f["severity"] == "advisory"
        for r in results
        for f in r["findings"]
    )
    if has_advisory_fail:
        return "advisory"
    return "pass"


def run(rules_path, scope_root="."):
    """Load rules, evaluate every rule against ``scope_root``, return
    ``{"results": [...], "verdict": "pass"|"advisory"|"block"}``."""
    rules = load_rules(rules_path)
    results = [evaluate_rule(rule, scope_root) for rule in rules]
    return {"results": results, "verdict": verdict_for(results)}


# ------------------------------------------------------------------------------ CLI ---

def _print_report(outcome):
    for result in outcome["results"]:
        print("Rule %s (%s):" % (result["rule_id"], result["text"]))
        if result["status"] == "SKIP":
            print("  SKIP 0 matches")
            continue
        fail_count = 0
        pass_count = 0
        for finding in result["findings"]:
            if finding["status"] == "FAIL":
                fail_count += 1
                print("  FAIL %s:%d" % (finding["file"], finding["line"]))
            else:
                pass_count += 1
        if pass_count:
            print("  PASS %d other match(es)" % pass_count)
        print("Summary: %d FAIL, %d PASS" % (fail_count, pass_count))
    print("Verdict: %s" % outcome["verdict"].upper())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deterministic claim verification engine")
    parser.add_argument("--rules", required=True, help="path to claim-rules.yaml")
    parser.add_argument("--scope-root", default=".", help="repo root to scan (default: cwd)")
    args = parser.parse_args(argv)

    try:
        outcome = run(args.rules, args.scope_root)
    except RuleError as exc:
        print("claim_verify: %s" % exc, file=sys.stderr)
        return 2

    _print_report(outcome)
    return 1 if outcome["verdict"] == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
