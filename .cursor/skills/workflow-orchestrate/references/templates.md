# Templates — reuse the base workflows before authoring one

Harness ships reusable base workflow scripts at `harness/plugins/hs/workflows/*.js`, auto-loaded and registered under the `hs:` namespace. Reuse is the default; a new script is the exception.

## What ships

| Base | Shape | Reuse for |
|---|---|---|
| `hs:base-fanout-consolidate` | N lenses run concurrently (barrier) → mechanical dedup in JS, no agent | multi-lens critique / scout / security-scan / any single fan-out→dedup |
| `hs:base-pipeline-verify` | find → verify, no barrier (item flows stage-to-stage) | review-shaped: findings each get an independent verification pass |
| `ping` | smoke test | verifying the Workflow tool is wired |

Call the **registered name**, not the bare `meta.name`: `Workflow({name:"hs:base-fanout-consolidate", args:{...}})`. If the registry has not picked up a base (no reinstall+restart), fall back to
`Workflow({scriptPath:"harness/plugins/hs/workflows/base-fanout-consolidate.js", args:{...}})`.

## `base-fanout-consolidate` args contract

```
args = {
  lenses:        [{ key, prompt }],   // one agent per lens; prompt is a ready-built string, not a callback
  findingsSchema: <JSON Schema>,      // each lens's structured output; must yield { findings: [...] }
  dedupKeyFields: ["file","line"],    // optional; fields forming the dedup key (empty = whole-object key)
  maxRetry: <int>, retryBaseMs: <int> // optional; deterministic backoff (VM bans wall-clock/RNG)
}
```

Build lens prompts as **data** (strings), never callbacks — the VM cannot serialize closures across agents. Same for any bespoke script.

## When to author a new `workflows/*.js`

Only when the shape is neither a single fan-out→dedup nor a find→verify — e.g. a bespoke multi-stage run (research → consolidate → critique → recommend) with barriers between stages. Then:

- Start from the `meta` literal (pure — no variables/among calls). `phases` titles must match `phase()` calls.
- Body is plain JS, async context, `await` directly. No `Date.now()` / `Math.random()` / argless `new Date()` (they break resume) — pass timestamps via `args`, vary per-index by label.
- Default to `pipeline()`; reach for `parallel()` only at a real barrier.
- Persist the script: every `Workflow({script})` call writes the script to the session dir and returns its path. Iterate by editing that file and re-invoking with `{scriptPath}` — do not resend inline.
- Early-write inside stages via `write_finding.py` (Bash) or by returning findings the orchestrator flushes immediately.

## Bespoke multi-stage skeleton (research → consolidate → critique → recommend)

```js
export const meta = {
  name: 'ctx-min-research',
  description: 'research -> consolidate -> critique -> recommend, early-write per stage',
  phases: [{title:'Research'},{title:'Consolidate'},{title:'Critique'},{title:'Recommend'}],
}
phase('Research')
const research = await parallel(GROUPS.map(g => () =>
  agent(g.prompt, {label:`research:${g.key}`, phase:'Research', schema: FINDINGS})))  // barrier: all before synth
// ... orchestrator flushes each to report_dir via write_finding.py ...
phase('Consolidate')
const directions = await agent(synthPrompt(research), {schema: DIRECTIONS})
phase('Critique')
const judged = await pipeline(directions.items,
  d => agent(critiquePrompt(d), {label:`critique:${d.key}`, phase:'Critique', schema: VERDICTS}))
phase('Recommend')
return await agent(recommendPrompt(directions, judged), {schema: RECOMMENDATION})
```
