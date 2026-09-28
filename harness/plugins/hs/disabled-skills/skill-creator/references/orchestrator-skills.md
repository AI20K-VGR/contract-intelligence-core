# Authoring orchestrator skills

An orchestrator is a skill that wraps multiple `hs:*` meta-skills into a fixed workflow (hs:cook, hs:discover, hs:triage, hs:understand). It differs from a leaf skill (does one thing).
Full contract: the Orchestrator skill contract section in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` — read before writing.

## When to create an orchestrator (not a leaf skill)

Create an orchestrator when the workflow:
- Repeats, consisting of >=2-3 different skills in a fixed order.
- Has a clear input contract and handoff output (brief, map, verified fix).
- Does NOT duplicate an existing orchestrator (cook = execute plan, plan = design).

Single responsibility -> leaf skill. Duplicates cook/plan -> do not create.

## Thin-core orchestrator template (modeled on hs:cook)

1. **Frontmatter** standard (name/description/user-invocable/metadata) — same as a leaf skill.
2. **Input block** at the top: what is needed to run; missing input -> where to return, no guessing.
3. **Chain steps** numbered: each step CALLS a component skill BY NAME (`hs:research`, `hs:fix`...), <=3 lines per step; details -> drawer.
4. **Gate or Handoff block**:
   - Produces a machine-readable artifact that a gate reads -> "HARD-GATE (real wiring)" pointing to a real gate. REUSE
     `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` + existing schemas; do not invent a new gate.
   - Produces only documentation -> "Handoff" pointing to `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` + chain.
5. **Boundaries**: what NOT to do (e.g. do not edit code directly if hs:fix has been delegated), when to escalate, out-of-scope -> record via `backlog_register.py add`.
6. **References table**.

## Backing-or-cut for orchestrators

Every chain step must point to a component skill that EXISTS (check `load_catalog()['owned']`). Every gate claim must point to a real gate/schema. No phantoms: if a "gate" is intended but no suitable artifact/gate exists -> either reuse what is available, or downgrade to a soft handoff.

## Wiring into the system (required for new orchestrators)

- `"${HARNESS_BIN_ROOT:-.}"/harness/data/skill-chains.yaml`: add the pair `[hs:<orch>, hs:<next>]`.
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md`: add the handoff line.
- Isolation nudge (if the handoff carries heavy context) -> author a hook via `hs:harness-creator`.

## Common mistakes

| Symptom | Fix |
|---|---|
| Copied child skill logic into the orchestrator | Call by name, remove the copied logic |
| Invented a new gate when verification.json already exists | Reuse `gate_stage` + existing schema |
| Over-claimed name (triage "fixes" bugs) | Name-honesty: orchestrator coordinates; child skill does the work |
| Forgot to register the chain | Add to skill-chains.yaml + workflow-handoffs.md |
