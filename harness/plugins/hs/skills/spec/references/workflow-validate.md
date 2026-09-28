# Workflow — Validate / Approve / Summary

End-to-end workflow for the **--validate** (+ optional **--strict**) flag — the only one of the
three named in this file's title that `hs:spec` actually exposes (see SKILL.md's Flags table).
**`--approve` and `--summary` are NOT SHIPPED in this build** — neither appears in SKILL.md's
Flags table, and there is no dedicated CLI entry point for either. Their sections below are design
references only; do not offer `--approve` or `--summary` to the PO as invokable flags. Operationalizes
the script-vs-LLM split for `--validate`: scripts produce JSON; the LLM layers judgment; the report
is composed for a human PO.

## `--validate` Flow

### Step 1 — Run structural scripts (in order)

```bash
python3 scripts/spec_graph.py --root <root> --snapshot
python3 scripts/check_traceability.py --root <root>
python3 scripts/check_consistency.py --root <root>
python3 scripts/build_traceability_matrix.py --root <root> --write
```

Each script emits JSON to stdout. Collect the union of `findings[]` across the three checkers. `spec_graph --snapshot` writes a snapshot JSON to `docs/product/visuals/.snapshots/` for later delta viz.

The structural checkers above now also emit the TIME-dimension findings: `dep_cycle` + `dep_dangling` (errors, from `check_traceability`) and `dep_order` + `time_child_late` (warns, from `check_consistency`). These are pure date/graph comparisons — deterministic, in-gate.

**Out-of-gate advisories (run separately, NEVER part of the `--strict` gate — they consume the wall clock or resolve external references):**

```bash
# overdue: target_date strictly before --today (default real today; pin for reproducibility)
python3 scripts/time_advisory.py --root <root> [--today YYYY-MM-DD]
# time_realism anchors: per-epic {size, child_story_count, days_remaining, …} feeder for the LLM check
python3 scripts/time_realism_anchors.py --root <root> [--today YYYY-MM-DD]
# competitive_drift anchors: per-PRD resolved parity map feeder for the LLM check (no --today)
python3 scripts/competitive_drift_anchors.py --root <root>
```

All three exit 0 on a valid run regardless of how many overdue/anchor items they surface (advisories/anchors, not gates) — the calendar never blocks.
They exit non-zero ONLY on a malformed CLI argument (e.g. a non-ISO `--today`), which is input validation, not a finding.
Surface `overdue` to the PO as information; feed the `time_realism` and `competitive_drift` anchors to the LLM pass in Step 2. Keep these OUT of `strict_gate.py` so the structural gate stays byte-reproducible.

For CI (no LLM in the loop), use the shell-runnable strict gate which exits non-zero on any error-severity finding:

```bash
python3 scripts/strict_gate.py --root <root>   # exits 2 on any error finding OR on zero artifacts (add --allow-empty to pass an empty workspace)
```

### Step 2 — Layer LLM judgment on the JSON

For every check in `validation-rules-spec.md` whose owner is LLM (`invest_quality`, `vagueness`,
`core_value_drift`, `gold_plating`, `semantic_duplication`, `time_realism`, `competitive_drift`,
`contradiction`), the LLM judges the current spec graph directly — **there is no judgment-caching
layer in this build** (`scripts/judgment_cache.py` was designed but never shipped), so every
`--validate` re-judges every node from scratch; there is no `--check`/`--store-batch` CLI to call
and no cache staleness key to consult.

- **invest_quality** — for every story: check Independent · Negotiable · Valuable · Estimable · Small · Testable. If any dimension fails, emit a finding (warn).
- **vagueness** — scan story AC and PRD MoSCoW lists for vague terms (`should`, `easy`, `fast`, `intuitive`, `robust`); if found, emit a finding suggesting a quantified rewrite.
- **core_value_drift** — for each PRD/epic/story, score alignment with `PRODUCT.md.core_value` as `aligned | weak | off` + a 1-line rationale. Emit a finding (warn) when `weak` or `off`.
- **gold_plating** — scan PRD scope: does any new requirement go beyond the stated problem? Emit finding (warn).
- **semantic_duplication** — compare every pair of PRDs/epics within the same product for intent overlap. Emit finding (warn) on suspected duplicates.
- **time_realism** — for each epic, read the SCRIPT-precomputed anchor from `time_realism_anchors.py` (`size`, `child_story_count`, `days_remaining`, …) and apply the FIXED rule in `validation-rules-spec.md → time_realism LLM Scaffold`:
  flag (warn) ONLY when `eligible` AND `size=="L"` AND `child_story_count>=6` AND `days_remaining<21`; missing anchor → `missing_anchor` (no flag); otherwise no flag.
  The finding MUST carry `context.cited_data` (verbatim from the anchor). **Do NO date arithmetic** — the script already computed `days_remaining`.
