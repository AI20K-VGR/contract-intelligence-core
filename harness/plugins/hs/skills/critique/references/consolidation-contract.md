# hs:critique — consolidation contract (on-demand)

Load when consolidating lens findings into one verdict. `hs:critique-consolidator` owns the logic; this is the controller's contract for what to pass in and what comes back.

## Pass in

- The JSON finding arrays from every lens that ran (see `critique-protocol.md` for the shape).
- Prior critique reports under `plans/reports/` (for repeat-offense detection).
- The scope label and the artifact type.
- Names of any lenses that failed or returned `[]` — so the consolidator marks them missing, not passing.

## What the consolidator does

1. **Cross-lens dedup** — same anchor/root cause merges into one finding, naming every lens that raised it. Agreement across lenses = signal, surfaced not hidden.
2. **Anti-overlap floor** — drop any finding lacking a non-empty `why_it_matters` AND `fix`.
3. **Severity** — `blocker > major > minor`, by blast radius × reachability. A `proven` finding outranks a `suspected` one at equal nominal severity.
4. **Top findings** — the three most threatening across all lenses, each with severity, lens, anchor, consequence, fix.
5. **Repeat-offense (attached last)** — findings seen in prior reports get an occurrence count (×N) and prior references. This is metadata: deleting the findings list must not change the repeat set.
   **Correlation via fingerprint (S5)** — the consolidator computes each finding's `fingerprint` (`dismissals_store.fingerprint()`, best-effort, `null` when `anchor` is not `file:line`) at the same step it settles `code_evidence`. Because the fingerprint drops the line number, it survives a reformat that shifts lines —
   match on `fingerprint` first when correlating a finding against a prior report, falling back to the anchor+finding text only when `fingerprint` is `null`.
6. **DEC-worthy flag** — items implying an architectural decision are flagged for the controller to raise with the user (the consolidator does not record DECs itself).
7. **Batch-validate every finding through the verdict truth-table** (`harness/plugins/hs/skills/code-review/references/verdict-truth-table.md`) — each surviving finding gets a per-finding verdict (`confirmed` / `dismissed` / `needs-human`) with `code_evidence` mandatory on `confirmed`; any condition FALSE ⇒ `dismissed`. This batch pass belongs **here only** — critique has already run blinded,
   multiple independent lenses, so cross-checking every finding adds signal. It is **NOT** bolted onto the default single-reviewer code-review path, where one reviewer batch-validating their own findings adds ceremony without an independent second opinion.

## What comes back

One consolidated markdown body (neutral tone) plus a proposed verdict:

- **BLOCKED** — at least one `proven` blocker survived.
- **PASS_WITH_RISK** — no surviving blocker, but majors remain, accepted with a named condition.
- **PASS** — no blocker and no unaccepted major survived.

Structure: header (`scope · lenses: … [missing: X]`), severity tally (`blocker N · major N · minor N`), top findings, per-lens sections, repeat-offense section (if any), DEC-worthy section (if any), verdict
+ one-paragraph rationale.

## Controller responsibilities (NOT the consolidator's)

- Write the report to `plans/reports/<slug>-critique-report.md`.
- In gate mode, write the verdict to `plans/<active-plan>/artifacts/critique-consensus.json` (schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-critique-consensus.json`): `verdict`, `reviewer` (resolve_actor), `role: critique`, `rationale`, `ts`, optional `lenses` and `top_findings`. Enforcement ships OFF: shipped policy lists `critique-consensus` at no stage; org opts in via a stage's
  `requires:` in `stage-policy.yaml` → verdict must then be `PASS`.
- Raise each DEC-worthy item with the user and, on confirmation, record it via `decision_register.py`.
