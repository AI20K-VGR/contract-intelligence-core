---
name: hs:eval-bootstrap
injectable: false
description: Bootstrap a full evals/ framework for THIS repo — deterministic scorer + ground truth + optional advisory LLM judge + CI, API-key-free. Two human gates — R7 (strategy card) + R9 (sandboxed evidence per fill). Use when the user says "set up evals for this repo", "bootstrap production tests", or "build an eval harness".
argument-hint: "[--strategy] [--domain] [--stack] [--skip-judge]"
allowed-tools: [Bash, Read, Grep, Glob, Edit, Write, AskUserQuestion, Task]
metadata:
  compliance-tier: workflow
---

# hs:eval-bootstrap — stand up an eval framework for a target repo

Invoke **inside the repo you want evals for**. Runs a 6-phase interview
that ends with a working `evals/` tree: a deterministic scorer, ground-truth
fixtures, an optional **advisory** LLM judge, and CI — runnable with **zero API
keys**. `hs:test` runs tests that already exist; this skill *builds* the eval
harness that did not exist yet.

**Seam (do not blur):** every judgment value — strategy, dimensions/weights,
threshold, P0 rules, case matrix, `DOMAIN_CONFIG`, `production_module` — is
proposed by you and gated on the human via **AskUserQuestion**; the code never
supplies a default. Once approved it is validated deterministically (weights
sum to 100, tokens are safe, rules are testable) and never re-derived.

| Field | Who proposes | Gate |
|---|---|---|
| domain, strategy, dims+weights, threshold, p0_rules | you | R7 card |
| case matrix + epsilon, `DOMAIN_CONFIG`, `production_module`, mirror_lang | you | R7 card |
| pipeline_mirror / `score_dimension` / `check_p0_gates` / a new normalizer-mask | you (code) | R9 sandbox evidence |
| render/stamp/hash/validate/canonical-JSON | code | — (deterministic) |
| normalize/mask at eval run time (per approved `DOMAIN_CONFIG`) | code | — (deterministic) |
| memory append/recall I/O | code | — (deterministic) |
| applying a recalled lesson to a new proposal (cite its id) | you | R7 card |

The code validates, it never fills a judgment.

## Role split

| Script | Role |
|---|---|
| `scripts/eval_scaffold.py` | Stamp the `evals/` tree by `${...}` substitution. Mechanical. |
| `scripts/eval_config.py` | Persist the approved card as canonical JSON + sha256; `verify`/`show`/`hash` re-derive it. Mechanical. |
| `scripts/sandbox_run.py` (+ `sandbox_denylist.py`) | Run one code-fill inside the layered R9 jail against the case matrix + edge set, emit an evidence artifact. Mechanical execution — the human still approves. |
| `scripts/eval_memory.py` | Append/recall the two-tier lesson/incident/decision/standard store. Mechanical I/O. |
| `scripts/mutation_matrix.py` | Generate + run the 3-layer mutation matrix from the hashed card — meta-tests the P0 gate. Mechanical. |
| **AskUserQuestion** | The two human gates: R7 (strategy card) and R9 (per-fill sandbox evidence), plus the Q4 pre-pip consent. |

## The 6 phases (detail: `references/protocol.md`)

1. **Analyse** — detect the stack (route to `hs:techstack`), find the pipeline entrypoint + its output surface, list candidate eval targets. **Recall memory first** (`eval_memory.py recall`) — an applicable lesson must shape the card or you say why it does not.
   **Stack route** (see `## Support matrix`): Python → the native lane; any other language with an available interpreter → the subprocess lane (mirror the target language, contract JSON over stdout, `--mirror-lang`); no usable interpreter or no JSON-stdout → refuse clearly with guidance, do NOT force-fit.
   **Pipeline-fit check (before promising a mirror):** the mirror lanes need a **deterministic, stdlib-reproducible core**. If the core is a **non-deterministic LLM/vision/network call**, no faithful `pipeline_mirror` exists — don't force-fit one. Score the pipeline's **recorded outputs** against golden fixtures with the deterministic scorer instead, and say so on the card.
2. **Strategy** — classify the output surface (`references/strategy-classification.md`) and write a one-screen strategy card.
   - **R7 gate:** present the card via **AskUserQuestion**, wait for approval, then persist it: `python3 scripts/eval_config.py write --target . --card -`.
3. **Generate** — run `scripts/eval_scaffold.py` (dry-run first). The only mechanical stamping step; it leaves fill-me stubs.
   - **R9 gate:** each stub fill (pipeline_mirror, `score_dimension`, `check_p0_gates`, a new normalizer/mask) runs for real in `sandbox_run.py`'s jail before it counts as done — approve, add guidance, or reject. Detail: `references/sandbox-evidence.md`.
