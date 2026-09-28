# Template Re-Audit Log

Provenance + audit trail for the `templates/python/` set. The source pack ships
no license, so every template was **re-implemented, not code-copied**: read for
intent, re-authored clean, brands stripped, bugs fixed. This log makes the audit
inspectable — each row names the rules it satisfies, its source-line provenance,
and the concrete change made. The executable half lives in
`"${HARNESS_BIN_ROOT:-.}"/harness/tests/test_eval_bootstrap_templates.py` (13 invariants).

## Rule legend

- **R1** — eval mock imports nothing from `src/`, needs no env vars / API keys.
- **R2** — the scorer/comparison layer is pure (no LLM, network, randomness); grade per-field one-at-a-time. The batch LLM judge is a NAMED exception, optional and advisory (VL-2).
- **R3** — the P0 hard-gate is a real, domain-filled gate (not vacuously empty).
- **R4** — normalization collapses diacritic + whitespace variants before comparison.
- **R5** — PII (email local-part, phone middle digits) is masked in output.
- **R6** — reports/setup docs are human-readable and domain-labelled.
- **R8** — the LLM judge runs a DIFFERENT model than the pipeline (self-eval-bias guard), enforced by a runtime assert.

## Substitution contract

- `.py` / `.json` templates use `string.Template` `${...}` tokens for the mechanical scaffold vars (`domain`, `threshold`, cross-module import names, `judge_model`, `pipeline_model`, `p0_rules`, `ext`). The scaffolder fills every one with `.substitute` (raise-on-missing → zero unrendered tokens).
- Model-authored fills (DIMENSIONS, per-dimension logic, P0 rule bodies, `SAMPLE_RESULTS`/`EXPECTED_*`) are **in-code stubs** (`raise NotImplementedError`, empty dict + example comments, `# TODO`), NOT `${...}` tokens — they survive scaffold as valid Python and the model fills them per the interview.
- `.md` / `.yml` templates keep single-brace `{...}` markers (runtime + model fills, e.g. `{date}`, `{dependency_install_command}`) and shell `$?` — they are **copied verbatim** by the scaffolder (never run through `string.Template`, whose parser would choke on `$?`).

## Cross-cutting fix (source finding #1 — brace collision)

The source substituted bare `{name}` tokens, which collide with Python's own
`{...}` (f-strings, set/dict literals, `.format`). Concretely it crashed at
`runner.py:229` / `judge_prompt.py:208` (`.format` over an unescaped JSON schema
→ KeyError) / `judge_runner.py:202`. Fixed globally by moving outer substitution
to `string.Template` `${...}` and eliminating every runtime `.format`/brace path:
the domain is baked in at scaffold time and report strings use `%`-formatting or
plain literals. Invariant #1 (AST-valid-after-substitution) pins this.

## Per-template audit

| # | Template | Rules | Verdict |
|---|----------|-------|---------|
| 1 | `scorer.py.tmpl` | R2, R3 | re-audit |
| 2 | `extractor.py.tmpl` | R1 | re-audit |
| 3 | `runner.py.tmpl` | R1, R2, R4, R5 | fixed |
| 4 | `comparison.py.tmpl` | R4 | fixed |
| 5 | `thresholds.py.tmpl` | R3 | fixed |
| 6 | `ground_truth.json.tmpl` | R4 | safe |
| 7 | `test_scorer.py.tmpl` | R2, R3 | fixed |
| 8 | `judge_prompt.py.tmpl` | R2 (batch), R8 | rewrite |
| 9 | `judge_runner.py.tmpl` | R2 (batch), R8 | rewrite |
| 10 | `judge_rubric.md.tmpl` | R2, R3 | safe |
| 11 | `quality_report.md.tmpl` | R6 | fixed (VL-2) |
| 12 | `production-eval-setup.md.tmpl` | R6 | fixed |
| 13 | `github-actions.yml.tmpl` | R1, R6 | safe |
| 14 | `extract_data_text.py.tmpl` | R1 | **new** |
| 15 | `run_production_evals.py.tmpl` | R1, R2 | **new** |
| 16 | `config_integrity.py.tmpl` | R7 | **new (wave-2)** |
| 17 | `pipeline_mirror.py.tmpl` | R1 | **new (wave-2, renamed from row 2 `extractor`)** |
| 18 | `test_mirror_parity.py.tmpl` | R2 | **new (wave-2)** |
| 19 | `test_config_conformance.py.tmpl` | R2, R3 | **new (wave-2)** |
| 20 | `gitlab-ci.yml.tmpl` | R1, R6 | **new (wave-2, `--forge`)** |
| 21 | `mirror-implementation-guide.md.tmpl` | R1, R6 | **new (wave-2)** |
| 22 | `test_mirror_contract.py.tmpl` | R2, R3 | **new (wave-2)** |

(Table reconciled with the on-disk `templates/python/*.tmpl` glob; row 2
`extractor.py.tmpl` is retained as historical provenance — see the rename note
below — and its current form ships as row 17 `pipeline_mirror.py.tmpl`.)

