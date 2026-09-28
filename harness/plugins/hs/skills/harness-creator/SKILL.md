---
name: hs:harness-creator
injectable: false
description: Create new harness primitives (hook, rule, schema, data, script, agent) — not skills. Use to add a hook/script/rule/schema/agent to the harness. To create an hs:* skill, use hs:skill-creator.
argument-hint: "[hook|rule|schema|data|script|agent] [name-or-description]"
allowed-tools: [Bash, Read, Write, Edit, MultiEdit, Grep, Glob]
metadata:
  compliance-tier: workflow
---

# hs:harness-creator — create harness primitives (not skills)

Create new **harness primitives** following the correct conventions: hook, rule, schema, data, script, or agent. Every primitive must include a **TDD test** and **real backing**.

**Boundaries with hs:skill-creator**: this skill does NOT create `SKILL.md`/`hs:*` invocable skills — that's `hs:skill-creator`'s job. Primitives here typically back other skills.

## Boundaries

- Only create files in `harness/hooks/`, `harness/rules/`, `harness/schemas/`, `harness/data/`, `harness/scripts/`, `harness/plugins/hs/agents/`, or `harness/install/hooks-registration.yaml` (Step 4 registration).
- Do NOT edit shared files (catalog.py, CLAUDE.md, BACKLOG.md, STANDARDIZE.md).
- Do NOT create a new compliance hook without a `TestComplianceRegistration` test.
- On completion: return the absolute path + pytest invariant result + STANDARDIZE row.

## Primitive decision table

| I want to... | Primitive | Required backing |
|---|---|---|
| Block/record a tool call at runtime | **Hook** | TDD test + hooks-registration.yaml |
| Set an on-demand contract for an agent/skill | **Rule** | cited by name in the skill/agent |
| Describe the schema of a machine-written artifact | **Schema** | gate that reads this artifact |
| Store human-editable policy | **Data** YAML | script/gate that reads this file |
| Analyze or inspect (no blocking) | **Script** analyzer | TDD test |
| Check and block (exit 2) | **Script** gate | TDD test + stage-policy wiring |
| Tuned agent role | **Agent** | role-prompt, not stack code |

Details for each type: `references/` drawers.

## Process (new)

### Step 1 — Identify the primitive type

Use the table above. If still unclear: read `references/hook-authoring.md` (hook), `references/rule-and-schema.md` (rule/schema/data), `references/script-and-data.md` (script), `references/agent-authoring.md` (agent).

### Step 2 — Write the red TDD test first

Required for hooks and scripts. Write the test in `harness/tests/`, then run it to
**FAIL intentionally** (ImportError/assert). See details: `references/invariants-and-tdd.md`.

### Step 3 — Implement

Create the file, use `hook_runtime` helpers (hook, nudge, compliance wrapper), `trace_log.append_event` / `telemetry_paths.append_event` for store writes.
**Do NOT open state/ files directly** — only through shared writers.

### Step 4 — Register (if compliance hook)

Add the filename to `"${HARNESS_BIN_ROOT:-.}"/harness/install/hooks-registration.yaml`. Verify that `TestComplianceRegistration` passes.

### Step 5 — Validate

```bash
python3 -m pytest harness/tests/test_bug_class_invariants.py -q
python3 -m pytest harness/tests/ -q
```

See the full checklist: `references/invariants-and-tdd.md`.

### Step 6 — Compose the STANDARDIZE row (return it — do not edit `docs/STANDARDIZE.md`)

```
| ADAPT | <primitive-type> <name> | (native synthesis) | harness/<subdir>/<name> | <notes> | grep-clean invariant + TDD |
```

## Backing (real wiring)

- Hook runtime: `harness/hooks/hook_runtime.py` (`hook_enabled`, `read_stdin_json`, `emit_continue`, `log_hook_error`, `run_telemetry_hook`, `run_nudge_hook`, `run_compliance_hook`)
- Class config: `"${HARNESS_BIN_ROOT:-.}"/harness/data/harness-hooks.yaml` (enabled/mode override — class cannot be changed via config)
- Invariant CI: `harness/tests/test_bug_class_invariants.py`
- Store writers: `trace_log.append_event`, `telemetry_paths.append_event`

## Quick reference

| Content | Drawer |
|---|---|
| Hook class, HOOK_CLASS, wrappers, template | `references/hook-authoring.md` |
| On-demand rule, schema contract, data YAML | `references/rule-and-schema.md` |
| Script analyzer vs gate, store writes | `references/script-and-data.md` |
| Agent role-prompt, format, limits | `references/agent-authoring.md` |
| Red->green TDD, CI invariants, checklist | `references/invariants-and-tdd.md` |
