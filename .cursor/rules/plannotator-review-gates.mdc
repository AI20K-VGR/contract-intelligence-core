# Plannotator review-gates -- optional review surface for every approval gate (on-demand)

At every gate requiring a HUMAN to approve an artifact, instead of forcing the
user to read-then-reply manually, OFFER the option to open a Plannotator review
directly. Plannotator is an EXTERNAL tool, optional -- the harness does NOT hard-
depend on it; without it, the gate degrades to a plain question (flow does not break).

## When to apply -- gate -> surface -> artifact

| Gate | Skill | Surface | Target |
|---|---|---|---|
| Red-team disposition | hs:plan (b4) | annotate | `plans/<p>/reports/...red-team...md` |
| Validate | hs:plan/validate-gate | annotate | `plans/<p>/plan.md` |
| Plan approval | hs:plan (human finalize) | annotate | `plans/<p>/plan.md` |
| Per-phase / review-decision | hs:cook | review | diff working-tree |
| Verdict | hs:test | review (diff) / annotate (QA report) | diff / report |

## How to ask (AskUserQuestion)

1. **3 explicit options**, recommended FIRST (convention from `validate-gate.md`):
   `Review directly (Plannotator) (Recommended)` / `Approve` / `Reject`.
2. **Do NOT add a "chat/free-type" option** -- AskUserQuestion already generates
   an "Other" field for free-text input; treat "Other" content as feedback.
3. Plain, non-technical language; use everyday analogies.

## Mechanism (helper, fail-open)

Run: `python3 harness/scripts/plannotator_surface.py <annotate|review> <target>`
-- markdown (plan.md, red-team report) -> `annotate`; code diff -> `review`.
Helper prints one line of JSON `{"status": ...}`; branch on status:

> **Always this wrapper, never the bare `plannotator-annotate` Skill.** The wrapper
> appends `--gate` (the flag that adds the **Approve** button); the bare skill runs
> `plannotator annotate` without it, so the UI opens annotation-only (Send / Close,
> no Approve) and the user cannot approve from it. "Approve button missing" ⇒ the
> launch dropped `--gate`. Folder vs single-file is irrelevant — the server passes
> `gate` in both modes. (See `harness/LESSONS.md`.)
>
> **This is now enforced, not just advised.** The compliance gate
> `plannotator_wrapper_guard` blocks a bare annotate on BOTH the Bash lane (a
> hand-typed / `!`-command `plannotator annotate ...`) and the Skill lane (a
> `Skill(plannotator-annotate)` call), fail-closed with a redirect to this wrapper.
> Only `annotate` is gated — `review` has no `--gate` flag so it passes. Break-glass:
> one switch `plannotator_wrapper_guard: {enabled: false}` in `harness-hooks.yaml`
> silences both lanes (the diff is tracked). Its runtime crash/timeout path fails
> open, so a guard runtime error never wedges a whole Bash/Skill lane.

| status | action |
|---|---|
| `approved` | record approval and continue (see "Recording decisions") |
| `annotated` | apply `feedback` (edit artifact) then **re-gate** (ask again) |
| `review_text` | read `feedback` plaintext: if it is an approval prompt -> continue; otherwise treat as feedback and edit |
| `dismissed` / `skipped` | fall back to the standard 3-option AskUserQuestion |
| `unavailable` | helper prints install instructions to stderr -> fall back to manual read |
| `error` | fall back to manual read (does not block) |

## Recording decisions (do NOT create a new writer)

- Plan approval gate -> `python3 harness/scripts/plan_approval.py` (v4.0.0 SLIM: self-approval,
  no role/quorum rule — only `plan_hash` anti-drift + mandatory sidecar). Required flags: `--plan`,
  `--verdict`, `--rationale`; `--author` is auto-resolved (trace event > plan.md `author:` frontmatter,
  which scaffold stamps) and only needed for an old plan lacking that line. See the CLI `--help`.
- cook/test -> `review-decision.json` / `verification.json` (schemas in `harness/schemas/`).

## Safety

- **Env-gate**: helper returns `skipped` when `CI`/`GITLAB_CI`/`GITHUB_ACTIONS` or
  `PLANNOTATOR_DISABLE` is set -- do NOT open a browser in CI/headless/e2e.
- **Reliable backstop**: the compliance gate (`gate_stage.py` -> `artifact_check.py`)
  re-surfaces this option in its block-reason when the approval artifact is missing --
  the option is not forgotten even if the skill forgets to offer it.
