#!/usr/bin/env python3
"""test_result_readers.py — normalize heterogeneous test output to one shape.

Four readers feed the DoD gate one comparable contract:
  - read_junit(path)     → {total, failed, errors, skipped, passed}
  - read_cobertura(path) → {line_rate, branch_rate}
  - read_jacoco(path)    → {line_rate, branch_rate} (same shape as read_cobertura)
  - read_sarif(path)     → {results: [{ruleId, severity, level}]}

Security posture: XML output of a test run is UNTRUSTED in a CI
pull-request context — a malicious fixture can carry a billion-laughs/XXE bomb.
stdlib ElementTree is NOT safe against that, so XML goes through `defusedxml`
(a controlled dependency declared in preflight_deps.py); a coarse size cap
refuses an over-large file BEFORE the parser sees it (defense-in-depth). SARIF
is JSON — read with stdlib `json` and a HAND-WRITTEN required-fields check (no
jsonschema dependency).

Every reader raises `TestResultError` (clear, actionable) on a missing,
over-cap, or malformed file — with one named escape: `read_junit` hands its
already-safe (defused, size-capped) root element to `junitparser.JUnitXml.
fromroot` for format validation, and an unrecognized root tag makes THAT call
raise `junitparser.JUnitXmlError`, not `TestResultError` — the contract is
"clear, actionable, and not always this module's own exception type." Every
numeric-attribute parse (`_int_attr`, `_float_attr`, the SARIF
`security-severity` read) is guarded and degrades to a default instead of
raising. The one real caller (`artifact_check.py`'s `_read_normalized_result`)
catches broadly regardless, so the escape does not crash the gate — but a
caller that only catches `TestResultError` specifically would miss it.

The telemetry channel (emit_test_execution) appends a normalized run to
harness/state/telemetry/test-execution.jsonl via telemetry_paths (actor+ts
enriched, append-only, fail-open).
"""

import json
import os
import sys
from pathlib import Path


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 12 MB: a real JUnit/Cobertura/SARIF report is KB–low-MB; anything past this is
# either a runaway export or an attack payload. Refused before parsing.
MAX_RESULT_BYTES = 12 * 1024 * 1024

# SARIF level → severity bucket. The gate keys off severity; `level` is
# kept verbatim for traceability.
_LEVEL_SEVERITY = {"error": "high", "warning": "medium", "note": "low",
                   "none": "low"}


class TestResultError(Exception):
    """A result file is missing, over the size cap, or malformed. The message
    names the path + the problem so the caller surfaces a fix, never a stack
    trace from inside the gate."""


def _read_capped(path, max_bytes: int) -> str:
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as e:
        raise TestResultError("test result %s is unreadable: %s" % (p, e))
    if size > max_bytes:
        raise TestResultError(
            "test result %s is %d bytes — over the %d-byte size cap; refused "
            "before parsing (an oversized XML report is treated as a possible "
            "bomb)" % (p, size, max_bytes))
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise TestResultError("test result %s is unreadable: %s" % (p, e))


def _parse_xml(path, max_bytes: int):
    """defusedxml-parsed root element, or TestResultError. defusedxml blocks
    entity-expansion / external-entity attacks; we add the size cap on top."""
    text = _read_capped(path, max_bytes)
    try:
        from defusedxml.ElementTree import fromstring
    except ImportError:
        raise TestResultError(
            "defusedxml is required to read XML test results safely — install "
            "it: pip install defusedxml (it is declared in preflight_deps.py)")
    try:
        return fromstring(text)
    except Exception as e:  # noqa: BLE001 — any parse failure → one clear error
        raise TestResultError("test result %s is malformed XML: %s" % (path, e))


def _int_attr(elem, name: str) -> int:
    try:
        return int(elem.get(name, 0) or 0)
    except (TypeError, ValueError):
        return 0


