# Verification mechanism — evidence rules on-demand (hs:plan/cook/test)

Supplements `harness/rules/harness-contract.md` (posture gate / actor=attribution
/ fail-open-closed are already in the contract — do NOT repeat them). These are the
shared evidence rules.

## 5 verification invariants

Every claim of "done / correct" must be accompanied by **machine-readable evidence**:

1. **Must be anchored**: SHA commit, `file:line`, or real command output. No anchor
   means the claim is `UNVERIFIABLE`.
2. **Downstream rejects UNVERIFIABLE**: the next step (red-team, validate, gate) treats
   an unanchored claim as if it does not exist — do not build further on it.
3. **Artifact is the source, not narration**: verdicts/checks are written to machine-
   readable JSON (`verification.json`, `review-decision.json`), not stated verbally.
4. **Self-report does not self-approve**: the gate reads the artifact plus the verdict
   policy; it does not trust "I PASS" (actor = attribution, not authorization — see
   contract).
5. **Trace keeps a record**: significant steps emit via `trace_log.append_event` (actor
   and ts are resolved automatically).

## Claim typing — the four evidence labels (canonical home)

Type every load-bearing statement by the evidence behind it. The label IS the grammar:
a claim's wording must never out-run its evidence tier.

| Label | Meaning | Allowed grammar |
|-------|---------|-----------------|
| **OBSERVED** | You verified it directly — ran it, read it, measured it — and nothing has changed since | "X is / does / returns …" |
| **DERIVED** | Follows from OBSERVED facts by a mechanism you can state | "X should / will / implies …" + the why |
| **PRIOR** | Training knowledge; may be stale | "X is typically … / was, as of …" — re-check if load-bearing |
| **ASSUMED** | Unverified and required by the conclusion | "assuming X — if wrong, then …" |

Rules (non-negotiable):

- **Only a tool promotes a claim.** Checking a PRIOR or ASSUMED with a real run makes it
  OBSERVED; restating it more confidently does NOT — that is a hallucination wearing
  OBSERVED grammar, the most avoidable kind. **Never relabel an unverified claim UP to
  OBSERVED**; an unrun claim is `[ASSUMED]` (or `[PRIOR]` when it is training knowledge),
  and it stays in that tier until a tool moves it.
- **Downgrade honestly.** When the environment changes, an earlier OBSERVED decays to PRIOR.
- **A rate is not a fact.** When the claim is a rate — accuracy, pass fraction, coverage,
  recall — `[OBSERVED]` requires `k/n` AND an interval; a bare percentage is `[ASSUMED]`.
  Load `sampled-rate-reporting.md` before writing one.
- **"I don't know", followed by what would settle it, is a first-class answer.**

`[ASSUMED]` (and load-bearing `[PRIOR]`) are the evidence-debt tags the downstream gate
(red-team / validate) collects and resolves. The evidence RANKING that decides which rung
a claim can earn lives with probe-first in `agent-operational-discipline.md` ★, and maps
onto these labels: the top rungs (direct observation / reproduction) earn **OBSERVED**; a
primary/secondary source not re-run this session is **PRIOR**; memory alone is **ASSUMED**;
**DERIVED** is what you conclude from OBSERVED facts by a stated mechanism.

## No "done" without fresh-run evidence (the human-side discipline)

The 5 invariants gate the *artifact*; this gates *you*, and the machine gate does NOT
replace it. **Iron Law: no completion claim without verification evidence produced in
THIS turn.** If you have not run the proving command in this message, you cannot say it
passes — a stale/partial run, or "should pass", does not count. Violating the letter
is violating the spirit: a paraphrase or an implied "Done!" is still the claim.

Before any "done / fixed / passing": identify the command that proves it → run it fresh
and complete → read the full output and exit code → only then state the claim, evidence
inline.

| Excuse | Reality |
|--------|---------|
| "Should work now" | Run the verification. |
| "I'm confident" / "seems to" | Confidence ≠ evidence. |
| "Just this once" / "I'm tired" | No exceptions. |
| "Linter passed" | Linter ≠ compiler ≠ tests. |
| "Agent said success" | Verify independently — check the diff. |
| "Partial check is enough" | Partial proves nothing. |
| "Different words, so the rule doesn't apply" | Spirit over letter. |

Red flags you are about to claim without proof: "should / probably / seems"; a "Great! /
Perfect! / Done!" before the command ran; about to commit/push/PR unverified; trusting an
agent's success report; a regression test that passed once but never ran the red→green cycle.

## Evidence filter — bidirectional

The same standard applies in both directions:

- **Finding** (red-team/review): no `file:line` or reproducible command means reject.
- **Planner's own position** (open decision Q-x): finalized by analogy, no `file:line`
  means **evidence debt**, not an exempt choice. Tag `[ASSUMED]` (or `[PRIOR]` if the
  position rests on prior/training knowledge — the claim-typing labels above), bring into
  validate. Without this step, a decision can place the canonical tree
  OUTSIDE the `ownership.yaml` fence zone without any red-team or cook catching it.

## Review, audit & decision discipline

The guardrails that keep a review, an audit response, or a scope cut from silently
undoing verified work or a user's decision. Two classes of decision do NOT get reopened
on an abstract objection:

- **Verified decision** — once a choice is backed by source, a test, or an empirical
  check, an audit/red-team raising only an *abstract* concern does NOT reverse it.
  **Do not reverse** on an abstract audit concern — only on NEW evidence or a changed
  context; when rejecting the concern, state the verification source in one line.
- **User decision** — an explicit user choice (threshold, library, feature scope, schema
  shape, pricing, timeline, compliance choice, UX trade-off) is never silently undone.
  If an audit argues for reversing one, present the original decision, the
  concern, the trade-off, and the concrete options — then wait for the user; do not
  self-apply the reversal.

**Scout first.** For questions answerable by reading the repo, scout before asking. Ask
only on conflicting evidence, missing context, business judgment, or high reversibility risk.

**Threat-model before applying a security/robustness finding.** Identify what the code actually stores, protects, or exposes; fix real failure modes, document non-issues briefly. Ask when the risk is plausible but depends on product intent.

## Artifacts on the filesystem

The gate reads `plans/<plan>/artifacts/*.json` from **disk** (no commit required).
`plans/` is tracked (only `plans/reports/` is gitignored scratch), so artifacts ARE
committed with the plan — the remote receipts-gate reads them from the pushed tree.
Personal-first: the LOCAL gate only ADVISES on a missing/failed receipt (it never
blocks the human); the REMOTE receipts-gate is the hard enforcement layer.
