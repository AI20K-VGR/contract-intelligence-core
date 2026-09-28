---
name: hs:ship
injectable: false
description: "Gated ship pipeline: review PASS → verification PASS → human approval → push/pr. Highest-risk stage — all gates must be real. Use when a completed branch needs to become a PR."
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task]
argument-hint: "[official|beta] [--skip-tests] [--dry-run]"
metadata:
  compliance-tier: workflow
---

# hs:ship — gated ship pipeline

`hs:ship` is the harness's highest-risk skill. It **does not bypass gates** — it orchestrates all prerequisites before push/PR reaches the transport layer.

**What each step needs is routed by the CLI, not listed here.** Every `hs-run ship next`
envelope carries the `rules` and `references` THIS state needs, plus an `advisory` when the
step has one. Read what the envelope names, and only that. But satisfying the envelope is
**not enough** to have shipped: it routes DOCUMENTS, and the receipt on disk and the branch
itself are the artifact the step changes — open them.

**Gates (personal-first)**: `harness/hooks/gate_stage.py` + `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` ADVISE on stage `ship` when artifacts are missing (exit 0 + `[advisory]`);
the pre-push hook `harness/install/git-pre-push-hook.sh` WARNS on a missing receipt but still BLOCKS the two Tier-A floors (destructive-to-protected + secret). Hard presence enforcement is the remote receipts-gate.

**`hs:ship` (this skill) ≠ the `ship` stage.** The `ship` stage in `stage-policy.yaml` is triggered by release/publish verbs (`gh release create`, `npm publish`, `docker push`) — which this pipeline never issues. Two gated transport points:
- **Step 10 `git push`** → the `push` stage, which requires only `verification` and only **ADVISES** locally.
- **Step 11 `gh pr create`** → the `pr` stage, which requires **all 3 artifacts**:
  - `verification` — verdict PASS **or PASS_WITH_RISK**, with no check that is not PASS/SKIP. (Read that as it is written: the strict PASS-only rule belongs to `review-decision`, not here. This is the gate that has always been running, not a loosening.)
  - `review-decision` — verdict **exactly PASS** (PASS_WITH_RISK does not qualify)
  - `plan-approval` — verdict APPROVED + plan hash has not drifted. **Personal-first SLIM: no roster, no reviewer≠author check — self-approval is allowed by design.** "No self-ship" is therefore NOT machine-enforced; treat it as a human-discipline directive if you want it.

**Nothing local hard-blocks either one.** `gate_stage.py` downgrades EVERY hard stage to an
advisory and returns without blocking — the `pr` stage included. The real enforcement is the
remote receipts-gate in CI. Treat a clean local run as "nobody stopped me", never as "the
gate passed me", and note the separate change-class DoD layer: a `git push` can print an
`[advisory]` about a required test type carrying no result file even on a tree where
`hs-run ship next` reports `ready`, because that layer runs after the artifact check clears.

An org wanting a stricter gate can add a 4th — `critique-consensus.json` (produced by `/hs:critique --gate`) — by listing `critique-consensus` in the `pr`/`ship` stage's `requires` in `stage-policy.yaml`. It ships **off** so a spine-only install is never blocked by a plugin it has not enabled.

## Arguments

| Flag | Effect |
|------|----------|
| `official` | Target main/master — full pipeline |
| `beta` | Target dev/beta branch |
| (empty) | Infer from branch name; ambiguous → ask |
| `--skip-tests` | Skip the test step (use when tests were already run separately) |
| `--dry-run` | Show the plan, do not execute |

> `--skip-tests` reuses the existing `verification.json` — only sound when it was
> produced in THIS branch state. A stale artifact from an earlier state passes the
> gate on evidence that no longer matches the diff (the Iron Law: a stale run is not
> a pass). Re-run tests if HEAD moved since the artifact was written.

## When to STOP (blocking)

- Currently on the target branch → ABORT
- Merge conflict that cannot be auto-resolved → STOP, show conflicts
- Tests fail → STOP, show failures
- `hs:code-review` returns `review-decision` verdict ≠ PASS → STOP, ask
- Artifact missing → **you MUST stop** — no local gate will stop you. The push gate advises, and the `pr` stage advises too; the remote receipts-gate is the only place presence is truly enforced, and it runs after the push.
- Artifact drift (plan modified after approval) → the `plan-approval` check fails on the `pr` stage; stop and re-approve

## When NOT to ask

