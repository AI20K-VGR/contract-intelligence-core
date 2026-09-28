# Rule, schema, and data — convention and contract

## Rule (`harness/rules/*.md`)

### When to create a rule

A rule is an on-demand contract: agents and skills load it when the task needs it, not always in context. Create a rule when:

- An invariant or contract needs to be defined for use by multiple skills or hooks.
- Detail should be separated from SKILL.md (thin-core) — rules replace references drawers for content shared across the harness (not shared = references drawer).
- Do not create a rule for content relevant to only one skill -> place it in that skill's `references/` directory.

### Format and size

```markdown
# <Rule name> — <short title>

## Purpose
<1-2 sentences: what this adds, what it does not replace>

## <Section 1>
...

## <Section N>
...
```

- Concise — do not repeat content from `harness-contract.md`.
- Cited by relative path when a skill or agent loads it: `harness/rules/<name>.md`.
- No CI test is required for a rule (prose), but if a rule describes an invariant then that invariant must have a test in `harness/tests/`.

### Real backings

- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/harness-contract.md` — posture gate, actor=attribution, store
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — 5 evidence invariants
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md` — red->green required
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md` — subagent delegation

---

## Schema (`harness/schemas/*.json`)

### When to create a schema

A schema describes the contract of a **machine-written artifact** that a gate reads. Only create a schema when:

- A real gate or script will read this artifact to make a block/pass decision.
- The artifact needs to be validated before the gate accepts it (no schema needed if the artifact is only a passive log).

**Do not create a schema** for:
- Human-editable config (use YAML without a JSON schema).
- Append-only logs or traces (JSONL row schemas rarely need a separate file).

### Format

JSON Schema draft 2020-12, minimal:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "<artifact-name>",
  "description": "<gate description: what it is used for, actor=attribution>",
  "type": "object",
  "required": ["stage", "plan", "actor", "ts", "verdict"],
  "properties": {
    "actor": {
      "type": "string",
      "description": "resolve_actor() output — attribution, not authn"
    },
    "ts": {"type": "string", "description": "ISO-8601"},
    "verdict": {"enum": ["PASS", "PASS_WITH_RISK", "BLOCKED"]}
  }
}
```

Required rules:
- `actor` ALWAYS present + description clearly stating "attribution, not authn".
- `ts` ALWAYS present as ISO-8601.
- Verdict enum: `PASS | PASS_WITH_RISK | BLOCKED` (harness standard).
- Filename: kebab-case, matching the artifact name (`artifact-verification.json`).

### Real examples

```
harness/schemas/artifact-verification.json
harness/schemas/artifact-plan-approval.json
harness/schemas/artifact-review-decision.json
```

---

## Data (`harness/data/*.yaml`)

### Classification principles

| Type | Format | Written by |
|---|---|---|
| Human-editable policy | **YAML** | Written by hand |
| Hook override config | **YAML** (`harness-hooks.yaml`) | Written by hand |
| Store event (trace/telemetry) | **JSONL** append-only | Machine via shared writers |
| Gate artifact (verification, approval) | **JSON** | Machine via script |

**Do not mix**: YAML for config/policy, JSONL/JSON for machine-written data. Do not use YAML for gate artifacts — gates require deterministically parseable JSON.

### When to create a data YAML

- Policy that adjusts script or gate behavior: stage-policy, team config, ownership.
- Human-editable override config.
- Do not create data YAML for logs or events — use shared writers.

### Additional rules

- Every machine-written record must have `actor` + `ts` via `resolve_actor()`.
- Store writes: **append-only, no read-modify-write**. Only via `trace_log.append_event` or `telemetry_paths.append_event` — do not open `state/` files directly from code outside the shared writers.
- `TestStoreWriteDiscipline` in `test_bug_class_invariants.py` catches violations.
