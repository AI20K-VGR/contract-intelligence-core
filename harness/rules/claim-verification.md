# Claim verification (on-demand)

Load when writing or reading a **universal / absence / structural claim** — "every
endpoint requires auth", "no PII in logs", "every exported function has a test" — a
shape a behavioral test cannot express (a test proves one input/output pair, not a
property over every match). The engine is `harness/scripts/claim_verify.py`; the rule
spec SSOT is `harness/data/claim-rules.yaml`.

## Contract

1. **Enumerate** — every match of a rule's `match` regex within its declared `scope`
   (full scan, never sampling).
2. **Assert** — the rule's `assert` condition against the window around every match.
3. **Report** — PASS or FAIL per match with `file:line` evidence.
4. **Verdict** — `block` if any FAIL has `severity: block`; `advisory` if the only
   FAILs are `severity: advisory`; `pass` otherwise. A rule with **zero matches is
   SKIPPED, never vacuously PASSED** — an empty scope must not manufacture a
   false-positive pass.

Full semantics: `docs/product/_refs/frankcode-src/qa/methodology/qa/rule-based-verification.md:44-48`.

## Writing a rule

Add an entry to `harness/data/claim-rules.yaml` — never edit `claim_verify.py` to
special-case a claim. Required fields: `id`, `text`, `scope`
(`codebase|module|fileset`), `match`, `assert`, `severity` (`block|advisory`).
`scope: fileset` also requires `path` (a glob pattern). `context` (int, default 0)
widens the assert window to catch a condition a few lines away from the match (e.g.
an auth decorator stacked above a route decorator). See the field table and seed
rules in `claim-rules.yaml` itself for the authoritative reference.

Keep `match` narrow and `assert` conservative — a loose regex produces false
positives/negatives on both sides; the mitigation is advisory-first locally, not a
cleverer regex.

## Running + reading a verdict

```bash
python3 harness/scripts/claim_verify.py --rules harness/data/claim-rules.yaml --scope-root .
```

Exit 0 on `pass`/`advisory`, exit 1 on `block` — advisory-first at the local level:
this is a read-only reporter (stdout + exit code only, mirrors `plan_graph.py`'s
detection-only stance), it never writes a store and never mutates scanned code. There
is **no hard local gate wired to it** in this phase; a `block` verdict is a strong
signal to act on, not an enforced stop.

## Boundary with `rule_view.py` / `standards.yaml`

The existing rule layer (`harness/scripts/rule_view.py` + `harness/standards/*.std.yaml`,
read by `hs:code-review`) is **scoped code-standards** review — style/architecture
conventions checked during review. `claim-verify` is a **different, wider** tool: an
arbitrary universal/absence/structural claim about the codebase, run standalone or
alongside review, not through the review-rule pipeline. Neither file replaces the
other — do not merge them, and do not route claim rules through `rule_view.py`.

## Anti-tautology

The engine imports `pathlib` / `argparse` / `sys` (stdlib), `regex` (third-party, for
variable-width lookbehind) and the repo's `yaml_io` wrapper over `ruamel.yaml` —
**never the application code it verifies**. No AI reasoning happens at check time:
same codebase + same rules -> same verdict, every run. This is the same invariant
`anti-tautology-detection.md` checks mechanically for a checker's import graph — a
claim rule that imported its target would be exactly the self-consistent-but-wrong
failure mode both guard against.

## Out of scope (YAGNI, defer)

Full semgrep/dataflow analysis and cross-file symbol resolution are deliberately not
built here — v1 is regex + glob (+ a simple AST-node match, not yet exercised by a
seed rule). Add that only when a concrete claim needs it, not speculatively.
