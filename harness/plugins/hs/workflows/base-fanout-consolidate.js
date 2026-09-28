export const meta = {
  name: 'base-fanout-consolidate',
  description: 'fan-out N lenses -> mechanical consolidate; data-driven depth-1 base for multi-lens consumers',
  phases: [{ title: 'Fanout', detail: 'one agent per lens, run concurrently' }, { title: 'Consolidate', detail: 'mechanical dedup across all lens findings' }],
}

// Data-driven base for the fan-out -> consolidate shape (critique, predict,
// scout, security-scan find). Every lens runs concurrently (a barrier — all
// findings are needed before dedup), then findings are merged and de-duplicated
// in plain JS (no agent). All inputs arrive as JSON `args`; lens prompts are
// ready-built strings. Invoked as Workflow({name:'hs:base-fanout-consolidate', args:{...}}).
//
// args = {
//   lenses:        [{ key, prompt }],   // one agent per lens; prompt is a ready-built string
//   findingsSchema: <JSON Schema>,      // each lens structured output; must yield { findings: [...] }
//   dedupKeyFields: ["file","line"],    // optional — fields forming the dedup key; empty = full-object key
//   maxRetry:       <int>,              // optional, default 0
//   retryBaseMs:    <int>,              // optional, default 500
// }
const spec = args || {}
const lenses = spec.lenses || []
const keyFields = spec.dedupKeyFields || []
const maxRetry = spec.maxRetry || 0
const retryBaseMs = spec.retryBaseMs || 500

// Structural anti-waste knobs (one source: harness/data/orchestration.yaml,
// resolved by the caller and passed in as args — the VM never reads config).
// Both are STRUCTURAL + VISIBLE: a breach surfaces a log() warning in the run,
// never a throw (a throw would kill the run and the recall the fan-out protects).
const groupCap = spec.groupCap || 0            // 0 = disabled (back-compat)
const earlyWrite = spec.earlyWrite || null     // { runId } — when set, each lens flushes

if (groupCap && lenses.length > groupCap) {
  log(`WARN group-cap: ${lenses.length} lenses > cap ${groupCap} — regroup by concern (one sub per finding is the anti-pattern)`)
}
if (!earlyWrite || !earlyWrite.runId) {
  log('WARN early-write: not configured — findings live only in return values until consolidation')
}

// Append the early-write flush instruction to a lens prompt. When earlyWrite is
// unset the prompt is returned unchanged (back-compat).
function withEarlyWrite(prompt, group) {
  if (!earlyWrite || !earlyWrite.runId) return prompt
  return prompt + `\n\n[early-write] After each finding, flush it via: write_finding.py --run-id ${earlyWrite.runId} --group ${group} --title "<t>" --body "<b>"`
}

// Route-all seam (dogfood; NOT pytest-covered — no Node in CI, so this branch is
// drift-linted, not unit-tested, and proven by dogfood / real_gemini). The caller
// resolves the gemini-partner config and passes args.route = { engine:'gemini',
// purpose, surface }. When engine is gemini and this base workflow is in the
// surface, a lens is asked to run through the single chokepoint gemini_companion
// instead of a native Claude pass. A down/inert companion degrades LOUDLY (the
// proxy reports "degraded to claude"), never a silent fallback.
const route = spec.route || null
function routePrompt(prompt) {
  if (!route || route.engine !== 'gemini') return prompt
  const surf = route.surface
  if (surf && surf !== 'all' && !(surf || []).includes('base-fanout-consolidate')) return prompt
  return (
    `Run this lens through the gemini partner lane (the single chokepoint), NOT a native pass:\n` +
    `  Bash: python3 "\${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/gemini_companion.py ${route.purpose || 'review'} -p "<the lens task below>"\n` +
    `Return the companion's JSON verbatim. If its status is "degraded"/"inert", record "degraded to claude" LOUDLY and do the lens yourself — never silently.\n\n` +
    prompt
  )
}

// agent() with deterministic attempt-index backoff. The VM bans the wall-clock
// and RNG primitives, so the delay is base * 2**attempt — no wall-clock, no
// jitter. Inlined (not imported) because the VM forbids module sharing.
async function withRetry(prompt, opts) {
  let attempt = 0
  while (true) {
    const res = await agent(prompt, opts)
    if (res != null) return res
    if (attempt >= maxRetry) return null
    const ms = retryBaseMs * Math.pow(2, attempt)
    await new Promise((r) => setTimeout(r, ms))
    attempt += 1
  }
}

// Stable dedup key for a finding. With no key fields, the whole object is the
// key; otherwise the named field VALUES are JSON-encoded as an array, which is
// printable (no control chars — the Workflow approval dialog rejects those) and
// collision-safe (distinct field splits yield distinct JSON).
function dedupKey(f) {
  if (!keyFields.length) return JSON.stringify(f)
  return JSON.stringify(keyFields.map((k) => (f && f[k] != null ? f[k] : null)))
}

// Barrier: collect every lens's findings before consolidating.
const all = (await parallel(lenses.map((lens) => () =>
  withRetry(withEarlyWrite(routePrompt(lens.prompt), lens.key), { label: `lens:${lens.key}`, phase: 'Fanout', schema: spec.findingsSchema })
    .then((r) => ({ lens: lens.key, findings: (r && r.findings) || [] })),
)))
  .filter(Boolean)
  .flatMap((r) => r.findings.map((f) => ({ ...f, lens: r.lens })))

const seen = new Set()
const deduped = []
for (const f of all) {
  const k = dedupKey(f)
  if (seen.has(k)) continue
  seen.add(k)
  deduped.push(f)
}

log(`consolidate: ${lenses.length} lenses -> ${all.length} raw -> ${deduped.length} unique`)
return { findings: deduped, lensCount: lenses.length, rawCount: all.length }
