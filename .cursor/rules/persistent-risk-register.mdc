# Persistent risk register — project-wide, outlives any one plan

`docs/risk-register.yaml` is a **project-wide, human-curated SSOT** that survives across
plans. It is a different thing from the **plan-scoped** `risks:` frontmatter a single plan
carries (`red-team-gate.md` disposition) — that block is scoped to its own plan and stops
mattering once the plan closes. The register exists so a risk left un-mitigated in one plan
keeps surfacing at the START of the next one, instead of being silently forgotten.

Anchor:
`docs/product/_refs/frankcode-src/planner-executor/methodology/planner/risk-register.md`
(§Workflow `:36-43`, §Scoring rubric `:70-78`, §Frame template `:47-66`, §Decision table
`:82-90`). Reader/writer: `harness/scripts/risk_register.py`.

## When to add a row

Add a row (`risk_register.py --add`) whenever a plan or a piece of work touches: **auth**,
**payments**, **PII**, a **migration**, a new **external dependency**, or a **contract-delta**
(a breaking API/schema change). These are exactly the categories FrankCode's source flags
(`risk-register.md:22`) as needing an explicit register entry rather than an implicit
"we'll notice if it breaks."

## Scoring rubric (P x I, 1-5 each)

| Score | Probability | Impact |
|---|---|---|
| 1 | never happened on a comparable surface | cosmetic, no user visible |
| 2 | precedent in dev/staging only | one user / one session affected |
| 3 | precedent in production < once/quarter | a cohort of users degraded |
| 4 | recurs monthly on comparable systems | feature unusable for a segment |
| 5 | near-certain given the design | platform-wide outage / data loss / security breach |

`severity = probability x impact`. Cutoffs: **>= 20 CRITICAL** · **12-19 HIGH (blocking)** ·
**6-11 MEDIUM** (mitigate if cheap) · **< 6 LOW** (accept + revisit later).

`risk_register.py --check` is a **read-only deterministic scorer**: it ALWAYS recomputes
severity as `probability x impact` and ignores an authored `severity` value that drifted from
that product (a stale number left behind after a hand-edited P or I). A row is `blocking`
when severity >= 12 **and** its effective status is `open` **and** it carries no mitigation
summary — exit code is non-zero in that case. This is advisory-first: it never hard-blocks a
local stage, the same posture as every other local gate in this harness (§7 of
`docs/system-architecture.md`).

## Response classification

Every row picks one `response`: `mitigate` (change the plan/work to reduce P or I),
`transfer` (offload to a managed service / SLA), `accept` (with a named `owner` and a
`trigger` to revisit), or `avoid` (cut the scope that creates the risk). A mitigation that
lives only in the register text and never becomes a real task/plan-phase is aspirational —
prefer citing a concrete task/phase id in `mitigation.task_ref` when one exists.

## Append-only writes — never rewrite history

- `--add` appends a NEW row to the `risks:` sequence. Validation (id/title/trigger/rollback/
  owner non-empty; probability/impact in `[1,5]`; lens/response/status in their enum) runs
  BEFORE any write — a bad row is rejected with a clear error and nothing is written.
- `--set-status` appends an EVENT `{action, risk_id, actor, ts}` to the `log:` sequence — it
  never rewrites the row's own `status` field. The CURRENT status of a risk is the row's
  authored `status` overridden by the most recent matching `log:` event (`effective_status` —
  same replay-not-rewrite shape `findings_store.py` uses for belief confidence). Both writers
  stamp `actor` + `ts` via `resolve_actor()` (`harness/hooks/hook_runtime.py`), following the
  pattern at `harness/scripts/findings_store.py:128-140`.
- Neither writer ever mutates or drops an existing row or event — only appends. Storage is a
  single YAML file, so a write is still a file-level read -> append-in-memory -> rewrite (not
  a byte-append), but the RECORDS themselves are never mutated. Accepted for now because the
  register is low-volume human config; if audit-trail volume ever grows past that, the
  status-change log graduates to its own append-only `.jsonl` sink (out of scope here — flag
  it if it comes up).

## STRIPPED from the FrankCode source — no SaaS anchor

The upstream `trigger` field is `{metric_id, threshold}` anchored to a Sentry/PostHog metric
(`risk-register.md:59-62`). This harness has no SaaS telemetry backend to anchor to, so
`trigger` here is a **plain observable-condition string** — e.g. "test suite X đỏ", "log chứa
PII", "queue depth vượt ngưỡng cấu hình" — never a metric id or SaaS query. `system_ref §15`
(the upstream system-level mitigation matrix) is also dropped: there is no tầng-1 document at
that address to cite.

## Wiring into `hs:plan` / red-team — advisory, one-directional

This register is an **input** a plan/red-team pass can consult (does this plan touch a risk
category already on file? is there an open, un-mitigated row this plan should either close or
explicitly accept?) — never the reverse. `hs:plan`/red-team does not write to this register
automatically, and a plan's own `risks:` frontmatter is NOT synced back into it. Promoting a
plan-scoped risk into this persistent register (because it recurred, or because it is still
open after the plan closed) is a deliberate, human-reviewed `--add` call — not a mechanical
mirror.

## Anti-patterns (carried from the source, `risk-register.md:112-119`)

- **Register of platitudes** — a row with no probability/impact/trigger is meaningless;
  validation rejects it outright.
- **Mitigation that lives only in the register** — never turned into a real task; write
  `mitigation.task_ref` when a concrete task exists.
- **Accepting without an owner** — no one to revisit when the trigger fires; `owner` is a
  required field.
- **Scoring inflation** — everything rated 5/5 (or 1/1 to dodge the blocking cutoff);
  `--check` recomputing severity catches the drift, not the intent, so a human still has to
  sanity-check new rows at review time.