3.5. **Data workflow** — sample discovery + ground truth, human in the loop. See `references/data-workflow.md`.
4. **CI** — wire the generated workflow so evals run on push/PR (API-key-free), then run `scripts/ci_wiring_check.py` to prove it is PLACED where the forge runs it (advisory; do not claim "CI wired" on `NOT_WIRED`/`INDETERMINATE`).
5. **Verify** — block-then-pass dry-run, then run the mutation matrix (not a hand mutation) to prove every P0 rule and threshold is actually gating. Detail: `references/protocol.md` Phase 5, `references/eval-memory.md`.
6. **Post-audit (Phase 6 — R10)** — **R10a** (machine): mutation matrix + `ci_wiring_check.py` + `gt_notes_lint.py`. **R10b** (advisory, never a gate): a **sealed-room** re-derivation by the `hs:independent-revalidator` agent — re-derive expectations from the SPEC alone, diff vs ground truth to catch a copied-from-output key. Detail: `references/r10-postaudit.md`.

## R1–R9 rules the generated framework must honour

| Rule | Requirement |
|---|---|
| R1 | The pipeline_mirror imports nothing from `src/`; needs no env vars / API keys. |
| R2 | The scorer/comparison layer is pure (no LLM, network, randomness); grade per-field. The batch LLM judge is a NAMED exception — optional, advisory, never the sole gate. |
| R3 | The P0 gate is **mutation-proven**: a card-built matrix kills every P0 rule + threshold/epsilon boundary **AND breaks the CODE — ≥1 code-mutation on `pipeline_mirror` + ≥1 on `check_p0_gates`** (human-approved patch, run against the real eval). A python card missing either, or an unkillable rule, refuses at `generate`; non-python gets a NOTE. |
| R4 | Normalisation is **config-driven**: the domain config MUST declare its `normalizers` map (an empty map is a documented decision, not an absent key). |
| R5 | PII masking is **config-driven** the same way: the domain config MUST declare its `masks` map; an empty map is a documented decision. |
| R6 | Reports are human-readable and domain-labelled. |
| R7 | The strategy is **approved by a human** (AskUserQuestion) before scaffolding, then persisted to a hashed `eval_config.json`. |
| R8 | The LLM judge runs a **different model** than the pipeline (self-eval-bias guard, enforced by a runtime assert). |
| R9 | Every LLM-generated code-fill runs for real in the `sandbox_run.py` jail and a human reads the evidence before it lands — no override, no "approve with known failures". |

## Support matrix (replaces the old Python-only fence)

| Stack | Lane | Guarded by |
|---|---|---|
| Python | native: mirror the `.py` module + direct parity import | parity + conformance + mutation |
| Any language with an available interpreter | subprocess: mirror the target language + a contract JSON over stdout | contract tests (denylist/determinism/fence) + mutation + R9 |
| No usable interpreter / can't emit JSON on stdout | refuse clearly + guidance — no force-fit | — |

### Containment by OS (R9 sandbox)

| OS at R9 bootstrap | Containment level | Evidence label |
|---|---|---|
| Linux + bwrap | OS-contained (namespace: filesystem + network) | `containment: bwrap` |
| Linux without bwrap / macOS | best-effort pre-filter (denylist + env-scrub + socket-patch + timeout), NOT an OS jail | `containment: python-filter-fallback` |
| Windows | best-effort pre-filter + kill-tree via taskkill (complete), NOT bwrap | `containment: python-filter-fallback` |

**Mandatory disclosure:** R9 runs fill code in an OS jail ONLY on Linux with bwrap;
macOS/Windows/Linux-without-bwrap is a best-effort pre-filter (NOT an OS jail) — the
fill is unvetted LLM code and the final gate is the human reading the evidence.

**Residual risk:** the mechanical layers (denylist, contract tests, mutation matrix,
R9) can still miss a subtle network-but-deterministic mirror or an out-of-band forge
by a hostile fill. Accepted because the threat model is Claude-generated fill code,
not an adversarial target repo — the human reading the evidence is the final gate.

## Dependencies in the target repo (Q4 — ask, then pip)

The generated framework needs no API keys, but PDF/DOCX sidecar extraction needs
`pymupdf` + `python-docx`. Handle deps in two steps, never silently:

1. **Declare** them in `evals/requirements.txt`.
2. **Ask before installing:** use **AskUserQuestion** to get consent BEFORE any
   `pip install` into the target repo. Only pip when the user says yes. If they
   decline, leave `requirements.txt` as the record and note the manual step.

## The judge is advisory, never a gate (VL-2)

