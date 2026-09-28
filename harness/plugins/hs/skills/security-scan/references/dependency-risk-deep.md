# Dependency risk (deep) — beyond CVE (on-demand)

A `hs:security-scan` reference for the *softer* supply-chain signals that a CVE scanner
misses. Trivy/pip-audit catch known CVEs; they do not catch "this package has one
maintainer who has not responded to an issue in 18 months" or "this adds 47 transitive
deps for a function you could write in 10 lines". This is the DEEP layer — it complements
the CVE layer in [`secret-and-dependency.md`](secret-and-dependency.md), it does not
replace it (no overlap; cross-link, do not restate the CVE checks).

## Trigger conditions

- A change adds a new entry to `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`,
  or equivalent.
- A change bumps a dependency's major version.
- A change adds a new SaaS/API integration (a network dep, not a library) — see the
  handling discipline in the secret-lifecycle 7-stage checklist (linked from the skill).

## Risk signals

| Signal | Evidence source | Weight |
|---|---|---|
| Maintainer count = 1 | repo metadata | High |
| Last commit > 12 months ago | repo metadata | High |
| Unresolved security issues open > 90 days | upstream advisories | High |
| Transitive dep count > 20 for a leaf-use package | `npm ls` / `pipdeptree` | Medium |
| License incompatible with the project license | SPDX identifier comparison | **Block** — hard fail |
| Native code requiring platform-specific builds | package manifest | Medium |
| Ships pre-built binaries | manifest / post-install | Medium (High if a post-install runs arbitrary code) |
| Post-install script present | `scripts.postinstall` or equivalent | **Block** — hard fail |

## Scoring

1. Detect a trigger match.
2. Collect evidence per signal.
3. Score: **≥2 High signals OR any Block signal → block**; **1 High → revise** (with an
   independent co-sign path). License-incompatible and post-install-script are **Block**
   on their own.
4. Suggest an alternative when one exists ("you could write this in 10 lines and avoid the
   47-dep transitive chain").
5. Fold the verdict into the security-scan report — map `block`/`revise` to the tier-1
   Severity scale (Critical/High) and record it in `security-scan.json`; write the
   detail report under `plans/reports/`.

## SaaS / API integrations (extra)

For a network dependency, additionally check:

- **Data residency** — where does data flow? Does it comply with the project's PII policy?
- **Authentication lifecycle** — how does secret rotation work? (the secret-lifecycle
  7-stage checklist covers the handling discipline).
- **Outage protocol** — what happens when the SaaS is down? Circuit breaker, fallback,
  graceful degradation?
- **SLA** — is an explicit SLA reviewed and acceptable?

## Outputs

- A per-dependency risk note under `plans/reports/`.
- A `security-scan.json` verdict entry with the risk signals and any suggested alternatives,
  Severity mapped to Critical/High.

## Anti-patterns

- Adding a "small utility" package that pulls in a large transitive chain.
- Accepting a single-maintainer dep "because it is popular" (popularity ≠ maintenance).
- Ignoring license signals "because we will check later" (a license propagates).
- Approving a post-install script without reading it.

Adapted from `docs/product/_refs/frankcode-src/qa/methodology/qa/dependency-risk.md`;
tracker/impact-graph references dropped, verdict mapped to the tier-1 Severity scale and
`security-scan.json`. The threat-model trigger for a new dependency is in
[`threat-model.md`](threat-model.md). Routing this reference into `security-scan/SKILL.md`
is the security-skill integration phase's job — not done here.
