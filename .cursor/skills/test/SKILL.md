---
name: hs:test
injectable: false
description: Run and validate tests for the current change — unit/integration profiles, concise QA report, 100% pass gate. Use when a change needs its tests run and a gate-ready verdict.
argument-hint: "[unit | integration] [--in-place] [--yagni] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:test — disciplined verification

`--yagni` cuts scope not needed for the stated outcome; the default delivers the full ask. Pass it to `hs-run`, which stamps the posture and names the rule.

Run tests for the scope that just changed; report results truthfully — a failure is information, not an enemy.

**Default: delegate the suite run to a `@tester` subagent** (isolates the large test output from the
main context); `--in-place` opts out and runs at main. In the delegated flow the `@tester`
**runs + reports only** (verdict + `checks[]` + Unmapped); **main persists `verification.yaml`** from
that report. The Pre-flight / Profiles / Result-rules sections below describe what gets run and how the
artifact is written — main routes on them; they are not "run it all yourself at main."

**What each step needs is routed by the CLI, not listed here.** Every envelope carries the
`rules` and `references` THIS state needs. Read what the envelope names, and only that. But a
satisfied envelope is not enough to have tested anything — the suite has to actually run, and
the files on disk are what the verdict is about.

## Pre-flight

1-2. **`hs-run test next`** — resolves the stack's own test command AND checks required
   deps in one call. Never assume `pytest`; the verb reports what THIS repo declares.
   exit 11 `ready` → `next_command` is the verbatim runner (`pytest`, `go test ./...`,
   `pnpm test`, …); run exactly that.
   exit 10 `no_stack_detected` / `stack_no_test_cmd` → no stack found, or the stack declares
   no runner. Ask the user
   which command to use — do not guess one.
   exit 2 `deps_missing` → `next_action` is the install command. Stop; do not run blindly.
   Run it from INSIDE the target repo: root resolution walks UP to the nearest `plans/` or
   `.git`, so invoking it from elsewhere measures a different tree than you mean.
3. Quick import-check of the recently modified module (catching import errors here is cheaper than mid-suite).

## Profiles

| Profile | Scope | When |
|---|---|---|
| `unit` (default) | test the modified module → full unit suite | every TDD cycle |
| `integration` | add e2e (`harness/e2e/run_vertical_slice.py`) | before a hard stage |

Standard command: `python3 -m pytest harness/tests/ -q` (this repo). A target repo runs its own suite — use the `next_command` Pre-flight 1-2 reported, never this literal.

`unit` / `integration` here are **run-scope profiles** (how much to run). Do not confuse them with the canonical `test_type` DoD names the gate keys on (Result rules below) — running the `unit` profile is not the same as emitting a canonical `unit` check.

**Focused first pass** (large suite, small change): run only the tests a change can break, then the full suite before the gate — the bundled selector walks the import graph in reverse (it is a SUPERSET, never a replacement for the full pre-merge run):

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/test/scripts/affected_tests.py --base main --pytest
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/test/scripts/affected_tests.py --changed "${HARNESS_BIN_ROOT:-.}"/harness/scripts/foo.py
```


## Result rules

- **100% pass is the gate** (tdd-discipline rule): failure → fix the code or fix a genuinely wrong test (with a reason); deleting/skipping/weakening tests to fake green is forbidden.
- QA report <200 lines: list **ALL** test failures (name + 1-line reason), notable coverage changes, final verdict: PASS / PASS_WITH_RISK (state the risk) / BLOCKED.
- Verdict + checks[] written to `plans/<plan>/artifacts/verification.yaml` (json accepted as legacy)
  (schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`) — the artifact the hard stage gate reads.
  **Owner: in the delegated flow MAIN writes it** from the `@tester`'s reported checks[]; a standalone
  `@tester` (top-level actor, no orchestrating main) writes its own.
- **Never write `verification.yaml` with a raw Bash redirect** (`>` / `cat >`) — it does not trip the PostToolUse hook, so the plan lifecycle never flips and the ship gate silently blocks. Write it via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/write_verification.py` (preferred) **or** the Write tool — both trip the lifecycle hook.
- **Grid coverage (advisory consume):** if `plans/<active>/artifacts/coverage-grid.<yaml|json>` exists, fold a `reject`/`needs-detail` verdict into the QA report as one advisory line — it NEVER flips the test verdict (100%-pass stays the only gate). Absent → silent.
- Each DoD-bearing check uses the **canonical `test_type` name** (`"${HARNESS_BIN_ROOT:-.}"/harness/data/test-policy.yaml`
  → `test_types`; map the runner: jest→`unit`, etc.) and carries `format` + a `file:` the gate re-derives from. Emit a machine-readable result file per stack:

  | stack | runner | reporter → JUnit | file |
  |---|---|---|---|
  | Python | `pytest` | `--junitxml` | `junit.xml` |
  | JS | `jest` | `jest-junit` | `junit.xml` |
  | Go | `go test` | `gotestsum --junitfile` / `go-junit-report` | `junit.xml` |
  | Rust | `cargo test` | `cargo2junit` | `junit.xml` |
  | Java | `mvn`/`gradle test` | surefire/gradle (native JUnit) | `target/surefire-reports/*.xml` |

- **MANDATE — after writing the artifact, before handing off to any hard stage**, the artifact writer
  (main in the delegated flow; the standalone `@tester` otherwise) runs the well-formedness validator
  and fixes anything it reports:
  `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/artifact_check.py --validate-verification plans/<active-plan>`
  (exit 1 = a non-canonical name or a phantom/unparseable result file — the push gate would block on it).

## Delegation + verdict-route (delegate-by-default)

The suite run is **delegate-by-default** to a `@tester` subagent — the win is isolating the (often large) test output from the main context. The `@tester` **runs + reports ONLY**: verdict + `checks[]` + the **Unmapped** list of code files with no covering test.
It **does not write tests**, and it does not re-spawn `@tester`/`/hs:test` (runs the suite directly via Bash in its own process). `--in-place` runs the suite straight at main (opt-out).

The main thread then routes on the verdict against a **DoD-anchored threshold**: a missing required `test_type` (a DoD FAIL) is a LARGE gap → `@developer` writes the test test-first; a coverage nicety or <2 unmapped files is SMALL → main fixes inline.

## Fix loop and regression

When failing: QA report → hand off to hs:cook (fix) or hs:fix (single bug) → re-run. A bug fix must have a regression test written BEFORE the fix (intentional failure).

## Boundaries

hs:test **only runs and reports** — it does not modify code, does not weaken tests, and does not decide on merge. Modifying code → hs:cook / hs:fix. Post-test review → hs:code-review. Evidence validation → hs:debug when root cause needs deep tracing.

## Related skills

- `hs:manual-test`: exploratory / manual API or UX checks no result file captures; emits a `manual` evidence-tier check into the same verification.yaml.
- `hs:rops`: run the suite on another machine when it is too slow or too heavy here, or when a timing needs a host that is not doing anything else. It returns the real exit code and keeps the full log on the remote, so the verdict written here is the run's own, not a truncated tail's.
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent verdict-route analyses over the SAME test results (no shared context); `hs:escalation-consultant` synthesizes the final verdict written to verification.yaml. Approval gate is `hs:workflow-orchestrate`'s own.

## HARD-GATE (real wiring)

`gate_stage.py` reads verification.yaml (json legacy): any check `FAIL` → hard stage is blocked. Fraudulent reporting (PASS while failing) surfaces on the next CI re-run; the trace ledger keeps a record of who wrote what (attribution, verification-mechanism rule).
