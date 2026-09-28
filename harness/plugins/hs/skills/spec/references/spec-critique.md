# Spec critique — MAP into hs:critique, not a second engine

`hs:spec` ships no own critique/consolidator/humanizer stack. The harness
already owns one (`hs:critique`) — a spec artifact rides it via an **explicit
`--lenses` route**, scoped by artifact type. This file is the "how to call
it" doc; the wiring lives in `"${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml` +
`harness/plugins/hs/agents/{spec-tech-critic,spec-craft-critic}.md` +
`spec/scripts/spec_critique_scan.py`.

## Why explicit `--lenses`, not auto-classify

`hs:critique`'s classifier (`critique/SKILL.md` step 1) recognizes exactly
`plan / decision / design / code / diff`; anything it does not recognize falls
back to the generic `default` lens set. A spec artifact (vision/BRD/PRD/epic/
story) is **not** one of those five — the classifier will never route it to
the spec lenses on its own, no matter how the `critique.yaml` spec keys are
named. This is by design: `hs:critique`'s engine is not touched by this
mapping.

So a spec artifact is critiqued by naming the lens set explicitly:

```bash
/hs:critique docs/product/stories/PRD-AUTH-E1-S1.md \
  --lenses spec-tech-critic,spec-craft-critic,product-value-critic,market-fit-critic
```

`spec_critique_scan.lens_set_for(<artifact-path>)` is the resolver that knows
which four names to pass — it reads `"${HARNESS_BIN_ROOT:-.}"/harness/data/critique.yaml`'s spec-family
keys (`spec`/`vision`/`brd`/`prd`/`epic`/`story`, all mapped to the same list
today) so the lens set has one SSOT home instead of being hand-typed at every
call site.

```python
from spec_critique_scan import lens_set_for

lens_set_for("docs/product/stories/PRD-AUTH-E1-S1.md")
# -> ["spec-tech-critic", "spec-craft-critic", "product-value-critic", "market-fit-critic"]

lens_set_for("plans/some-plan/plan.md")
# -> None — not a spec artifact; the classifier-driven plan route is untouched
```

## Scope-by-artifact-type map

| Artifact | `critique.yaml` key | Lens set |
|---|---|---|
| `PRODUCT.md` / anything else under `docs/product/` with no more specific bucket | `spec` | `spec-tech-critic, spec-craft-critic, product-value-critic, market-fit-critic` |
| `vision.md` | `vision` | same |
| `brd.md` | `brd` | same |
| `prds/*.md` | `prd` | same |
| `epics/*.md` | `epic` | same |
| `stories/*.md` | `story` | same |

Two of the four lenses are **reused**, not new: `hs:product-value-critic` and
`hs:market-fit-critic` already existed in `hs:critique` (product-bearing artifact
types `plan/decision/design`) — they carry no spec-graph machinery and judge
desirability/positioning identically on a spec artifact. Only the tech and
craft lenses are spec-specific new agents, mapped from product-spec's own
`tech-critic`/`craft-critic` (feasibility and prose-quality frameworks) but
re-homed as plain `hs` critic agents: neutral tone, no built-in voice/level
knob (voice is `hs:voice`'s job, not the lens's), no JSON-only output
contract divergence from the other `hs:critique` lenses.

## The scan bundle — citation ground truth, nothing else

`spec_critique_scan.build_scan(root, target_id)` builds the JSON a lens agent
reads before it writes a single finding:

- `source_files`: the target artifact PLUS every declared ancestor (via
  `spec_graph.ancestors`), each **line-numbered against the real on-disk
  text** (`"<n>: <text>"`). A lens must cite `<artifact_id>:<line>` where
  `<line>` is a REAL number it read here — never a guessed one, never a bare
  file path.
- `structural_findings`: mechanical validate output, wired in opportunistically
  once `check_traceability` / `check_consistency` output exists. Until then
  this is an empty list — never a fabricated finding. Lenses must not restate a
  structural finding verbatim; their value is the judgment call the mechanical
  check cannot make.

Nothing in this bundle is a verdict. It is inputs a lens reads, same as any
other `hs:critique` lens reads its artifact.

## Discipline: map, don't re-implement

`spec_critique_scan.py` builds a bundle and resolves a lens set. It does
**not**:

- consolidate lens findings into a ranked verdict (`hs:critique-consolidator`
  already does this — reuse it, do not re-implement it),
- apply a voice/level/register pass (`hs:voice` governs harshness harness-wide
  — a spec critique report is neutral by default like every other
  `hs:critique` report),
- write a report file (the controlling `hs:critique` session writes
  `plans/reports/<slug>-critique-report.md`, exactly like any other run).

If a future change to this file starts doing any of the three above, that is
the double-implementation trap this design deliberately avoids — stop and
route back through `hs:critique`'s existing engine instead.

## Applying findings back to the spec — NOT SHIPPED in this build

The origin product-spec project carried an `apply_critique_progress.py` /
`--apply-critique <report>` loop: walk a critique report finding-by-finding,
Keep / Change-and-re-approve / Defer each, record one `DEC-<n>` per resolved
finding, fingerprint-keyed so a re-run never double-records or re-litigates a
disposition (a no-silent-reversal flow). **That resumable apply loop is NOT
ported here** — no `--apply-critique` flag, no script, no fingerprint/resume
state. Today a PO consumes critique findings by hand and records any resulting
decision one at a time via `dec_ledger.py --decision` (no resume or
double-record guard). Porting the resumable apply/governance loop is tracked
in `BACKLOG.md` (BL-234); do not present it as available until it lands.
