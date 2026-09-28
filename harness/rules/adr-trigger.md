# ADR trigger — when an Architecture Decision Record is required (on-demand)

Load during `hs:plan` when a plan touches architecture. The harness already has the ADR
scaffold (`hs:docs-scaffold --type adr`), the `docs/decisions/adr/` store, and the DEC
ledger — what was missing is the rule for *when an ADR is mandatory before plan lock*.
This rule is the SSOT for that trigger list; the C4 methodology reference points here and
does not restate it.

Most architecture regret is not "we made the wrong call" — it is "we made a call and no
one remembers why". An ADR is a ~200-word artifact that pays off once, when the next
engineer asks "why Postgres over SQLite here?" and the answer is in the repo.

## Trigger table

**Required** (a HIGH-band plan, or any band when the row says mandatory):

- New framework or library with its own mental model (ORM, state machine, workflow engine).
- New or changed data store (any DB, cache, or event store).
- New external vendor (API, SaaS, infra provider) creating a multi-month lock-in.
- New security boundary (auth model change, new trust zone, new PII flow).
- Cross-service contract that pins two services together for > 6 months (MID/HIGH).

**Optional** (LOW/MID plans):

- Picking between two libraries that do the same thing.
- Choosing between two well-understood patterns inside an existing architecture.

**Skip entirely**:

- File-layout tweaks, renames, or any change reversible in < 1 hour.
- Code-style decisions — that is the linter's job.

When a required trigger fires, the plan cannot lock without ≥1 ADR at `status: accepted`,
linked from the plan's Architecture section.

## Where ADRs live

The harness already stores ADRs under `docs/decisions/adr/` and records the decision in
the DEC ledger. Do NOT coin a new store. Author with `hs:docs-scaffold --type adr`.

## Status lifecycle (append-only)

- `proposed` — written, not yet accepted; can be modified freely.
- `accepted` — reviewed at plan lock; now append-only (a change means a new ADR).
- `deprecated` — no longer followed, not yet replaced (rare; usually signals a supersede
  is needed).
- `superseded-by-<id>` — another ADR replaces this one. Point forward; never delete the
  old ADR — it is the record of what was once believed.

Never rewrite history. If the decision changes, write a new ADR that references and
supersedes the old one.

## Required content

Each ADR carries Context (what force pushed the decision), Decision (active voice, present
tense, specific), Consequences (what gets easier/harder, what it locks in, the rollback),
Alternatives considered (real trade-offs, not one-line dismissals), and a **Revisit
trigger** — a concrete, measurable condition under which to re-open the decision (not "if
it breaks"). Target 150–250 words; an ADR longer than one screen has usually merged two
decisions — split it.

## Anti-patterns

- **Retrospective ADR** — an ADR for a decision that shipped months ago; only useful if
  the decision is still live and undocumented, and the date must reflect the original
  decision, noted as written retrospectively.
- **ADR for everything** — ADRs for reversible choices become noise and stop being read;
  use the required/optional/skip table.
- **Copy-paste alternatives** — one-line dismissals that do not engage the trade-off;
  fewer alternatives with real analysis is better.
- **Rewriting an accepted ADR** — once accepted it is append-only; supersede instead.
- **Missing revisit trigger** — without it the ADR is write-once-forget.

## Cross-reference

The C4 workflow's step-8 "ADR trigger check" points here; see
[`../plugins/hs/skills/mermaidjs/references/c4-methodology.md`](../plugins/hs/skills/mermaidjs/references/c4-methodology.md).
The persistent risk register maps a risk to *why* it was accepted or mitigated this
specific way — an ADR captures that reasoning
([`persistent-risk-register.md`](persistent-risk-register.md)).

Adapted from `docs/product/_refs/frankcode-src/planner-executor/methodology/planner/architecture-adr.md`
(Nygard format, When-to-apply, status lifecycle). The FrankCode ADR store path and external
tracker routing are dropped in favour of the harness `docs/decisions/adr/` + DEC ledger.
