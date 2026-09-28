# Evidence standard — verified vs assumed (on-demand)

Supplements `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` (core invariants live there — not repeated here). This file is the applied guide for the research context.

## Claim classification

| Status | Condition | Action |
|---|---|---|
| `VERIFIED` | has URL + date, or `file:line` in the repo | Use normally |
| `ASSUMED` | no independent anchor; inference only | Tag clearly, add to open questions |
| `CONFLICTING` | >=2 sources contradict each other | Record both; note the conflict; do not pick a side |

## Valid evidence in research

- Direct URL to doc / repo / article + access date (or publish date)
- Actual command output (`$ <cmd>` -> `<output>`) when verifying with Bash
- `file:line` of config / schema in the current repo
- Benchmark numbers from an independent source (not self-reported by the vendor)

## Invalid evidence

- "Typically..." / "Best practice is..." with no source
- A memory summary without fetching the original source
- A single marketing source used to confirm that same vendor's claim
- Undated timestamp (undated blog, unversioned wiki)

## Two-way Evidence Filter (applied verbatim from verification-mechanism)

- **Finding**: no `URL`/`file:line`/reproducible command -> reject claim, do not build on it
- **Researcher's claim**: unanchored -> tag `[ASSUMED]` (or `[PRIOR]` if it rests on training knowledge), add to open questions, do not conclude

## How to anchor a claim in the report

```markdown
<claim text> [1]

...

## References
[1] https://example.com/docs/page | Official docs | 2025-06 | VERIFIED
```

`[ASSUMED]`/`[PRIOR]` claim -> add to "Open questions" at the end of the report:
```
- [ASSUMED] <claim> — source needed: <suggested search direction>
```
