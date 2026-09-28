#!/usr/bin/env python3
"""perf_telemetry.py — load/perf metrics (telemetry, never a gate) + per-language
coverage judgement.

Load/stress/perf is a MEASUREMENT, not a pass/fail: read k6/JMeter JSON
into {p50, p95, error_rate, throughput}, append to the perf channel, and flag a
p95 regression vs the previous baseline as an ADVISORY — never a hard block. The
band is wide on purpose (environment noise; mirrors hs:bakeoff's noise-band
thinking).

Coverage is judged PER LANGUAGE: there is no fair global average across
stacks, so each Cobertura report is compared to its own threshold and a failing
stack is named — never washed out by a passing one.
"""

import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_PERF_SINK = "perf-metrics.jsonl"


# --- load/perf ----------------------------------------------------------------
def read_k6(path) -> dict:
    """Parse a k6 summary JSON → {p50, p95, error_rate, throughput}. Missing
    metrics degrade to None rather than raising — perf is advisory, a partial
    report should still surface what it has."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    metrics = (doc or {}).get("metrics") or {}

    def _val(name, key):
        return ((metrics.get(name) or {}).get("values") or {}).get(key)

    return {
        "p50": _val("http_req_duration", "med"),
        "p95": _val("http_req_duration", "p(95)"),
        "error_rate": _val("http_req_failed", "rate"),
        "throughput": _val("http_reqs", "rate"),
    }


def perf_regression(current: dict, baseline: dict, threshold_pct: float = 20) -> dict:
    """Advisory verdict comparing current p95 to a baseline. `regressed` is True
    only when p95 rose more than `threshold_pct` over baseline (a wide band to
    absorb environment noise). ALWAYS advisory — there is no block path."""
    cur = (current or {}).get("p95")
    base = (baseline or {}).get("p95")
    regressed = False
    delta_pct = None
    if isinstance(cur, (int, float)) and isinstance(base, (int, float)) and base > 0:
        delta_pct = (cur - base) / base * 100.0
        regressed = delta_pct > threshold_pct
    return {"regressed": regressed, "delta_pct": delta_pct,
            "enforcement": "advisory", "block": False}


def emit_regression_trace(current, baseline, *, label=None,
                          threshold_pct: float = 20.0) -> dict:
    """Compute perf_regression and, when it regressed, append a fail-open
    `perf_regression` ADVISORY trace (never a block) so the advisory is auditable
    in the trace store. Returns the verdict either way (caller still reads
    delta_pct). No trace when within the noise band."""
    verdict = perf_regression(current, baseline, threshold_pct)
    if verdict.get("regressed"):
        try:
            hooks = str(Path(__file__).resolve().parent.parent / "hooks")
            if hooks not in sys.path:
                sys.path.append(hooks)
            import trace_log
            trace_log.append_event(
                "perf_telemetry", "perf_regression", target=(label or "perf"),
                note="p95 %+.0f%% vs baseline (advisory)"
                % (verdict.get("delta_pct") or 0))
        except Exception:  # noqa: BLE001 — tracing never blocks
            pass
    return verdict


def emit_perf_metrics(metrics: dict, *, label=None) -> None:
    """Append one perf-metrics record to the telemetry channel (actor+ts added
    by telemetry_paths). Fail-open."""
    try:
        import telemetry_paths
        rec = dict(metrics)
        if label is not None:
            rec["label"] = label
        telemetry_paths.append_event(_PERF_SINK, rec)
    except Exception:  # noqa: BLE001 — telemetry is fail-open
        pass


# --- per-language coverage ----------------------------------------------------
def coverage_per_language(reports: dict) -> dict:
    """{language: {line_rate, branch_rate}} from a {language: cobertura-path}
    map. Kept SEPARATE — no global/merged key is ever produced."""
    import test_result_readers as rdr
    out = {}
    for lang, path in (reports or {}).items():
        out[lang] = rdr.read_cobertura(path)
    return out


def coverage_meets_per_lang(per_lang: dict, thresholds: dict):
    """(ok, failures): each language's line coverage vs its own threshold
    (percent). A stack with no declared threshold is not gated. Failures name
    the stack so a py-pass/js-fail is reported as js-fail, never averaged away."""
    failures = []
    for lang, data in (per_lang or {}).items():
        floor = (thresholds or {}).get(lang)
        if floor is None:
            continue
        pct = (data.get("line_rate") or 0) * 100
        if pct < floor:
            failures.append("%s coverage %.0f%% is below its %s%% line floor"
                            % (lang, pct, floor))
    return (not failures), failures
