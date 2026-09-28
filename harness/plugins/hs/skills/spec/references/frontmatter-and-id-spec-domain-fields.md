# Frontmatter & ID Spec — Domain Fields

Split from [frontmatter-and-id-spec.md](frontmatter-and-id-spec.md) (reference size cap) — same doc/authority, only location moved.

## Domain Fields

### `personas`
List of persona **labels** (English keys). Free-text labels chosen by the PO, capped 2–4 by default (soft guidance, not hard limit).

```yaml
personas: [shopper, store-admin]
```

### `scope`
Enum: `in` (this artifact is in-scope for the current release), `out` (explicitly out-of-scope), `core-value` (this artifact is part of the product's stated core value proposition).

`core-value` is the PO's claim; `--validate` asks the LLM to score `aligned | weak | off` against `PRODUCT.md`'s core-value sentence.

### `moscow`
Enum: `must`, `should`, `could`, `wont`. Applied to PRD functional requirements and stories. PRD-level may carry an aggregate; story-level is per-story.

### `horizon`
Enum: `now`, `next`, `later`. Roadmap classification. Roadmap viz groups by this.

### `size` (stories only)
Enum: `S`, `M`, `L`. Coarse PO-level effort indicator (not story points). No engineering-units estimation.

### `metrics`
List of metric references (free-text identifiers). PRDs reference BRD-goal metrics; stories may reference PRD metrics.

```yaml
metrics: [conversion-rate, time-to-checkout]
```

### BRD `goals` (under `brd.md` `goals:` key)

`goals:` is **list-of-dicts**, not a list of bare IDs. Each goal entry MUST carry the following keys; `spec_graph.py` expands them into `type: goal` nodes (`BRD-G<n>`) that PRDs reference via `brd_goals: [BRD-G<n>, …]`. Flat ID strings cause `dangling_link` findings at validate time.

```yaml
# inside brd.md frontmatter
goals:
  - id: BRD-G1                                  # parent-scoped ID, required
    title: "Onboard 100 boutique brands in 12 months"  # required, prose
    metrics: [brands-onboarded]                 # required, ≥1 metric slug (plural key)
    status: draft                               # required, closed enum
    owner: Jane Doe                             # optional, accountable person; LLM should ask if missing
    moscow: must                                # optional, MoSCoW priority (must|should|could|wont)
  - id: BRD-G2
    title: "Achieve 80% 90-day repeat-purchase rate"
    metrics: [repeat-rate-90d]
    status: draft
```

The metric key is plural `metrics:` (a list). A legacy spec on the old singular `metric:` is not auto-rewritten: validate
emits a `legacy_metric_key` **warn** (never an error block) and stops there — the check only warns, it does not rename
anything. The rename to `metrics:` (value preserved) is manual: edit the goal's frontmatter by hand, then confirm with
the PO. A goal key outside `id/title/metrics/status/owner/moscow` warns `unknown_goal_key`.

The BRD template (`assets/templates/brd.md`) carries a YAML comment block above `goals:` repeating this shape so a PO opening a freshly generated `brd.md` sees the contract inline.

### `acceptance_criteria` (stories only)
List of strings, each a single AC. Scripts count and presence-check; LLM evaluates testability.

```yaml
acceptance_criteria:
  - "Given a registered user, when they sign in with correct credentials, then they reach the home page."
  - "Given five failed sign-ins, when the user tries again, then the account is rate-limited for 15 minutes."
```

### Multi-dimensional impact fields (RISK / TIME / COMPETITION)

These optional fields carry the multi-dimensional impact data. All are optional, so a spec that omits them parses and
validates exactly as before (back-compat). **COST is deliberately NOT a field** — it is approximated by the existing
`size: S|M|L` proxy on stories; the skill stores no money/effort figure.

#### `risks` (epic / PRD only)

Optional list, each item:
`{description: str, impact: low|med|high, likelihood: low|med|high, status: open|mitigated|accepted, mitigation: str}`.
`description` is the only required key; `impact`/`likelihood`/`status` are validated against their closed enums (a
risk's `status` is `open|mitigated|accepted`, distinct from an artifact's `draft|review|approved`). Drives the
risk-matrix viz; a top-heavy register (>50% `impact: high`) warns, and a sizeable epic with no risks warns (blind spot).

```yaml
risks:
  - description: "Stripe onboarding/KYC delays a brand's first payout, blocking launch."
    impact: high
    likelihood: med
    status: open
    mitigation: "Pre-collect KYC docs during onboarding, before checkout goes live."
```

#### `target_date` (PRD / epic) and `depends_on` (PRD / epic)

- `target_date` — a single ISO calendar date (`YYYY-MM-DD`). A child due after its parent, or before a prerequisite,
  warns. Only the SHAPE is structural; overdue-vs-today is advisory (a separate `time_advisory.py`, outside the validate
  gate, so `--validate` stays reproducible).
- `depends_on` — a list of artifact IDs this artifact waits on (PRD + Epic only). An unresolved target is `dep_dangling`
  (error); a circular chain is `dep_cycle` (error).

```yaml
target_date: 2026-09-30
depends_on: [ PRD-CHECKOUT-E1 ]
```

#### `competitors` (BRD only) and `competitive_parity` (PRD)

Competitor IDENTITY lives ONCE in the BRD's `competitors:` list (the DRY home). A PRD references those competitors by ID
via the ID-keyed `competitive_parity` map.

- `competitors` — list, each item: `{id: COMP-<SLUG>, name: str, url: str, threat: low|med|high}`. A `url` beginning
  `private:` is dropped before it reaches the graph/render (OpSec chokepoint).
- `competitive_parity` — mapping `{COMP-ID: ahead|parity|behind|none}`. Each key must resolve to a BRD competitor id
  (else `unknown_ref` error); each value is a parity enum.

```yaml
# brd.md
competitors:
  - id: COMP-SHOPIFY
    name: "Shopify"
    url: "https://www.shopify.com"
    threat: high
# prds/checkout.md
competitive_parity:
  COMP-SHOPIFY: behind
```

### `assumptions`, `dependencies`, `out_of_scope` (PRD)

Optional free-text content. These are PRD **body sections** (rendered as optional `<!-- OPTIONAL -->` blocks in the
`prd.md` template), not frontmatter fields. No script reads them from frontmatter. Surfaced during the PRD interview as
narrative prose; for structured ordering dependencies use the frontmatter `depends_on` field instead.

