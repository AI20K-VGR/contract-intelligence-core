# Hook authoring — convention and contract

## Three hook classes (HOOK_CLASS is a constant in code)

| Class | Default | On error | Config-overridable |
|---|---|---|---|
| `telemetry` | ON | fail-open, silent | `enabled` |
| `nudge` | OFF | fail-open, advisory stderr | `enabled` |
| `compliance` | ON + blocking | **fail-closed exit 2 + reason** | `enabled`, `mode` |

**HOOK_CLASS must be a hard constant in hook code:**
```python
HOOK_CLASS = "compliance"   # or "telemetry" | "nudge"
```
`"${HARNESS_BIN_ROOT:-.}"/harness/data/harness-hooks.yaml` only records `enabled`/`mode` overrides — class CANNOT be changed via config. A modified config must not be able to change a gate into a telemetry hook.

## Anatomy of a hook

```python
#!/usr/bin/env python3
"""<hook-name>.py — <class> hook: <short description>."""

import os, sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "<telemetry|nudge|compliance>"
_NAME = Path(__file__).stem


def core(data: dict):
    """telemetry/nudge: return None.
       compliance: return None (pass) | str (block reason)."""
    ...


def main() -> int:
    # Use the matching wrapper:
    hook_runtime.run_telemetry_hook(_NAME, core)   # telemetry
    # hook_runtime.run_nudge_hook(_NAME, core)     # nudge
    # hook_runtime.run_compliance_hook(_NAME, core) # compliance
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Which wrapper to use

| Class | Wrapper | Exit behavior |
|---|---|---|
| `telemetry` | `run_telemetry_hook` | ALWAYS emit_continue + exit 0 |
| `nudge` | `run_nudge_hook` | ALWAYS emit_continue + exit 0 |
| `compliance` | `run_compliance_hook` | exit 2 if `core()` returns str; exit 0 if None |

Nudge hooks with custom detection (e.g. reading the session ledger) typically **inline** the steps of `run_nudge_hook` (`hook_enabled` -> `core` -> `emit_continue`, all exceptions -> `log_hook_error`) rather than calling the wrapper — real examples: `cook_isolation_nudge.py` and `discover_isolation_nudge.py`. Both forms are valid; the wrapper is concise for nudges that only return a message;
inline is appropriate when detection logic must run before deciding whether to prompt.

The compliance wrapper handles: ImportError -> exit 2 + install command; crash -> exit 2 + audit trail + emergency bypass instructions. No external try/except needed.

## hook_runtime helpers — actual API

```python
import hook_runtime

hook_runtime.hook_enabled(name, hook_class)    # bool: should it run?
hook_runtime.read_stdin_json()                 # dict: payload from Claude Code
hook_runtime.emit_continue()                   # stdout: {"continue": true}
hook_runtime.log_hook_error(name, exc)         # crash log, fail-open
hook_runtime.resolve_actor(session_id=None)    # str: attribution (not authn)
```

## harness-hooks.yaml — enabled/mode overrides

`"${HARNESS_BIN_ROOT:-.}"/harness/data/harness-hooks.yaml` only records overrides; class defaults apply when a hook has no entry:

```yaml
hooks:
  <hook-name>: {enabled: false}        # emergency disable — leaves a git diff
  <hook-name>: {mode: advisory}        # compliance -> warn, no block (opt-in)
```

Hook with no entry -> class default applies:
- telemetry: `enabled: true`
- nudge: `enabled: false`
- compliance: `enabled: true, mode: blocking`

## Compliance hook — additional requirements

1. **exit 2 + actionable reason**: `core()` returns a clear string reason — the user can read it and knows how to fix it. Do not return a numeric code or exception traceback.
2. **Fail-closed**: any exception in `core()` -> wrapper blocks with exit 2 + audit.
3. **Registration required**: add the filename to `"${HARNESS_BIN_ROOT:-.}"/harness/install/hooks-registration.yaml`. CI test `TestComplianceRegistration` verifies this — unwired = no protection.
4. **Do not import skill code**: hooks are runtime; skills are LLM prose. `TestHookImportBoundary` catches violations.

## Nudge hook — additional notes

- Default OFF — user must enable via harness-hooks.yaml: `{enabled: true}`.
- Core may return `None` (silent) or `str` (print advisory to stderr).
- Never blocks — must `emit_continue()` and exit 0.
- Real example: `harness/hooks/cook_isolation_nudge.py`.

## Real examples

- Telemetry/nudge pattern: `harness/hooks/cook_isolation_nudge.py`
- Compliance pattern: `harness/hooks/gate_stage.py`
- Runtime helpers: `harness/hooks/hook_runtime.py`
