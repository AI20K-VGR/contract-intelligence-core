# R10 — post-audit: audit the eval you just built

R10 is Phase 6 of the bootstrap. It runs AFTER Phase 5 Verify and BEFORE the
append-lesson step. Its target is the NEW eval itself — the failure mode the
mutation matrix alone never catches: an eval that grades itself with an answer
key copied from the same code it judges. Two halves — a
deterministic machine pass (R10a) and an advisory judgment pass (R10b).

## R10a — deterministic (machine runs it, no LLM)

Confluence of the three mechanical checks built across this fix. All three are
deterministic; none uses an LLM. Run each, read each verdict:

1. **Code-sensitive mutation matrix** — `scripts/mutation_matrix.py generate`
   then `run`: with the code vehicle (≥1 `pipeline_mirror` + ≥1 `check_p0_gates`
   mutation) this now breaks the CODE, not just the answer key. A python card
   that is not code-mutation-proven refuses at generate time.
2. **CI wiring** — `scripts/ci_wiring_check.py --target . --config
   evals/eval_config.json`: is the stamped workflow PLACED where the forge runs
   it (not just sitting in `evals/ci/`)?
3. **Ground-truth notes-lint** — `scripts/gt_notes_lint.py --ground-truth
   <path>`: does any note name production/the code as the answer-key SOURCE?

R10a is advisory in aggregate (each script's own `--strict` gates if you want a
hard stop); it is a machine cross-check, not a new gate on the eval's exit code.

## R10b — sealed-room re-derivation (advisory, judgment)

R10b re-derives the case-matrix expectations from the SPEC alone and diffs them
against the committed ground truth, so a key that was quietly copied from output
surfaces as a divergence. It is spawned as an AGENT — the
`hs:independent-revalidator` subagent, via `subagent_type:
"hs:independent-revalidator"` (a fresh-context Claude; per DP-6 context
isolation is what R10b needs — model-diversity via the partner/gemini lane is an
optional `--flag`, not required). Because it is an agent and not a stashable
skill, confirm the `subagent_type` actually spawns: a typo or an absent agent
falls back silently to the default `claude`, which is NOT independent — if it
will not spawn, STOP and report, do not "read it inline".

**It is advisory — it never gates the eval's exit code.** The operational gates
(scorer + P0 + threshold + the code-sensitive mutation matrix) stay
deterministic and keep gating. Skipping R10b means "less audited", not "broken".

### Flow (with the degrade path)

1. **Find the exam question.** Run `scripts/spec_scan.py --target .` (or scan by
   hand) to LIST candidate independent-spec docs (AC / DEC / requirements /
   README / ADR). The list is by filename only — it decides nothing.
2. **Ask the user** which candidate is the authoritative, independent spec —
   the statement of what the code is SUPPOSED to do, authored separately from
   the code.
   - **A separate spec exists** → the subagent re-derives the expected values
     from THAT spec. Label the result `confidence: HIGH`.
   - **No separate spec exists** → generate a `derived-spec` FROM the code for a
     human to approve, then feed the **human-approved** derived-spec as the exam
     question. Label the result `confidence: LOW — spec derived from code`.
3. **Spawn the sealed-room subagent** on the chosen spec. It re-derives each
   case's expected value from the spec, then diffs against the committed ground
   truth and reports: divergences (a possible copied-from-output key), a
   ground-truth-independence audit, and case-coverage-vs-spec.
4. **A human reads the report** and only then decides whether to append a
   lesson. Nothing here auto-appends.

## The three locks (do not remove — they stop the self-eating-tail trap)

1. **A human MUST approve the derived-spec.** The machine generating a
   derived-spec from code and then grading itself against it is FORBIDDEN — that
   is exactly the original "set your own exam and mark it yourself" bug. The
   human approving the derived-spec is the link that injects an independent
   "what the code SHOULD do" judgment. A rubber-stamp approval makes the result
   worthless, and the `LOW` label says exactly that.

2. **The subagent must not read code / production / the mirror / ground_truth —
   enforced by a falsifiable READ-TRAIL, not by a promise.** The
   `hs:independent-revalidator` agent has `Read` + `Bash`, and no tool-fence or
   cwd-jail hard-stops a `Bash` read at an absolute path — so this is NOT a
   mechanical seal. Instead: the subagent MUST list EVERY path it read into its
   report, and the human gate REJECTS the run if that read-trail contains
   `ground_truth.json`, the mirror, production source, or `scorer.py`. Label the
   containment honestly: `containment: prompt-only best-effort` — a best-effort
   prompt constraint audited after the fact, in the same spirit as the R9
   sandbox's best-effort pre-filter. Do not describe it as more than that.

3. **Label `confidence` — HIGH vs LOW.** `HIGH` = a separate, independent spec
   drove the re-derivation. `LOW` = the spec was derived from code (even with a
   human approving it). No one may mistake a `LOW` result for a real
   independent guarantee; the label is the disclosure.
