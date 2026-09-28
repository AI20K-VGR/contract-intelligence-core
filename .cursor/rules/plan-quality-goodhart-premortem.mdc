# Plan quality — Goodhart check + pre-mortem (on-demand, should)

Load at `hs:plan`'s red-team/validate step, BEFORE spawning `@red-teamer` — a should-tier
check (MoSCoW): a skipped run does not block plan approval, but skipping it loses the
cheapest failure-catching pass in the loop.

### Goodhart 30-second check

Before finalizing a metric-bearing success criterion, spend 30 seconds asking "if
someone optimized ONLY this number and ignored the intent, what would they do?" — a
criterion that survives that question (the gamed version is still useless to the user)
is safe to ship; one that does not survives needs a second criterion that closes the gap.

### pre-mortem 6-lens

Before red-team, walk all 6 lenses below and surface a finding — or explicitly note "not
applicable" — for EACH one; a lens silently skipped is a lens never actually considered.

| Lens | Seed question |
|---|---|
| Technical | what breaks first under load/scale/edge-case input? |
| UX | where does a user get confused or stuck mid-flow? |
| Adoption | why would a user NOT switch to this from what they do today? |
| Organizational | which team/owner does this create new work for, unasked? |
| External | what upstream dependency/API/vendor can silently change under this? |
| Security | what does this expose that was not exposed before? |

Findings from this pass feed the plan's `risks:` frontmatter. Severity reuses the C/H/M/L
scale `hs:plan`'s red-team reference already defines — do not invent a new scale here.

## Examples

IN: Organizational lens surfaces "this needs the infra team to rotate a secret" —
recorded as a risk before red-team, not discovered mid-cook.
OUT: skipping the Security lens because "this is just a docs change" without writing
"not applicable" — the lens was never actually asked, just assumed away.
