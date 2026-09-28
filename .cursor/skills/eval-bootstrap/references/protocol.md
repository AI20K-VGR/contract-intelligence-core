# Protocol — the 6-phase bootstrap

Full walk-through for `hs:eval-bootstrap`. Skill body = index; this = detail. Phases 1, 2, 3.5, 5 are yours (judgment); Phase 3 is the only
mechanical step (the scaffolder).

## Phase 1 — Analyse the repo

1. **Detect the stack** — route to `hs:techstack`, then route per the support
   matrix (`SKILL.md` `## Support matrix`): Python → the **native lane** (mirror
   the `.py` module, direct parity import). Any other language with an available
   interpreter → the **subprocess lane** (mirror the target language, a contract
   JSON over stdout, `--mirror-lang`). No usable interpreter, or the target can't
   emit JSON on stdout → refuse clearly with guidance and STOP; do NOT force-fit
   and do NOT call the scaffolder.
2. **Find the pipeline** — locate the production entrypoint and its
   **output surface**: structured fields (extraction), a free-text answer
   (generation), a score/label (classification), a ranked list (retrieval). The
   output surface drives what Phase 2 proposes.
3. **Scope the eval target** — one domain per run (e.g. `cv_extraction`). Note the
   production module the pipeline_mirror will mirror.
4. **Multi-module inventory** — if the repo has more than one production module
   worth evaluating (api/worker/job), do NOT auto-pick. Present a table on the
   card: `module → output surface → worth-eval? → reason`. The user picks 1..n
   modules. Each chosen domain runs its own card-to-stamp round under
   `evals/eval_types/<domain>/`; the scripts/ and config-integrity machinery
   are shared across domains. One card never covers two output surfaces —
   one card, one surface.
5. **Recall memory before proposing a strategy** — run recall for this
   domain/surface/stack before writing the card in Phase 2:
   ```bash
   python3 <skill>/scripts/eval_memory.py recall \
       --filter domain=<d>,surface=<surface>,stack=python --limit 10 --target .
   ```
   This is MANDATORY: a proposal that ignores an applicable lesson must say
   why. Any lesson that shapes the card is cited by id in the card's
   `cited_lessons` field — schema, verbs, and rules: `references/eval-memory.md`.

## Phase 2 — Classify the strategy + get approval (R7)

Map the output surface to a strategy (`references/strategy-classification.md`):
`ground-truth`, `judge`, `hybrid`, or `contract`. Write a one-screen **strategy
card** with these fields:

- **Domain**, **output surface**, chosen **strategy** + one line of why.
- **Dimensions + weights** — the 5-set accuracy/robustness/consistency/
  completeness/precision is a pre-filled suggestion only; the user edits it,
  the code carries no default. **primary_dimension** names the one dimension
  the judge's recommendation anchors to.
- **Threshold** and the **P0 hard-gate rules** — each rule carries a `source`
  anchor from one of three kinds: a code site (e.g. `code:src/pipeline.py:88`,
  a validate/raise already in production), a data sample (a field present in
  100% of the samples), or a memory lesson id.
- **Case matrix** — finite, with the standard edge set: empty, null,
  unicode-with-diacritics, malformed, boundary.
- **Epsilon** per continuous axis.
- **DOMAIN_CONFIG** — field-to-normalizer / field-to-mask; an empty map must
  carry a note explaining why it is empty.
- **production_module** — the module chosen in the Phase 1 inventory.
- **mirror_lang** — the target language for the pipeline mirror.
- **cited_lessons** — lesson ids from the Phase 1 recall that shaped this
  card's choices (empty list if recall found nothing applicable).

**R7 gate — mandatory:** present the strategy card via **AskUserQuestion** and
wait. Do not stamp anything until the human approves. This is the human's one
chance to redirect before files land.

**After the user approves, write the card immediately:**

```bash
python3 <skill>/scripts/eval_config.py write --target . --card -
```

