"""Turn qa/reports/*.json into qa/reports/SUMMARY.md (attach it to the handover)."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import REPORTS_DIR  # noqa: E402

SUITES = {"smoke": "Smoke", "security": "Security", "performance": "Performance", "e2e": "End-to-end"}


def _load(name: str) -> dict:
    path = REPORTS_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    results = _load("results.json")
    perf = _load("perf.json")
    e2e = _load("e2e.json")
    tests = results.get("tests", [])

    lines = ["# QA run summary", "", f"Generated: {results.get('generated_at', '-')}", ""]
    lines += ["| Suite | Passed | Failed | Known finding (xfail) | Skipped |", "|---|---|---|---|---|"]
    by_suite: dict[str, Counter] = defaultdict(Counter)
    for t in tests:
        by_suite[t["suite"]][t["outcome"]] += 1
    for key, label in SUITES.items():
        c = by_suite.get(key, Counter())
        lines.append(f"| {label} | {c['passed']} | {c['failed']} | {c['xfailed']} | {c['skipped']} |")

    findings = sorted(
        {re.match(r"(FINDING [A-Z]+-\d+[^\n]*)", t["xfail_reason"]).group(1)
         for t in tests if t["xfail_reason"].startswith("FINDING")}
    )
    if findings:
        lines += ["", "## Known findings (tests marked xfail)", ""] + [f"- {f}" for f in findings]

    failed = [t for t in tests if t["outcome"] == "failed"]
    if failed:
        lines += ["", "## Failures", ""]
        lines += [
            f"- `{t['nodeid']}` — {t['doc']}<br>`{(t['message'].splitlines() or [''])[0][:200]}`"
            for t in failed
        ]

    if perf:
        lines += [
            "",
            "## Performance",
            "",
            "| Scenario | Requests | Concurrency | RPS | p50 ms | p95 ms | p99 ms | Max ms | Errors | p95 budget |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, r in perf.items():
            budget = r.get("budget_p95_ms")
            mark = "" if budget is None else (" ✅" if r["p95_ms"] <= budget else " ❌")
            lines.append(
                f"| {name} | {r['requests']} | {r['concurrency']} | {r['rps']} | {r['p50_ms']} | "
                f"{r['p95_ms']}{mark} | {r['p99_ms']} | {r['max_ms']} | {r['error_rate']:.1%} | {budget or '-'} |"
            )

    if e2e:
        lines += ["", "## End-to-end pipeline", ""]
        lines.append(f"- Dossier: `{e2e['dossier_id']}` — final status **{e2e['final_status']}** in {e2e['total_s']} s")
        lines.append(f"- Upload (POST /dossiers) answered in {e2e['upload_ms']} ms")
        lines.append("- Timeline: " + " → ".join(f"{s} @ {t}s" for t, s in e2e["timeline"]))

    lines += ["", "## All tests", "", "| Result | Test | What it checks |", "|---|---|---|"]
    icon = {"passed": "✅", "failed": "❌", "xfailed": "⚠️", "skipped": "⏭️"}
    for t in sorted(tests, key=lambda t: t["nodeid"]):
        lines.append(f"| {icon.get(t['outcome'], t['outcome'])} | `{t['nodeid']}` | {t['doc']} |")

    out = REPORTS_DIR / "SUMMARY.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
