---
name: hs:security-scan
injectable: true
description: Scan codebase for security issues — hardcoded secrets, dependency CVEs, injection/authz gaps, STRIDE+OWASP. Use before releases, after adding auth/payment/data, or for periodic audits.
argument-hint: "[path|glob] [--secrets-only] [--deps-only] [--red-team] [--iterations N] [--fix] [--compliance <fw>]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:security-scan — security audit with threat model

Structured STRIDE + OWASP scan. Detects secrets, dependency CVEs, injection vulnerabilities, and authz gaps. With `--red-team`, runs a 4-persona attacker loop before summarizing. Threat-model-first: identify boundaries and assets before searching for bugs.

**Does not** replace a pentest; **does not** perform runtime analysis; **does not** audit infrastructure (reads only code + config tracked in git).

`hs-run security next` names the state and routes what that state needs. But a satisfied
envelope is not enough to have audited anything: it reports one mechanical sweep of the
narrow surface the tool could reach, and reading every document it routes leaves the code
on disk exactly as safe or unsafe as it was.

## When to use

- Before a release or major merge
- After adding auth, payment, or data-handling code
- Periodic review (monthly/quarterly)
- Compliance prep — SOC2 / GDPR / PCI-DSS / HIPAA gap-mapping
- When the `@code-reviewer` agent raises a trust-boundary concern

## When NOT to use

- Purely cosmetic changes (CSS, copy)
- No code handling user input or sensitive data

## Modes & Flags

| Invocation | Behavior |
|---|---|
| `/hs:security-scan` | Full audit — STRIDE + OWASP + secrets + deps |
| `/hs:security-scan --secrets-only` | Scan secrets/credentials only |
| `/hs:security-scan --deps-only` | Dependency audit using the project's tool only |
| `/hs:security-scan --red-team` | 4 attacker personas → STRIDE/OWASP sweep |
| `/hs:security-scan --red-team --iterations N` | Red-team limited to N iterations |
| `/hs:security-scan --fix` | Audit → iteratively fix Critical/High (with guard) |
| `/hs:security-scan --compliance <fw>` | Map findings to SOC2/GDPR/PCI-DSS/HIPAA (references/compliance-frameworks.md) |
| `/hs:security-scan <path>` | Limit scope to a path/glob |

Flags can be combined: `--red-team --fix --iterations 10`. `--compliance` with no framework maps all four.

## The loop

```
hs-run security next
```

Run it, read the `state`, do the judgment that state names. Each state is derived from
what is on disk right now, and the envelope carries the rules and references THAT state
needs — read what it names, and only that.

The sweep is the START of a security pass, never the end. It reads a deliberately narrow
surface and says so; the STRIDE/OWASP reasoning, the code-pattern pass and the severity
call are yours.

**What the mechanical sweep does NOT read** — state this in the report rather than
letting a clear result imply more than it means:

- **Excluded by convention**: `tests/ spec/ specs/ fixtures/ examples/ samples/ mocks/
  __tests__/`, `test_*.py`, `*_test.py`, and any `.md .lock .example .sample .template
  .dist` file. Measured: the same AWS key in 10 such paths returns clean; in `leak.txt`
  it blocks.
- **Only the CHANGED working tree**: `git diff HEAD` (staged + unstaged) plus untracked
  file content. A tracked file nobody modified, and anything living only in commit
  history, are BOTH invisible — measured, a committed unmodified file holding a real key
  returns clean.
- **Gitignored paths**, binary files, and everything past the first 1,000,000 bytes of a
  file.

Flag steps the sweep does not own: `[--red-team]` the 4-persona attacker loop ·
`[--compliance]` map findings to framework controls (references/compliance-frameworks.md)
→ `## Compliance` section · `[--fix]` fix one finding → guard (test/lint) → commit →
next. Finish by writing the report to `plans/reports/security-scan-<date>-<scope>.md`.

**Orchestration of the persona fan-out (`--red-team`).** The 4 attacker lenses are a
read-only fan-out. Route first through `hs:workflow-orchestrate` before any spawn —
state `reason`, `strategy` (mode + base + persona→count) and `scope`. The persona set is
**config-fixed**, so the route is the cheap challenge layer: `route_depth` `light` →
proceed via the base below; `agent` → escalate the `@workflow-orchestrator` agent first.
- **ultracode opt-in present** → run them via the shared `Workflow({name:"hs:base-fanout-consolidate", args:{lenses, findingsSchema, dedupKeyFields}})` (one lens per attacker persona; deterministic fan-out + mechanical dedup; `scriptPath` if the name is not registered). Persona prompts are built as data, not callbacks.
- **opt-in absent** (mandatory fallback — Workflows are plan-gated) → the inline persona loop, as today.
- **Stamp** the path that ran (`Workflow(name)` | `Workflow(scriptPath)` | `inline-Task fallback`).