From then on every eval turn re-verifies the card hash before scoring. The
code validates deterministically: weights sum to 100, P0 rules are non-empty
and each rule is testable, the case matrix is non-empty. The code never fills
a judgment value — it only validates what the approved card supplies.

## Phase 3 — Generate the tree (the only mechanical step)

Run the scaffolder. Dry-run first:

```bash
python3 scripts/eval_scaffold.py --target . --domain <d> --strategy <s> --forge <github|gitlab> ... --dry-run
python3 scripts/eval_scaffold.py --target . --domain <d> --strategy <s> --forge <github|gitlab> ...
```

It stamps `evals/eval_types/<d>/` (scorer, pipeline_mirror, runner, judge modules),
`tests/`, `scripts/`, `docs/`, and a CI workflow by `${...}` substitution. It
refuses to overwrite without `--force`. After stamping, you fill the in-code
stubs the templates leave: `DIMENSIONS` + weights, `score_dimension`, the P0
gate body in `check_p0_gates`, and the pipeline_mirror `run_pipeline` logic — mirror the
production module without importing `src/`. **Every one of those fills is an
R9 fill (Phase 3.5) before it counts as done** — filling the stub is not the
finish line, the sandbox run + human gate is.

## Phase 3.5 — R9 gate: evidence per fill (L3 lock)

Every code-fill from Phase 3 (pipeline_mirror, `score_dimension`,
`check_p0_gates`, a new normalizer/mask profile) is LLM-generated code, so it
must run for real in a jail and show its work before it lands — L3, never a
"looks right" self-check. Full procedure, the real `sandbox_run.py` command,
the 3-way approval gate, exit-code semantics, the eval-turn rule, and the
resume/card_hash rule all live in `references/sandbox-evidence.md`. Read that
drawer before filling a stub; this section only anchors where the gate sits in
the flow: after a fill is written, before it is treated as part of the tree.

The gate's **Add guidance** choice appends a `standard` record to tier-2
memory (cross-repo, per-machine); an **Approve** decision appends a
**decision record** to tier-1 memory so a later resume recalls it against the
current card hash. Schema, verbs, and the append commands:
`references/eval-memory.md`.

## Phase 3.6 — Data workflow

Discover sample files, generate `.txt` sidecars, and bootstrap ground truth with
the human in the loop. Full steps: `references/data-workflow.md`. Deps (pymupdf,
python-docx) go through the Q4 ask-then-pip gate first.

## Phase 4 — CI

Wire the generated workflow (`evals/ci/production-evals.yml`) into
`.github/workflows/` so unit tests, contract tests, and production evals run on
push/PR. It is API-key-free by construction (the pipeline_mirror + deterministic
scorer need no secrets).

Then **prove the wiring** — the scaffold only STAMPS the file into `evals/ci/`;
a file there never runs on its own:

```bash
python3 <skill>/scripts/ci_wiring_check.py --target . --config evals/eval_config.json
```

It reads the card's `forge` and reports `WIRED` / `NOT_WIRED` / `INDETERMINATE`
(advisory, exit 0; `--strict` exits 1 on anything but WIRED). **WIRED means the
file is PLACED where the forge runs it (github: under `.github/workflows/`;
gitlab: `include:`-d from the root `.gitlab-ci.yml`) — NOT that CI has run.** A
github workflow with `on: workflow_dispatch` only is WIRED-but-caveated: placed
right, but it will not trigger on push/PR. An `INDETERMINATE` verdict is LOUD by
design — never treat it as a pass.

## Phase 5 — Verify (block-then-pass)