def read_junit(path, *, max_bytes: int = MAX_RESULT_BYTES) -> dict:
    """Aggregate a JUnit-XML report into {total, failed, errors, skipped,
    passed}. Handles both a single <testsuite> root and a <testsuites> root
    wrapping many suites (jest/mocha) by summing every testsuite's attributes.

    Parses via `_parse_xml` (defusedxml + size cap already applied) then hands
    the SAME already-safe root element to junitparser — `JUnitXml.fromroot`
    accepts any ElementTree-shaped element, so this never falls back to
    junitparser's own unsafe default (`xml.etree.ElementTree`, no XXE/bomb
    guard). `fromfile`/`fromstring` are deliberately not used for this reason.

    Deliberately does NOT read `JUnitXml.tests` (the top-level aggregate): that
    property's `update_statistics()` unconditionally recomputes every child
    suite's counts from <testcase> children, discarding a suite's declared
    summary attrs whenever it carries counts but no per-testcase detail (the
    jest/mocha aggregate shape) — a real, silent-corruption trap in the library.

    Counts come off the raw elements rather than junitparser's descriptors, for
    two measured reasons. First, ACCESS ORDER matters on the descriptors: reading
    `.tests` on a suite that lacks it fires `update_statistics()`, which rewrites
    all four counts, so a `failures="2"` the file declared is gone before the next
    line reads it. Second, `root.iter("testsuite")` reaches a `<testsuite>` nested
    inside another one, which iterating the JUnitXml object does not.

    The `max(declared, counted-children)` floor is the load-bearing part. The DoD
    gate keys off `failed + errors` alone, so any path that reports zero for a
    failing run opens ship/deploy. junitparser recounts an ABSENT attribute but
    trusts a present one that says `"0"` or `""` — three real shapes reproduced
    that way, each handing the gate a clean bill for a run with a genuine failure
    in it. Taking the max keeps a correct declared summary (jest/mocha aggregates
    with no testcase children) while refusing to believe a zero that the file's own
    contents contradict."""
    # Imported HERE, not at module scope. `harness/hooks/gate_stage.py` imports this
    # module on every matching event just to call `emit_test_execution`, and a hook is a
    # fresh process each time — measured, the module-level form cost +77 ms per event for
    # a library that only `read_junit` ever touches. That is the same per-event budget the
    # omegaconf peek in artifact_check exists to protect, spent by accident.
    import junitparser

    root = _parse_xml(path, max_bytes)
    # Constructed for the format validation it performs on the root tag; the counts
    # below deliberately do not go through its descriptors (see above).
    junitparser.JUnitXml.fromroot(root)
    suites = list(root.iter("testsuite"))
    total = sum(_int_attr(s, "tests") for s in suites)
    failed = sum(_int_attr(s, "failures") for s in suites)
    errors = sum(_int_attr(s, "errors") for s in suites)
    skipped = sum(_int_attr(s, "skipped") for s in suites)

    child_total = sum(1 for _ in root.iter("testcase"))
    child_failed = sum(1 for tc in root.iter("testcase")
                       if tc.find("failure") is not None)
    child_errors = sum(1 for tc in root.iter("testcase")
                       if tc.find("error") is not None)
    child_skipped = sum(1 for tc in root.iter("testcase")
                        if tc.find("skipped") is not None)

    total = max(total, child_total)
    failed = max(failed, child_failed)
    errors = max(errors, child_errors)
    skipped = max(skipped, child_skipped)
    passed = max(0, total - failed - errors - skipped)
    return {"total": total, "failed": failed, "errors": errors,
            "skipped": skipped, "passed": passed}


def _float_attr(elem, name: str):
    try:
        return float(elem.get(name))
    except (TypeError, ValueError):
        return None


def read_cobertura(path, *, max_bytes: int = MAX_RESULT_BYTES) -> dict:
    """Read a Cobertura coverage report's root rates → {line_rate, branch_rate}
    as floats in [0, 1] (or None when the attribute is absent)."""
    root = _parse_xml(path, max_bytes)
    cov = root if root.tag == "coverage" else next(
        (e for e in root.iter("coverage")), None)
    if cov is None:
        raise TestResultError(
            "test result %s is not a Cobertura report (no <coverage> element)"
            % path)
    return {"line_rate": _float_attr(cov, "line-rate"),
            "branch_rate": _float_attr(cov, "branch-rate")}


def read_jacoco(path, *, max_bytes: int = MAX_RESULT_BYTES) -> dict:
    """Read a JaCoCo XML report's aggregate counters → {line_rate, branch_rate}
    (same shape as read_cobertura, so a Java module feeds the SAME coverage gate
    as a Python/JS one). JaCoCo expresses coverage as report-level
    <counter type="LINE" missed covered> children — not a line-rate attribute —
    so the rate is covered/(covered+missed). None when a counter is absent."""
    root = _parse_xml(path, max_bytes)
    rep = root if root.tag == "report" else next(
        (e for e in root.iter("report")), None)
    if rep is None:
        raise TestResultError(
            "test result %s is not a JaCoCo report (no <report> element)" % path)
    rates = {}
    # report-level counters are DIRECT children of <report> (the aggregate); the
    # per-package/class counters nested below are intentionally not summed here.
    for c in rep:
        if c.tag != "counter":
            continue
        ctype = (c.get("type") or "").upper()
        if ctype not in ("LINE", "BRANCH"):
            continue
        total = _int_attr(c, "covered") + _int_attr(c, "missed")
        rate = (_int_attr(c, "covered") / total) if total > 0 else None
        rates["line_rate" if ctype == "LINE" else "branch_rate"] = rate
    return {"line_rate": rates.get("line_rate"),
            "branch_rate": rates.get("branch_rate")}


