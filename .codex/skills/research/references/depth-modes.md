# Depth modes — breadth vs depth (on-demand)

Run in step 4 (synthesis). Determines the synthesis strategy based on mode.

## breadth (default)

**Goal**: quick survey, compare >=2 options, enough to decide the next step.

**Limits**: <=5 sources; at most 3 options compared; no API detail drilling.

**Synthesis process**:
1. Build a trade-off matrix: each option x each criterion (performance, complexity, maintenance, security, adoption) — use `[+] [-] [~]` instead of made-up numbers.
2. Rank: 1 primary recommendation + 1 fallback, with conditions for choosing each.
3. State clearly what was not evaluated (scope boundary).

**Output**: report <=400 lines; executive summary <=5 lines; trade-off matrix as a markdown table; clearly ranked recommendation.

---

## depth

**Goal**: deep understanding of one topic — implementation detail, edge cases, migration path.

**Limits**: <=10 sources; prefer direct fetching over search summaries.

**Synthesis process**:
1. Read changelog / release notes — identify version range, breaking changes.
2. Find GitHub issue patterns (open bugs, known limits).
3. Check security: related CVEs (if any), auth/permission model.
4. Check performance: real benchmark numbers from independent sources.
5. Document the implementation path: quick start + common pitfalls + migration notes.

**Output**: report <=800 lines; has "Quick Start" and "Common Pitfalls" sections; every code snippet includes source and version.

---

## Switching mode mid-research

Started with `breadth` -> one option stands out -> propose switching to `depth` for that option (ask via `AskUserQuestion`, do not switch automatically).

Started with `depth` -> actual scope is larger than expected -> propose `--delegate` to a `@researcher` agent rather than expanding without limit.

## Currency heuristics (security + deprecation)

Apply on every research pass, regardless of mode:

- **Security topics** — always check for recent CVEs and security advisories; note CVE ids, affected versions, and the fixed version.
- **New technologies** — assess community adoption and support level (release cadence, last publish, open-issue trend) before recommending.
- **APIs** — verify endpoint availability and the current auth requirements; flag any endpoint marked beta/experimental.
- **Older technologies** — always note deprecation warnings and the migration path to the supported replacement; a recommendation that lands on a deprecated API is a defect.
- **Currency** — prioritise sources from the last 12 months unless historical context is the point of the question.
