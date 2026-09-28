# output-rendering.md — how a report skill/agent renders human-facing prose

Load before generating any report, doc, plan narration, or human-facing summary.
This is the single home of the report-rendering contract. The 21 report skills and
agents named in `test_report_reads_resolved.py` reach it — 18 by carrying one
identical one-line pointer to this file, and `hs:code-review`, `hs:setup` and
`hs:plan` through the rule the CLI routes them at the step instead. The register
BEHAVIOR (audience tiers, the humanize default, the evidence list) lives only
here, never restated in a stanza, so the contract changes in exactly one place.
What is enforced is the SOURCE, not the wording: `test_report_reads_resolved.py`
fails any of the 21 that reads the raw tracked `output.yaml` instead of going
through `--resolved`.

## Resolve the live values FIRST

```bash
python3 harness/scripts/output_config.py --resolved
```

`--resolved` prints `resolve_all()` — the terminal-voice axes and the output-config
register knobs (`language`, `humanize`, `audience`, `code_style`) merged, honoring the
dev override (`HARNESS_OUTPUT`). It is the ONLY sanctioned read. **Do NOT hand-read the
tracked `harness/data/output.yaml`**: that file is the fail-closed gate path and ignores
the dev override by design, so a hand read returns the wrong value for a developer who
set a knob locally. A subagent never receives the session inject, so this resolve is how
it learns the register at all.

## Apply the knobs

- **`language`** (`en` | `vi`, default `vi`): write the prose in this language. Instruction
  text stays English; only the GENERATED prose follows it.
- **`audience`** (`off` | `0..5`, default off): the prose register for the report.
  - `0–1` (plain / guided): open with a plain-language "so what" summary, define every
    term inline on first use, and close with a short glossary.
  - `2–3` (informed / practitioner): normal domain vocabulary, define only specialist terms.
  - `4–5` (expert / peer): dense, terse, lead with the load-bearing point; at 5 assume full
    shared context.
  - The same `audience` value also shapes the terminal chat register (injected per session);
    here it shapes the written report.
- **`humanize`** (`true` | `false`, **default off**): apply
  `harness/data/output-styles/humanizer-and-anti-ai-tells.md` (strip AI-writing tells; when `language: vi`,
  also the Vietnamese translation-tells) ONLY when resolved true. Default is off to save
  tokens — turn it on when publishing a report externally.
- **`code_style`** (`off` | `0..5`): shapes generated CODE only (comment density, verbosity,
  examples). It does NOT alter report prose — that is `audience`. Most report rendering does
  not touch it.

## Evidence is invariant at every level

`audience` and `humanize` shape ONLY the surrounding prose. Evidence tokens —
`file:line` references, IDs, SHAs, numbers, and verbatim quotes — are never translated,
re-rounded, paraphrased, or rewritten at any `audience` level or with `humanize` on. Copy
them exactly as found.

## Where the deliverable lands (`output_rung`)

`hs-run <domain> next` stamps `output_rung` and names this file when the rung is above
the default. The rung says WHERE the deliverable lands; nothing above changes.

- **`markdown`** (default): the documents the step already writes. Nothing extra.
- **`html`**: additionally render ONE self-contained page beside them. Self-contained
  means it opens from disk with no build step and no network: inline the CSS and the
  JavaScript, embed images as `data:` URIs. Honour the `visual:` switches from
  `output_config.py --resolved` — `diagram_design` picks a template from
  `harness/assets/diagram-templates/`, and `antv` (default OFF, 874 KB) is inlined from
  `harness/assets/antv/` only when resolved true. A page whose charts arrive over the
  network renders blank where it is read, and an empty chart looks like a section with
  no data rather than a failure.
- **`wiki`**: publish that page and hand back the link. The page is rendered first —
  `output_rendered` says so — because publishing markdown returns a link to something
  the reader did not ask for. Publishing is outward-facing: confirm with the human
  before it happens, every time, and never publish a page carrying a credential, an
  internal URL, or anything the user framed as sensitive.

The page is an ADDITION, never a replacement: the markdown stays the reviewable,
diffable artifact, and a gate that reads a plan reads that. Content follows the same
contract as any report here — the register knobs above, and evidence invariant.