- **competitive_drift** — for each eligible PRD, read the SCRIPT-resolved anchor from `competitive_drift_anchors.py` and apply the FIXED rule in `validation-rules-spec.md → competitive_drift LLM Scaffold`: flag (warn) ONLY when `eligible` (scope `core-value` AND `competitors_with_data >= 2`) AND every real (non-`none`) parity is `behind`; missing anchor / ineligible / any non-`behind` → no flag.
  The finding MUST carry `context.cited_data` (verbatim from the anchor). **Never invent a competitor or parity verdict** — use only what the script resolved.
- **contradiction** — compare every new artifact against `approved`-status artifacts. If contradicted → emit `error`-severity finding + surface to PO via the contradiction protocol (see below). **Never auto-flip.**

A per-change impact-pass (propagating a change to downstream nodes and writing an
`docs/product/impact/<ts>.md` report) was also designed but never wired into a script or workflow
step — do not promise it to the PO. See `workflow-validate-judgment-cache.md` for what remains
available (the graph-diff primitives) versus what is not shipped.

### Step 3 — Compose the human report

Format per `validation-rules-spec.md` § Human Report Format (single authoritative home for the report skeleton: Summary / Errors / Warnings / Suggested Next Steps).

Write the report to stdout (and optionally to `docs/product/validation-report-<ts>.md` if the PO asks).

### Step 4 — Strict-Gate Behavior

- Without `--strict`: report all findings, do nothing else (advisory).
- With `--strict`: if **any** finding has `severity: error`, stop. Print: "Strict mode blocked on errors above. Resolve and re-run."
- `severity: warn` never blocks.

## Contradiction Protocol (critical — never auto-flip)

→ `validation-rules-spec.md` § Contradiction Protocol (single authoritative home for the keep/change/hybrid steps).

This protocol runs on a `contradiction` finding against an `approved` artifact before the report is composed, and applies even if `--strict` is OFF.

### Decision Register wiring (kill re-litigation)

See [Decision Register Wiring](workflow-validate-decision-register.md).

## Drift Detection (frontmatter ↔ prose)

When generating reports or summaries:

- If the LLM notices a heading-text in the body that conflicts with a frontmatter value (e.g., body says "MUST" but frontmatter says `moscow: should`), emit an advisory note. **Frontmatter wins by rule** (`CLAUDE.md → Frontmatter is source-of-truth`).
- Never auto-overwrite frontmatter from prose, and vice versa.

## `--approve` Flow

**NOT SHIPPED in this build.** `--approve` is not a flag `hs:spec` exposes — see the caveat at
the top of this file. The steps below are a design reference only.

1. Run `--validate` (without `--strict`). Collect findings.
2. If errors exist → tell the PO: "Open issues: {n_errors}. Approval will record these as outstanding. Continue?" Warn-not-block per brainstorm decisions.
3. If contradictions exist → run the contradiction protocol first; abort approval until resolved.
4. Ask: "Approve which artifact? (default: the most recently edited)"
4b. **Open-questions gate.** Run `open_questions.py --root <dir>` (or `scan_file` on the chosen artifact).
    If the artifact still carries an unresolved marker (`cần PO xác định` / `TBD` / `Vẫn còn mở`) — anywhere in it: an acceptance-criterion, a body line, or a note — surface it verbatim and ask: "This artifact carries an unresolved open question ({marker}, line {n}) — resolve it now, approve as-is (recorded outstanding), or cancel?"
    Warn-not-block: an artifact with a hanging parameter is approvable only with the PO's eyes open, never silently.