- Commit message → compose from diff + commit log
- Patch version bump → decide autonomously
- Changelog → generate automatically (do not ask for content)
- No version/changelog file present → skip silently

## Pipeline

```
Step 1: Preflight         → check branch, mode, diff, dry-run
Step 2: Merge target      → fetch + merge origin/<target>
Step 3: Test              → delegate hs:test (auto-detect runner)
Step 4: Review            → delegate hs:code-review → writes the review-decision receipt
Step 5: Verification      → hs:cook has written the verification receipt (check it)
Step 6: Plan approval     → the plan-approval receipt must exist
Step 7: Changelog/Version → generate automatically, no prompts
Step 8: Release notes     → the `ready` state routes the drawer
Step 9: Human confirm     → `hs-run ship next`, THEN a live AskUserQuestion confirm BEFORE push (REQUIRED — this is the description's "human approval")
Step 10: Commit + Push    → conventional commit + git push (via pre-push hook)
Step 11: PR               → gh pr create with standard body
```

**Step 9 gate call.** `hs-run ship next` judges the **`push`** stage and reports what to do
about it. A refusal carries the gate's own reason verbatim in `next_action` — fix what it
names, in the place the state names. exit 10 `ready` → the gate checked and found nothing
missing; it deliberately hands back NO runnable command, because `ready` is the input to the
confirm below and never a substitute for it. exit 10 `gates_not_enforced` → the policy
required nothing here, so nothing was checked: that is "nobody asked", not "you are covered".

**It does not replace Steps 5-6.** `push` requires `verification` only; `pr`/`ship`/`merge`/
`deploy` require `verification` + `review-decision` + `plan-approval`. A clear gate call is
one artifact checked, not three — run Steps 5-6 as written.

**Autonomous self-ship is prohibited.** The gates are personal-first and self-approvable (an agent can
write its own PASS artifacts), so the ONLY real human checkpoint is Step 9's live confirm — the
description's "human approval" means a live `AskUserQuestion`, NOT a pre-existing `plan-approval.json`.
A `ready` from the gate call is not that confirm and never stands in for it.
This MUST out-ranks the proactive "just push it" bias. (The "When NOT to ask" items below scope to commit-message / version / changelog content only — never the push itself.)

**Role split:** `hs:ship` delegates the test run (Step 3 → `hs:test`) and review (Step 4 → `hs:code-review`) but **owns git transport inline** (commit/push/PR) — no hand-off to `@git-manager`.

## Step 4 — Review (real gate)

`hs:code-review` writes the review-decision receipt into the active plan's `artifacts/`. Verdict must be `PASS` — `PASS_WITH_RISK` does not qualify for ship. If verdict ≠ PASS: AskUserQuestion (fix now / accept risk / cancel).

**Simplify before review**: scan the branch diff first — a special case, a duplicated pattern, or an abstraction earning its keep nowhere should be collapsed before review. A smaller diff is a cheaper review and a smaller risk surface. Pattern library: `harness/plugins/hs/skills/problem-solving/references/simplification-cascades.md`.

## Steps 5-6 — Artifact check

Run `hs-run ship next`. It reads the same receipts through the same public entry point the
gate itself uses, so its answer cannot disagree with the gate — and it names which of them is
missing, unusable, or fine. Do not hand-write a check beside it: a second reader of the same
files is a second opinion that drifts, and the one nobody runs is the one that lies.

## HARD-GATE (real wiring)

| Gate | Real backing |
|------|-------------|
| Stage ship (artifact check) | `harness/hooks/gate_stage.py` + `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` |
| Transport layer (pre-push) | `harness/install/git-pre-push-hook.sh` |
| Plan approval artifact | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/plan_approval.py` + `harness/schemas/artifact-plan-approval.json` |
| Review decision artifact | `harness/schemas/artifact-review-decision.json` (verdict PASS strict) |
| Verification artifact | `harness/schemas/artifact-verification.json` (no FAIL check) |

**Do not shortcut the gate.** If a gate blocks incorrectly, investigate the artifact — do not edit the hook.

## Boundaries

- DO NOT force-push any branch.
- DO NOT proceed when artifacts are missing — you MUST stop; no local gate blocks, so the only real enforcement is the remote receipts-gate, and it runs after the push.
- DO NOT commit secrets — scan the staged diff before committing (pattern: `AKIA|token|password|secret`).
- On exit: return the PR URL. If the gate refuses, return the state it reported and the reason it carried.
- Enable `hs:context-engineering` if context is nearly full before this long pipeline.
