---
name: hs:rule-author
injectable: false
description: >-
  Author a safe per-repo review-rule override in the layer-b folder docs/standards/ — detect conflicts with the
  shipped standards, narrow an overlapping scope when the intent differs, and on a real conflict confirm with
  you and record a mandatory reason. Use when you want to tune, disable, or add a review rule for this repo
  without editing the shipped standards tree, or when a review keeps flagging a rule that does not fit here.
  Output is static; review-time reads it deterministically, no LLM per review.
allowed-tools: [Bash, Read, Write, Edit, AskUserQuestion]
argument-hint: "[paste rules/context, or describe the rule you want]"
metadata:
  compliance-tier: workflow
---

# hs:rule-author — author a per-repo review-rule override

The authoring-time companion to the operational standards layer. The review-time consumer (`rule_view` + `user_override`) reads layer-b override files statically; this skill WRITES them, safely. Never mutates the shipped standards tree (`harness/standards/**`) — only repo-local override files.

**Where the override lives** — `user_override` reads, in precedence order: env `HARNESS_USER_OVERRIDE` (a file OR a dir) → the knob folder `user_rules_dir` (`"${HARNESS_BIN_ROOT:-.}"/harness/data/standards.yaml`, default `docs/standards/`, reads every `*.yaml`)
→ legacy single file `standards.user.yaml` at the repo root (fallback only, used when the folder holds no override files). WRITE to the knob folder (`docs/standards/<name>.std.yaml`), NOT the legacy root path — a folder file shadows the root one, so a root write silently stops being read the moment the folder is populated. Read the knob before writing: `python3 -c "import sys;
sys.path.append('harness/scripts'); import user_override; print(user_override._knob_user_rules_dir('.'))"`.

## Why a dedicated skill

A review-rule override is easy to get wrong: silently weaken a safety rule, shadow a floor rule with a new id, or write a glob overlapping a shipped rule unintentionally. This skill front-loads the judgment ONCE, at authoring time: every later review is a deterministic file read — no LLM cost per review, no drift between intended and enforced.

## Inputs

Either form works:
- **Paste**: rule snippet, code example, or review finding to suppress/adjust.
- **Interview**: invoked bare — asks target rule, scope (files), severity.

## Flow

1. **Gather intent** — the target rule id (to modify an existing rule) or a new id (to add one), the scope globs, the severity, and whether to enable/disable.
2. **Load the current rules** — build the operational rule set: `rule_view.load_rules(root, scope_intersects=None)` gives every operational rule (`None` = no scope filter, unlike `[]` which matches nothing); read each rule's `scope`, `severity`, `floor`.
3. **Detect conflicts** — `user_override.detect_conflicts([proposed], std_rules)` flags a proposed rule whose scope overlaps a shipped rule with an opposite severity. Disjoint scopes never warn (P0 glob-intersection, not substring guess). See `references/conflict-resolution.md`.
4. **Resolve**:
   - **Phantom conflict** (scopes overlap but the intent is for a narrower set):
     propose a narrower glob so the two no longer overlap, and re-check.
   - **Floor rule** (`floor: true`): STOP. A floor rule is non-overridable and a
     new-id rule that shadows it with a weaker posture is refused by the loader.
     Do not write the override — explain that the rule is a floor.
   - **Real conflict** (genuinely want to override a non-floor rule): confirm
     with the user via AskUserQuestion, then collect a mandatory `reason:`.
5. **Write the override file** — to the knob folder, `docs/standards/<name>.std.yaml` (NOT the legacy root
   `standards.user.yaml`). Append/merge the override entry in the schema
   (`"${HARNESS_BIN_ROOT:-.}"/harness/schemas/standards-user-override.json`): `{rule_id, reason, ...fields}`
   under an `overrides:` list. Every entry carries a non-empty reason. `mkdir -p docs/standards/` first if the
   folder is absent.
6. **Verify** — re-load with `user_override.load(root)` and `user_override.apply(...)`; surface the warnings it returns (each override is loud by design) so the user sees what changed and what was refused.

## Hard rules

- NEVER write an override without a non-empty `reason:` (the loader refuses it).
- NEVER attempt to override or shadow a `floor: true` rule — explain instead.
- NEVER mutate `harness/standards/**` — this skill writes ONLY the repo-local layer-b override files in the knob folder (`docs/standards/`, default). The legacy root `standards.user.yaml` is a read-fallback, not the write target.
- The output is STATIC: do not wire any LLM call into review-time. Review reads the file.

## Pairs with

- `hs:remember` — the reverse handoff. Authoring/changing an enforcement rule IS an architectural decision (changes what the gate blocks) — after writing the override, propose a DEC + rationale via `hs:remember` (plus a memory when non-obvious). Symmetric loop: remember PROPOSES the rule on a rule-worthy pattern; rule-author
  PROPOSES the record after authoring — neither writes the other's artifact.

## References

- `references/conflict-resolution.md` — the conflict/scope-resolution procedure, a narrow-glob worked example, and the `standards.user.yaml` format.
