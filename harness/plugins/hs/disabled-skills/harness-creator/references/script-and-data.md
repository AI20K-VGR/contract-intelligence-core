# Script authoring — analyzer vs gate

## Two script types

| Type | Exit code | Output | When to use |
|---|---|---|---|
| **Analyzer** | ALWAYS 0 | JSON stdout | Collect, analyze, report — no blocking |
| **Gate** | 0 (pass) / 2 (block) | JSON stdout + stderr reason | Check a condition then block if it fails |

### Analyzer — always exit 0

```python
#!/usr/bin/env python3
"""<name>.py — analyzer: <description>. Always exit 0, stdout JSON."""

import json, sys
from pathlib import Path

def analyze(root: Path) -> dict:
    # ... collect data ...
    return {"status": "ok", "findings": [...]}

def main() -> int:
    import harness_paths
    result = analyze(harness_paths.root())
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

Analyzers must not exit 2 — on error, return JSON with an `"error"` field and exit 0. The caller (gate or skill) decides whether to block based on the result.

### Gate — exit 2 + actionable reason

```python
#!/usr/bin/env python3
"""<name>.py — gate: <description>. exit 0 pass, exit 2 + stderr block reason."""

import json, sys
from pathlib import Path

def check(root: Path) -> str | None:
    """None = pass; str = reason to block (actionable, human-readable)."""
    # ... check condition ...
    if missing:
        return "Artifact X is missing — run hs:cook to create it before pushing."
    return None

def main() -> int:
    import harness_paths
    reason = check(harness_paths.root())
    if reason:
        sys.stderr.write("[BLOCKED] %s\n" % reason)
        return 2
    print(json.dumps({"status": "pass"}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

The block reason must be actionable: the reader knows what to do to unblock. Do not return a raw exception message or a numeric code.

## Store writes — only through shared writers

Scripts must NOT open `state/` files directly. Use:

```python
import trace_log
trace_log.append_event(hook="<script-name>", event="<event>",
                       session=session, actor=actor, **kwargs)

import telemetry_paths   # use via hook_runtime or directly
# or call hook_runtime.run_telemetry_hook if the script is a hook
```

`TestStoreWriteDiscipline` in `test_bug_class_invariants.py` catches any `open(..., "w"/"a")` pointing into `state/` from code outside the whitelist writers.

## fs_guard — script-path containment helper

`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/fs_guard.py` is the **script-path containment helper** — it limits harness scripts to writing only within their declared zone. This is a boundary for harness scripts, not for the LLM Write tool. Do not describe fs_guard as anything else — `TestWording` catches incorrect descriptions.

## Additional rules

- Filename: `snake_case.py` (Python convention).
- Every script requires TDD: write a test in `harness/tests/` before implementing.
- Scripts must not import from `harness/plugins/hs/skills/` — coupling between runtime scripts and skill prose is not allowed.
- Use `harness_paths.root()` to resolve absolute paths instead of `os.getcwd()`.
- Heavy imports (PyYAML, networkx) should be lazy-loaded inside functions — fast import, no block on missing dep.

## Real examples

- Analyzer: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/catalog.py`, `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/analyze_telemetry.py`
- Gate/check: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/artifact_check.py`, `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/check_fence.py`
- Decision store: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py`