1. Dry-run the eval on the sidecar fixtures: a clean run exits 0.
2. **Run the mutation matrix** — generate it from the approved (hashed) card,
   then run it against the stamped tree:
   ```bash
   python3 <skill>/scripts/mutation_matrix.py generate --config evals/eval_config.json \
       --out evals/_mutation/matrix.json
   python3 <skill>/scripts/mutation_matrix.py run --config evals/eval_config.json \
       --matrix evals/_mutation/matrix.json --evals-root evals \
       --sample-dir data/samples \
       --ground-truth evals/eval_types/<d>/tests/production_fixtures/ground_truth.json
   ```
   Every P0 rule must be killed, every threshold/epsilon boundary must flip
   exactly at the edge, and noise must stay green. A red layer means the
   gate is not actually gating — fix before declaring done. This replaces a
   single hand-mutated field: one field proves nothing about the OTHER rules.
   **The card MUST also carry a code layer — ≥1 code-mutation on
   `pipeline_mirror` and ≥1 on `check_p0_gates`** (a human-approved patch point
   that breaks the SOURCE and runs the real eval): only this proves the eval
   catches broken CODE, not just a wrong answer key. For a python mirror,
   `generate` REFUSES (exit 4) a card missing either — that refusal is the
   condition for calling the eval mutation-proven. (A subprocess-lane / non-python
   stack gets a NOTE instead; the code vehicle is native-python for now.)
3. Run `hs:test` on the generated contract tests.
4. If a judge strategy was chosen, confirm the judge is advisory: the exit code
   must not change when the judge runs (`--judge`) vs when it is skipped.
5. **Recall the R9 exit-code contract** (`references/sandbox-evidence.md` §4)
   when verifying any fill that went through the sandbox: only exit 0 was ever
   presented for approval, so a fill now in the tree should have no exit
   1/2/3/4 evidence sitting unresolved in `evals/_sandbox_evidence/`.
6. **Re-run `ci_wiring_check.py`** and read the verdict into the handoff: do NOT
   claim "CI wired" when it reports `NOT_WIRED` or `INDETERMINATE`. State the
   verdict verbatim and, for a `WIRED`-but-`workflow_dispatch` caveat, say
   plainly that the file is placed but will not run on push/PR until the trigger
   is added.
## Phase 6 — R10 post-audit (audit the eval you just built)

Runs AFTER Verify, BEFORE append-lesson. Its target is the NEW eval itself — the
"graded itself with an answer key copied from its own code" failure the mutation
matrix alone never catches. Full drawer: `references/r10-postaudit.md`.

1. **R10a — deterministic (machine, no LLM):** confluence of the three
   mechanical checks. Run each and read its verdict:
   ```bash
   python3 <skill>/scripts/mutation_matrix.py generate --config evals/eval_config.json --out evals/_mutation/matrix.json   # code-sensitive
   python3 <skill>/scripts/ci_wiring_check.py --target . --config evals/eval_config.json
   python3 <skill>/scripts/gt_notes_lint.py --ground-truth evals/eval_types/<d>/tests/production_fixtures/ground_truth.json
   ```
2. **R10b — sealed-room (advisory, judgment):** spawn the
   `hs:independent-revalidator` agent (via `subagent_type:
   "hs:independent-revalidator"` — confirm it actually spawns; a silent fallback
   to `claude` is NOT independent) to re-derive the case-matrix expectations from
   the SPEC alone and diff vs ground truth. Three locks hold (verbatim in the
   drawer): a human MUST approve any derived-spec; the subagent's read is
   audited by a falsifiable **read-trail** (rejected if it read
   ground_truth/mirror/production/scorer) — `containment: prompt-only
   best-effort`, not a hard seal; and every result is labelled
   `confidence: HIGH | LOW`. Advisory only — R10b never gates the eval's exit
   code.
3. **Append a lesson** — once R10 is green, append what made this eval differ
   from expectation (or confirm nothing did) to tier-1 memory:
   ```bash
   python3 <skill>/scripts/eval_memory.py append --type lesson --domain <d> \
       --surface <surface> --stack python --target . --auto-hash \
       --body "<what surprised us>"
   ```
   Full schema + rules: `references/eval-memory.md`.
