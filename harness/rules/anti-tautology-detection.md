# Anti-tautology detection (on-demand)

Load when authoring a NEW verification artifact (a test, a rule, a claim-check
script) or reviewing one someone else wrote. Backs the invariant with a
mechanical check: `harness/scripts/anti_tautology.py`.

## The invariant

A verification artifact MUST NOT `import` the application module it is meant
to verify. A checker that reaches into the code it is supposed to validate can
be self-consistent and still wrong — it is checking the code against itself,
not against an independent source of truth. Anchor:
`docs/product/_refs/frankcode-src/qa/methodology/qa/rule-based-verification.md`
lines 100-108, "Anti-tautology mechanism" → *"No code reuse — Rule engine uses
AST/regex/semgrep. It does not call application code"* + *"Golden assertions"*
(expected values hardcoded, not computed by calling the target).

## Boundary with `testability-triad.md:43`

`harness/rules/testability-triad.md:43` already has a branch named
`anti-tautology` — it is a DIFFERENT failure mode, kept separate on purpose:

| | `testability-triad.md:43` | this rule |
|---|---|---|
| Scans | acceptance-criterion WORDING | a checker file's IMPORT GRAPH |
| Catches | an AC that restates the implementation ("the function returns what the function computes") | a test/rule/claim-check that `import`s the app module it verifies |
| When | writing/reviewing an AC during `hs:plan` | writing/reviewing a checker file (test, rule, claim-check) |
| Mechanism | human/model judgment on prose | deterministic AST scan (`anti_tautology.py`) |

Do not fold one into the other — the triad rule is not touched by this phase.

## When to run

- Adding a new rule-file or claim-check script (e.g. a future
  `harness/scripts/claim_verify.py`-style checker) that is meant to verify an
  app module independently.
- Reviewing a test file where the reviewer suspects it imports the code under
  test to compute its own expected value (a golden-value tautology, not a
  legitimate fixture import).

```bash
python3 harness/scripts/anti_tautology.py <checker_path> --target <module|glob>
```

`--target` is either a dotted module name (`myapp`, matches `myapp` and any
submodule `myapp.sub`), or a glob such as `harness/scripts/grid/*.py` (matches
any module whose dotted name renders to a path under that glob).

## Reading a finding

Each finding is `{file, line, imported_module, severity}`:

- `severity: block` — the checker directly imports the target (plain, `from
  ... import`, aliased, or a resolved relative import). This is the tautology
  the invariant forbids; the verdict is `tainted`.
- `severity: advisory` — a heuristic hit only: a call shaped like
  `<matched-module-alias>.<fn>(...)`, which often means the checker computed
  an "expected" value by calling the very module it verifies (a golden-value
  tautology) rather than hardcoding the expected value in the spec. This is a
  hint, not proof — it never escalates the verdict by itself, and it fires on
  ordinary attribute-call usage too (coarse on purpose, see Risk below).

Verdict is `clean` when no `block` finding exists (advisory-only findings
still yield `clean`); `tainted` when at least one `block` finding exists.

## Advisory-first, never a hard local block

`anti_tautology.py`'s exit code (0 clean/advisory-only, 1 tainted) is meant
to be read advisory-first by a calling gate — same personal-first posture as
`harness/data/stage-policy.yaml` — it does not itself hard-block a local
commit or push. A hard CI gate wiring this check is a decision for whoever
owns that gate config, not something this script does on its own.

## False positives: a legitimate import

A checker sometimes has a real reason to import the target (e.g. a fixture
that must construct a genuine object of the target's type, not fake it).
`--allow <module|glob>` (repeatable) exempts a specific module/glob from
findings — use it narrowly, on the exact module that needs the exception, not
as a blanket suppression. Prefer narrowing `--target` first (scanning only the
sub-module actually being verified) before reaching for `--allow`.

## Scope (KISS/YAGNI — do not over-build)

This is an import-graph scan plus one coarse call heuristic — not a
dataflow analysis, not a semgrep replacement. It does not execute the checker
or the target; it never touches `testability-triad.md` or
`standards.yaml`/`rule_view.py`. It closes the narrow gap where a checker's
imports form a closed loop that proves nothing about the code it claims to check.