def _validate_sarif(doc, path) -> None:
    """Hand-written required-fields check (NO jsonschema): a SARIF log is a dict
    with `version` and a `runs` LIST, each run a dict with a `results` LIST.
    Anything else raises so a non-SARIF JSON cannot pass as an empty clean run."""
    if not isinstance(doc, dict):
        raise TestResultError("SARIF %s is not a JSON object" % path)
    if "version" not in doc:
        raise TestResultError("SARIF %s missing required field `version`" % path)
    runs = doc.get("runs")
    if not isinstance(runs, list):
        raise TestResultError(
            "SARIF %s missing/invalid `runs` — expected a list of runs" % path)
    for i, run in enumerate(runs):
        if not isinstance(run, dict) or not isinstance(run.get("results"), list):
            raise TestResultError(
                "SARIF %s runs[%d] missing/invalid `results` list" % (path, i))


def _severity_of(result: dict) -> str:
    """Severity bucket for one SARIF result. An explicit
    properties.security-severity (CVSS-like 0-10) wins; else map from `level`."""
    props = result.get("properties") or {}
    raw = props.get("security-severity")
    if raw is not None:
        try:
            score = float(raw)
            if score >= 9.0:
                return "critical"
            if score >= 7.0:
                return "high"
            if score >= 4.0:
                return "medium"
            return "low"
        except (TypeError, ValueError):
            pass
    return _LEVEL_SEVERITY.get(str(result.get("level", "warning")).lower(),
                               "medium")


def read_sarif(path, *, max_bytes: int = MAX_RESULT_BYTES) -> dict:
    """Read a SARIF log → {results: [{ruleId, severity, level}]}. json (stdlib)
    + a hand-written required-fields check; raises TestResultError on a missing,
    over-cap, or malformed file."""
    text = _read_capped(path, max_bytes)
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise TestResultError("SARIF %s is malformed JSON: %s" % (path, e))
    _validate_sarif(doc, path)
    out = []
    for run in doc["runs"]:
        for res in run["results"]:
            if not isinstance(res, dict):
                continue
            out.append({
                "ruleId": res.get("ruleId"),
                "level": res.get("level", "warning"),
                "severity": _severity_of(res),
            })
    return {"results": out}


def sarif_verdict(sarif: dict):
    """(verdict, detail) for a normalized SARIF result set (read_sarif output).
    FAIL when any finding is error-level OR high/critical severity — those are
    the actionable buckets a security/a11y gate must block on; warning/note are
    advisory. detail names the blocking count so the gate reason is concrete."""
    blocking = [r for r in (sarif.get("results") or [])
                if str(r.get("level", "")).lower() == "error"
                or str(r.get("severity", "")).lower() in ("high", "critical")]
    if blocking:
        return "FAIL", ("%d error/high-severity finding(s): %s"
                        % (len(blocking),
                           ", ".join(sorted({str(r.get("ruleId")) for r in blocking
                                             if r.get("ruleId")}))[:200]))
    return "PASS", "no error/high-severity findings"


# --- telemetry channel --------------------------------------------------------
_TELEMETRY_SINK = "test-execution.jsonl"


def build_test_execution_record(change_class, signals, test_types, verdict,
                                grace=None) -> dict:
    """The normalized telemetry record (actor + ts are added by telemetry_paths
    on append). Pure — separated from the write so the shape is unit-testable."""
    rec = {
        "change_class": change_class,
        "signals": list(signals or []),
        "test_types": list(test_types or []),
        "verdict": verdict,
    }
    if grace is not None:
        rec["grace"] = grace
    return rec


def emit_test_execution(change_class, signals, test_types, verdict,
                        grace=None) -> None:
    """Append one normalized run to the test-execution telemetry channel.
    Fail-open (telemetry must never break the gate)."""
    try:
        import telemetry_paths
        telemetry_paths.append_event(
            _TELEMETRY_SINK,
            build_test_execution_record(change_class, signals, test_types,
                                        verdict, grace))
    except Exception:  # noqa: BLE001 — telemetry is fail-open by contract
        pass