If the strategy includes a judge, it produces a REPORT — patterns, dimension
scores, recommendations. It **never** multiplies into the maturity score and
**never** flips the deterministic pass/fail verdict. `--skip-judge` bypasses it
entirely (default for CI). Design detail: `references/llm-judge-design.md`.

## Handoff note — stamped `test_scorer.py` is RED on arrival

`DIMENSIONS`/`THRESHOLD` are read from the approved card immediately, so the
generated `test_scorer.py` runs against a real card from the start — but
`score_dimension`/`check_p0_gates` are still fill-me stubs (`score_dimension`
raises `NotImplementedError`). Every pinned test from `test_score_returns_
expected_structure` down FAILS until you fill those stubs. That failure is the
intended day-0 signal to do the fill, not a broken template.

## Boundaries

- **Only write under `evals/`** (+ the CI workflow). Never touch the target's production code, `src/`, or its tests.
- **Memory lane — exactly two destinations, no others:** `evals/_memory/*.jsonl` (tier-1, tracked in the target repo) and the per-machine harness state dir (tier-2, cross-repo). Both go through `eval_memory.py`, never the scaffolder.
- **Sandbox evidence dir (the R9 gate):** `evals/_sandbox_evidence/` — a self-explaining name that travels to the client repo; tracked by default so the team sees the proof a generated fill actually ran and passed.
- **Self-target fence:** REFUSE to scaffold if `--target` contains `orchestrator/critic/score.py` or a `harness/` tree — this skill builds evals for OTHER repos, not for the harness/orchestrator that hosts it. Say so and stop.
- **Images are model-read, never machine-OCR** — no OCR library. Extract image text with a model at bootstrap, review it, commit the `.txt` sidecar.
- **Stack route follows the support matrix** (`## Support matrix`) — refuse only when no interpreter is available or the fill cannot emit JSON on stdout; never force-fit.
- The scaffolder refuses to overwrite an existing `evals/` tree without `--force`; prefer `--dry-run` before stamping.

## Backing

- Phase 3 generation → `scripts/eval_scaffold.py` (deterministic `${...}` engine).
- R9 evidence protocol → `references/sandbox-evidence.md`. Two-tier memory → `references/eval-memory.md`.
- Template provenance + the executable re-audit → `references/template-audit-log.md`.

## Quick reference

```bash
# 1. Recall memory before proposing a strategy (Phase 1)
python3 scripts/eval_memory.py recall --filter domain=cv_extraction,surface=extraction --limit 10 --target .

# 2. After R7 approval, persist the card, then verify/show/hash it
python3 scripts/eval_config.py write --target . --card -
python3 scripts/eval_config.py verify --target .
python3 scripts/eval_config.py hash --target .

# 3. Dry-run then stamp (every judgment value is a required arg, no defaults)
python3 scripts/eval_scaffold.py --target . --domain cv_extraction --strategy ground-truth \
    --forge github --threshold 70 --production-module src/cv_extraction.py --mirror-lang python \
    --p0-rules "name must be non-null" --dimensions '{"accuracy": 100}' \
    --primary-dimension accuracy --domain-config '{"normalizers": {}, "masks": {}}' --dry-run
python3 scripts/eval_scaffold.py --target . --domain cv_extraction --strategy ground-truth \
    --forge github --threshold 70 --production-module src/cv_extraction.py --mirror-lang python \
    --p0-rules "name must be non-null" --dimensions '{"accuracy": 100}' \
    --primary-dimension accuracy --domain-config '{"normalizers": {}, "masks": {}}'

# 3.5 R9 gate: run a fill for real, then present the evidence for approval
python3 scripts/sandbox_run.py --fill pipeline_mirror.py --entry run_pipeline \
    --config evals/eval_config.json --case-timeout 10 --evidence-out evals/_sandbox_evidence/mirror.json

# generate PDF/DOCX sidecars (after pip consent)
python3 evals/scripts/extract_data_text.py --data-dir data/samples

# 5. Verify: block-then-pass, then the mutation matrix (never a hand mutation)
python3 evals/scripts/run_production_evals.py --sample-dir data/samples \
    --ground-truth evals/eval_types/cv_extraction/tests/production_fixtures/ground_truth.json
python3 scripts/mutation_matrix.py generate --config evals/eval_config.json --out evals/_mutation/matrix.json
python3 scripts/mutation_matrix.py run --config evals/eval_config.json --matrix evals/_mutation/matrix.json \
    --evals-root evals --sample-dir data/samples \
    --ground-truth evals/eval_types/cv_extraction/tests/production_fixtures/ground_truth.json

# append the lesson once verify is green
python3 scripts/eval_memory.py append --type lesson --domain cv_extraction --surface extraction \
    --stack python --target . --auto-hash --body "<what surprised us>"
```