**`--fix` writes stay on the parent / `hs:fix`.** The fan-out base is read-only; it never writes. A Workflow-orchestrated `--fix` (where a `workflow-subagent` does the Edit) works out of the box under the deny-list write-RBAC: a subagent edits project source freely, refused only the hard floor (guard code + `harness/**`). No lane setup; `--fix` may also run inline on the parent.

## Severity

| Level | Meaning | Fix priority |
|---|---|---|
| **Critical** | Immediately exploitable, data breach or RCE | Block release |
| **High** | Exploitable with moderate effort, large impact | This sprint |
| **Medium** | Hard to exploit, limited impact | Next sprint |
| **Low** | Theoretical risk, defense-in-depth | Backlog |
| **Info** | Best practice, no direct risk | Optional |

## Credential hygiene (required)

- **DO NOT** print real secret values in the report — mask as: `<REDACTED_TOKEN>`, `<REDACTED_PASSWORD>`
- Reject any finding containing an unmasked JWT (`eyJ…`), 32+ hex chars, or `AKIA`/`ASIA` prefix
- Do not auto-edit code in `--secrets-only` mode — report only and recommend rotation

## Boundaries

- DO NOT merge or deploy automatically; scan output is input — the fix decision belongs to the human.
- `--fix` only repairs confirmed Critical/High findings; commit pattern: `security: <short description>`.
- `--fix` stops early on guard failure — report actual status rather than continuing.
- Do not edit files outside `plans/reports/` (report) unless `--fix` is active.
- Findings require a `file:line` anchor or a reproduction command — no anchor → tag `[ASSUMED]` (or `[PRIOR]` if it rests on prior/training knowledge).
- On exit: absolute path of the report + unresolved questions.

## HARD-GATE (real wiring)

```
harness/install/git-pre-push-hook.sh    — transport-level gate; scrubs HARNESS_*
                                          env before judging; missing python3 →
                                          fail-closed

"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml          — stage → artifact requirements config;
                                          stages pr/ship/deploy require verification
                                          + review-decision + plan-approval

harness/plugins/hs/agents/code-reviewer.md
                                        — agent that reviews trust-boundary / auth /
                                          data-leak / input-validation; security
                                          findings from code-reviewer feed into scan

plans/reports/                          — long-term storage for security-scan reports
```

**The pre-push hook blocks SECRETS. It does not block missing paperwork** — the two are
different postures in the same function and the difference is worth knowing before you
rely on it. A secret in the diff being pushed returns a block reason and the push stops.
A missing or failed stage receipt (verification / review-decision / plan-approval) prints
a `[pre-push warn] ... remote receipts-gate will enforce` line to stderr and returns
None — the push PROCEEDS. Enforcement of receipts is remote, in CI, not here.

The stage-policy line above is the one that holds: `pr`/`ship`/`deploy` each require all
three artifacts, and that requirement is real.

Second caveat on "every push": `.git/hooks/pre-push` is an INSTALLED COPY, outside the
manifest's reach. It gates every push only for as long as that copy is intact — an
uninstalled or edited hook fails silently by not existing.

Secrets caught at pre-push are the transport layer; this scan is an earlier one
(pre-commit / on-demand). Neither replaces the other.

## Gate mode (opt-in ship gate)

Ships OFF. To make a security scan a hard requirement for a stage, an org adds `security-scan` to that stage's `requires:` in `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` (e.g. `ship: { requires: [verification, review-decision, security-scan] }`). Then a stage gate passes only when a verdict artifact exists and reads PASS — produce it after a scan:

```json
// plans/<active>/artifacts/security-scan.json  (schema: harness/schemas/artifact-security-scan.json)
{ "verdict": "PASS",            // PASS = no unresolved HIGH/CRITICAL; else BLOCKED
  "stage": "ship", "actor": "<resolve_actor>", "ts": "<iso8601>",
  "findings": [ { "severity": "high", "category": "secret", "location": "f.py:12",
                  "finding": "...", "status": "fixed" } ] }
```

Default-OFF on purpose: requiring it where no scanner runs would brick the stage (same lesson as critique-consensus). The presence gate proves a scan ran, not who.

## Workflow position

Typically run: before `hs:code-review` (scan provides security context) · before `hs:git` ship
Related: `hs:code-review` (security dimension) · `hs:fix` (fix findings) · `hs:plan` (schedule Medium/Low)