5. Ask: "Who is approving (owner)? Stakeholders to record?"
6. Update the artifact:
   - Frontmatter: set `status: approved`, add `approval: {approved_by, approved_at, approved_version}`, bump `version` minor.
   - Body: append the `sign-off.md` fragment with the answers.

## `--summary` Flow

**NOT SHIPPED in this build.** `--summary` is not a flag `hs:spec` exposes — see the caveat at
the top of this file. The steps below are a design reference only; `generate_templates.py --type
exec_summary` itself is real, but nothing in this build calls it as part of a `--summary` flow.

1. Run `spec_graph.py` (no snapshot needed unless the PO asks).
2. Compose the exec-summary inputs:
   - Product name + core-value (from PRODUCT.md).
   - BRD goals (titles + status).
   - PRDs (id + title + horizon).
   - Roadmap groupings (now/next/later via the `roadmap` view).
   - Persona list.
   - Top 3 risks (highest impact × likelihood).
3. Call `generate_templates.py --type exec_summary --values <json> --write` to render `docs/product/exec-summary.md`.
4. Optionally render an HTML version: `visualize.py --view tree --format html --root <root>` and bundle.

### `--audience` modifier

`--summary` takes an optional `--audience` flavor (NO new top-level flag — DRY over this same value-assembly path; `generate_templates.render()` is token-substitution, so reuse the value path that BUILDS the token values, then render):

- **`--audience exec`** (default) — exactly the flow above. Byte-for-byte the current exec one-pager.
- **`--audience release-notes`** — designed to build "what changed since the last approved
  snapshot" from a governance audit trail, but its assembler (`assemble_audit_trail.py`) is **not
  shipped in this build** — the same absent script behind the retired `--viz audit` view. Of the
  two designed audiences, only the `exec` one-pager has a real assembler; neither ships as a flag here.

## `--decision` Flow

`--decision` is the PO's manual entry point into the per-workspace DEC ledger — the same
`docs/product/decisions.md` the Contradiction Protocol writes to (above), allocated by
`scripts/dec_ledger.py` (never `decision_register.py` — that is the harness's own,
schema-incompatible tool for its architecture register; see `references/dec-ledger.md`). Use it
to log a standalone ruling that did not arise from a contradiction (e.g. "we will NOT support
multi-currency in v1"), so the choice is recorded once and never re-debated.

- **`--decision list`** → show the ledger's blocks (id, status, date):

  ```bash
  python3 scripts/dec_ledger.py --root <root> --list
  ```

- **`--decision`** (no arg) → record a new ruling. Ask the PO (via AskUserQuestion) for the ruling
  and the why, then allocate + append in one call (the script owns the `^DEC-\d+$` grammar, the
  monotonic id allocation, and the append-only write through the soft fence + flock; the LLM
  supplies the title + rationale prose):

  ```bash
  python3 scripts/dec_ledger.py --root <root> --add \
    --status active --affects "<artifact-id>[,<artifact-id>...]" \
    --title "<short ruling>" --body "<why>"
  ```

The ledger is append-only with no supersede mechanism today — `dec_ledger.py` has no
`--supersedes` flag and never flips a prior block's `status`. To revisit an earlier ruling, record
a fresh `DEC-<n>` whose body prose says which prior id it replaces; do not describe a
`decision_register.py`-style superseding write here. Same DRY guard: the record links to artifacts
by ID (`affects:`), it never copies their structural facts. Full mechanism + the two-ledger split:
`references/dec-ledger.md`.

## Cross-Flag Notes

- The LLM **must run scripts first**; it must not infer the graph by reading files directly.
- All script invocations run via `python3 scripts/<name>.py` from the skill's `scripts/` directory (skill-local, no repo venv).
- There is no mandatory change-log write on any flag in this build — `change_log_writer.py` was
  designed but never shipped. Do not promise the PO a `docs/product/change-log`-style close-out
  step; none of these flows persist one today.
- There is no `--status` / spec-health command in this build — the read-only health nudge
  (`status.py` / `status_vcs.py`, last-validated errors/warns + drift reminder + open-questions
  digest) was **NOT SHIPPED**. `--validate` re-derives the same underlying findings on demand; use
  it instead. Do not advertise a standing spec-health dashboard.
