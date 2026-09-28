# Human gates, evidence, and artifacts — shared by `hs:plan` and `hs:cook`

## When to stop and ask (and how)

Three triggers, all hard:

- **A deviation from the approved plan.** Stop and ask. Never silently change what the plan
  says, however obvious the improvement looks from inside the phase.
- **A side effect you did not plan for.** Stop, ask with 2–4 concrete choices (what is
  affected, what caused it, what the options cost). Do **not** self-patch a regression, and do
  not advance while any unverifiable claim is still outstanding.
- **A verdict below its floor** (see the grid judgment file). Surface, ask, proceed only on an
  explicit confirm.

**How to ask well:**

- Output a **visible recap before the first question**. The interview often runs in a fresh
  session where the user has never seen the artifact you are asking about; a question that
  references unseen content appears to come from nowhere.
- Put the **recommended option first** and mark it as recommended. For an approval-type
  question, offer the direct-review option first.
- **A user who overrides your recommendation is a normal outcome.** Record the choice and move
  on. Do not argue back unless you have new evidence — repeating the same argument louder is
  not new evidence.

## Every claim carries its anchor, or it carries a tag

A claim with no `file:line` (or SHA, or captured output) behind it is tagged `[ASSUMED]` —
`[PRIOR]` when it comes from training knowledge rather than this repo. This applies to your
**own** decisions too, not just to a subagent's report: a decision finalized by analogy with
no anchor is a finding, not an exempt choice, and an item on any design checklist with no
evidence behind it is `[ASSUMED]`, not a settled call.

Five invariants that follow from that:

1. every claim is anchored to something re-derivable;
2. an unverifiable claim is **rejected downstream**, not carried;
3. the **artifact** is the source of truth — never a verbal statement in the transcript;
4. **a self-report does not self-approve**; the gate reads the artifact and the verdict policy;
5. every significant step leaves a trace.

## What "high risk" means (this definition gates the auto-stop)

Auth · secrets · payments · database schema · public API contracts · CI/deploy/release ·
migrations · destructive filesystem operations · production config.

If the work touches one of these, it is high-risk, and the rules below change accordingly.

## Approval rules for any machine-written verdict

- A **score never approves by itself.** Numbers inform; they do not decide.
- **Any evidenced critical issue blocks**, whatever the rest of the report says.
- A `PASS_WITH_RISK` may continue on a **soft** stage only, and the risk must be stated.
- Autonomous mode may auto-approve **only** when all three hold: the review verdict is `PASS`,
  the artifact validator passes, and the risk gate does not require an auto-stop. Autonomous
  mode skipping human review is for **low-risk, artifact-validated** work — never a blanket
  skip.
- High-risk work under autonomy **stops** and asks before finalize/commit/ship, unless the
  risk-gate record already carries an explicit human approval.
- If artifact generation fails, **retry once**; if it still fails, escalate to the user rather
  than bypassing the artifact. A missing artifact is never "close enough".

## Redaction

An artifact must never contain a raw secret, token, or key. Command output is summarized; when
a snippet is genuinely needed, redact first and mark the record as redacted. An artifact is a
durable, committed file — treat every line of it as published.
