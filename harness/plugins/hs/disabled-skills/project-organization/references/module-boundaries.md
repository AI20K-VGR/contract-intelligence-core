# Module Boundaries

Rules for when to split a module, where to place boundaries, how to assign responsibility. Stack-neutral — all languages.

## Core principles

**YAGNI before KISS before DRY** (priority order from CLAUDE.md / `harness/rules/`):
- Do not create abstractions before they are genuinely needed
- Split a module only when it reduces real complexity, not to "feel tidier"
- Only DRY when a code block is repeated ≥3 times AND has a real drift risk

## When to split a module

**Split when:**
- A file/module has >1 independent reason to change (genuine SRP violation)
- Logic is used in ≥3 different places and has a drift risk
- The boundary aligns with a clear team or ownership boundary
- The current module exceeds ~300-400 lines AND can be divided by clear responsibility

**Do NOT split when:**
- The goal is only to make a file "look tidier"
- The logic is small and used in only one place
- Splitting introduces hidden coupling through shared state
- There are no tests yet — splitting without tests is blind refactoring

## Boundaries in harness

Harness is organized by functional layer, not feature:

| Layer | Path | Responsibility |
|-------|------|-------------|
| Hooks | `harness/hooks/` | gate compliance, telemetry, nudge — HOOK_CLASS constant in code |
| Scripts | `harness/scripts/` | analytical always-exit-0 (analyzer) or exit-2 (gate); no store RMW |
| Skills | `harness/plugins/hs/skills/` | workflow orchestration — SKILL.md + references/ |
| Rules | `harness/rules/` | on-demand contracts (load when task needs them) |
| Data | `harness/data/` | policy YAML (human-edited); schema JSON (machine contract) |
| State | `harness/state/` | append-only JSONL runtime — not committed, no RMW |
| Tests | `harness/tests/` | pytest; mirror structure of hooks/scripts |

**Ownership rule** (`"${HARNESS_BIN_ROOT:-.}"/harness/data/ownership.yaml`): each zone has a clear owner — check before creating a new file in a zone owned by someone else.

## Module naming rule — name-honesty

A file/module name must describe its **actual** responsibility, accurately and completely:
- `gate_stage.py` → gates stage transitions (compliance, fail-closed)
- `write_guard.py` → tool-mediated config-edit gate (not "all writes")
- `fs_guard.py` → script-path containment helper (not "filesystem guard")

**Name-honesty check:** read the name → guess the content → open the file → compare. If the reality is narrower than the name → rename or narrow the scope.

Over-description is prohibited: for example, inflating `fs_guard`'s scope past "script-path containment helper" — implying it stops writes broadly — is incorrect (harness-contract.md wording clause).

## When to create a references/ drawer

A skill/doc gets references/ when:
- The core SKILL.md would exceed ~140 lines if all detail were kept inline
- Part of the content is only needed for specific tasks (on-demand)
- The content is cohesive enough to stand alone (not a loose fragment)

**Do NOT create references/** when:
- The core is already short (≤80 lines) — keep it flat
- The content is too small — add it directly to SKILL.md

## Dependency direction

Harness uses implicit dependency injection by convention, not a DI framework:
- Hooks receive context via stdin JSON (Claude Code protocol)
- Scripts receive command-line args; output stdout JSON (analyzer) or exit 2 (gate)
- Skills orchestrate via prose, not direct import of hooks/scripts

**No cycles:** hooks do not call hooks; analytical scripts do not call gate scripts.

## Modularization checklist (before splitting)

- [ ] Are there tests for the current behavior? (TDD — splitting without tests is risky)
- [ ] Does the new responsibility have a clear name? (name-honesty)
- [ ] Will the new file live in the correct layer? (harness layer table above)
- [ ] Does the split introduce hidden coupling?
- [ ] Does `"${HARNESS_BIN_ROOT:-.}"/harness/data/ownership.yaml` have any zones that are affected?
