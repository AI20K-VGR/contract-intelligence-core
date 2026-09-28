#!/usr/bin/env python3
"""standards_compliance_run — RUN a standards tree's type-1 compliance checks.

Distinct from check_standards.py (which validates the GRAPH shape): this module
RUNS the deterministic, shell-executable checks a rule declares, so a rule that
says `mypy --strict` is actually exercised instead of merely parsed.

Two kinds of compliance_check:
  - type-1 (shell)  — `{type: shell, cmd: "...", expect: <int rc>}`. Executed for
                      real; deterministic pass/fail. This is the only kind the
                      machine can verify.
  - type-2 (judged) — `{type: judged, text: "..."}` or a bare string. NEVER
                      executed; marked judged. The machine enforces only that it
                      is present and well-formed (format + coverage), NOT that the
                      code actually complies — that stays an LLM/human judgement.
                      Do NOT oversell a judged check as machine-verified.

SECURITY — arbitrary command execution. A type-1 check runs an arbitrary shell
command sourced from a YAML file in the standards tree. This module is therefore
ONLY for an operator-invoked / CI context. It MUST NOT be wired into a hook
(PreToolUse or otherwise): a forged or hostile .std.yaml could otherwise run code
on every tool call. Advisory-first: the runner reports results and ALWAYS exits 0
even when checks fail; raising it to a blocking gate is a separate, deferred
decision.

CLI:
    standards_compliance_run.py --root <project-dir> [--json]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import mechanical_runner
import standards_graph
import trust_store
from encoding_utils import configure_utf8_console

configure_utf8_console()


# A shell check that hangs must not wedge the runner; bound every command.
_CMD_TIMEOUT_S = 60


def classify_check(check: Any) -> Dict[str, Any]:
    """Normalize one compliance_check item to a typed dict.

    A bare string is back-compat shorthand for a judged check (NEVER executed).
    A dict with `type: shell` is type-1; any other/missing type is judged."""
    if isinstance(check, str):
        return {"type": "judged", "text": check}
    if isinstance(check, dict):
        if check.get("type") == "shell":
            return {
                "type": "shell",
                "cmd": check.get("cmd"),
                "expect": check.get("expect", 0),
            }
        return {
            "type": "judged",
            "text": check.get("text") or check.get("cmd") or "",
        }
    # Anything else (list/number/None) is not a runnable check — treat as judged.
    return {"type": "judged", "text": str(check)}


def run_check(norm: Dict[str, Any], cwd: Path) -> Dict[str, Any]:
    """Execute a normalized check. Judged checks are reported, never run."""
    if norm["type"] != "shell":
        return {"type": "judged", "result": "judged", "executed": False,
                "detail": norm.get("text", "")}

    cmd = norm.get("cmd")
    if not isinstance(cmd, str) or not cmd.strip():
        return {"type": "shell", "result": "error", "executed": False,
                "detail": "shell check missing a cmd string"}

    # Trust gate (R2): a YAML-sourced shell command runs ONLY against a repo the
    # operator explicitly vetted (`hs-cli trust <repo>`). Same gate the review-time
    # auto-fire path in mechanical_runner uses — closing the second untrusted-shell
    # surface. An untrusted cwd yields a `skipped` result, NOT an error, and the
    # module stays advisory (exit 0); it is still NEVER wired into a hook.
    if not trust_store.is_trusted(cwd):
        return {"type": "shell", "result": "skipped", "executed": False,
                "detail": "repo not trusted for shell exec (hs-cli trust)"}

    # Shell-exec via the SHARED runner primitive (one implementation).
    res = mechanical_runner._run_shell(cmd, cwd=cwd, timeout=_CMD_TIMEOUT_S)
    if res.get("timeout"):
        return {"type": "shell", "result": "fail", "executed": True,
                "detail": res.get("detail", "timeout after %ds" % _CMD_TIMEOUT_S)}
    if res.get("error"):
        return {"type": "shell", "result": "error", "executed": True,
                "detail": res.get("detail", "exec error")}

    expect = norm.get("expect", 0)
    result = "pass" if res.get("rc") == expect else "fail"
    return {"type": "shell", "result": result, "executed": True,
            "rc": res.get("rc"), "expect": expect}


def run_root(root: Path) -> Dict[str, Any]:
    """Build the standards graph and run every rule's compliance checks."""
    root = Path(root)
    graph = standards_graph.build_graph(root)
    rows: List[Dict[str, Any]] = []
    for node in graph["nodes"]:
        if node.get("type") != "rule":
            continue
        rid = node.get("id")
        for check in node.get("compliance_checks") or []:
            norm = classify_check(check)
            res = run_check(norm, cwd=root)
            rows.append({
                "rule_id": rid,
                "check": norm.get("cmd") or norm.get("text") or "",
                "type": res["type"],
                "result": res["result"],
                "detail": res.get("detail", ""),
            })
    summary = {
        "pass": sum(1 for r in rows if r["result"] == "pass"),
        "fail": sum(1 for r in rows if r["result"] == "fail"),
        "judged": sum(1 for r in rows if r["result"] == "judged"),
        "error": sum(1 for r in rows if r["result"] == "error"),
        "skipped": sum(1 for r in rows if r["result"] == "skipped"),
    }
    return {"checks": rows, "summary": summary}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="project root (contains harness/standards/)")
    ap.add_argument("--json", action="store_true", help="emit the full report as JSON")
    args = ap.parse_args(argv)

    # Do NOT pre-resolve: is_trusted (in run_check) refuses a symlinked root,
    # and resolving here would collapse the symlink and silently defeat that refusal
    # — keeping the CLI gate consistent with mechanical_runner's raw-root trust check.
    report = run_root(Path(args.root))

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(
            "standards compliance (advisory — only type-1 shell checks are "
            "executed; judged checks are NOT machine-verified)\n")
        for r in report["checks"]:
            sys.stdout.write(
                "  [%-6s] %s :: %s%s\n" % (
                    r["result"], r["rule_id"], r["check"],
                    (" — " + r["detail"]) if r["detail"] else ""))
        s = report["summary"]
        sys.stdout.write(
            "summary: pass=%d fail=%d judged=%d error=%d skipped=%d\n"
            % (s["pass"], s["fail"], s["judged"], s["error"], s["skipped"]))

    # Advisory-first: ALWAYS exit 0, even on failing checks. Raising this to a
    # blocking gate is a separate, deferred decision.
    return 0


if __name__ == "__main__":
    sys.exit(main())