### Provenance + change notes

1. **scorer** — pure Decimal ROUND_HALF_UP kept. `{domain}/{threshold}/{p0_rules}`
   → `${...}`. Annotations bared to `list/dict/tuple` (3.9-proof). `${p0_rules}`
   retained as the non-vacuous P0 marker (invariant #8).
2. **extractor** — eval-mock stub. `{domain}/{production_module}` → `${...}`.
   Dropped unused imports; zero `src/` / network imports (invariant #5).
3. **runner** — added the missing `import re` (source used `re.sub` with no import
   → NameError). Fixed the `{ {domain} }` brace bug via a `DOMAIN` module constant
   + `%`-formatting. Removed the duplicate `main()`/argparse — the CLI now lives
   only in `run_production_evals.py`; runner is a library. Cross-module imports →
   `${extractor_module}` / `${scorer_module}` (lazy, function-level).
4. **comparison** — stripped the `ehiring-ai` brand at 3 sites (:9, :26, :230).
   `${domain}` in the header. `from __future__ import annotations` keeps
   `set[str]` / `Optional` lazy → 3.9-safe.
5. **thresholds** — stripped the `ehiring-ai` brand (:6). `${domain}`. f-strings →
   `%`-formatting; `from __future__` for lazy annotations.
6. **ground_truth** — `{domain}/{ext}` → `${...}`. Agnostic JSON, unchanged shape.
7. **test_scorer** — stripped the `KB Guard` brand (:15). `${scorer_module}` for the
   import; `SAMPLE_RESULTS` / `EXPECTED_MATURITY` / `EXPECTED_PASSED` converted from
   `{...}` template vars to in-code fill markers (model pins them once the scorer
   exists).
8. **judge_prompt** — removed the `.format()` over `SYSTEM_PROMPT` (its literal JSON
   schema braces caused a KeyError crash every call). Domain is baked into
   `SYSTEM_PROMPT` via `${domain}`; the user prompt uses `%`-formatting. Advisory
   framing added.
9. **judge_runner** — VL-2 core: removed `combined_multiplier` / `final_maturity` and
   `merged_passed`. The source multiplied the LLM score into maturity (:162) and
   flipped `passed` on judge P0 (:166-180), putting the LLM in the scoring path.
   Replaced with `attach_judge_advisory`, which returns the deterministic score
   verbatim plus a `judge_advisory` block (`p0_recommendation` is advisory, never a
   gate). Added the R8 runtime assert (`DEFAULT_JUDGE_MODEL != PIPELINE_MODEL`).
   Removed the stale hard-coded model-id map (`_model_name_for`). `from __future__`
   fixes the PEP604 bare-union (:217). Cross-module imports → `${...}`.
10. **judge_rubric** — agnostic scoring rubric, near-verbatim + an advisory-only note.
11. **quality_report** — VL-2: removed the "Quality multiplier" / "Merged final score"
    rows that implied the judge overrode the verdict. The report now separates the
    authoritative deterministic verdict from the judge advisory score.
12. **production-eval-setup** — stripped `frankode-evals-bootstrapper` (:342). Added
    the image → model-read (no OCR) instruction and `extract_data_text.py --data-dir`
    usage; noted `--judge` is advisory.
13. **github-actions** — CI workflow, near-verbatim; no brands.
14. **extract_data_text** — new (source had prose only, no template — agent-def :297).
    pymupdf + python-docx via lazy import; no OCR — images are surfaced for a manual
    model-read + hand-committed `.txt` (invariant #4).
15. **run_production_evals** — new (source cited an entrypoint at agent-def :210 but
    shipped no template; VL-4). CLI that puts the domain's eval dir on `sys.path`,
    runs the deterministic eval, and exits 0/1 on the deterministic verdict. `--judge`
    runs the advisory pass and never changes the exit code (VL-2).

## Rename audit (extractor -> pipeline_mirror)

`extractor.py.tmpl` -> `pipeline_mirror.py.tmpl` (`git mv`, history preserved);
entry function `extract` -> `run_pipeline(input_data) -> dict`; scaffold
context key `extractor_module` -> `mirror_module`; vocabulary swept across
every template + `eval_scaffold.py` (runner/judge_runner/judge_prompt/
judge_rubric/production-eval-setup/protocol/strategy-classification), guarded
mechanically by `test_no_extractor_vocabulary_left`. Row 2 above
("extractor — eval-mock stub...") documents the ORIGINAL re-implementation
audit and is left unchanged as historical provenance, not current state.

## Brands stripped (grep-clean, invariant #3)

`ehiring-ai` (comparison, thresholds), `KB Guard` (test_scorer), `frankode` /
`frankode-evals-bootstrapper` (production-eval-setup). No `frankode|frankcode|
ehiring-ai|kb guard|plan-2333|auditcore` remains anywhere under `templates/python/`.

## OCR (invariant #4)

Zero `pytesseract` / `PIL` in the set. Image text is obtained by a model read at
bootstrap time and committed as a `.txt` sidecar by hand, keeping the eval runner
deterministic and API-key-free.
