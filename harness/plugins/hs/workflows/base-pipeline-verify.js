export const meta = {
  name: 'base-pipeline-verify',
  description: 'find -> verify -> sweep pipeline; data-driven depth-1 base for review-shaped consumers',
  phases: [{ title: 'Find', detail: 'one finder agent per lens' }, { title: 'Verify', detail: 'adversarially verify each finding as its lens completes' }],
}

// Data-driven base for the find -> verify shape (code-review recall, and any
// consumer that surfaces findings then re-checks each one). All inputs arrive
// as JSON `args` (the VM forbids passing functions across the boundary), so the
// verify prompt is a string TEMPLATE the base renders per finding, not a
// callback. Invoked as Workflow({name:'hs:base-pipeline-verify', args:{...}}).
//
// args = {
//   lenses:        [{ key, prompt }],   // one finder per lens; prompt is a ready-built string
//   verifyTemplate: "...{{field}}...",  // rendered against each finding (placeholders = finding fields)
//   findingsSchema: <JSON Schema>,      // finder structured output; must yield { findings: [...] }
//   verdictSchema:  <JSON Schema>,      // verifier structured output (e.g. { isReal: bool })
//   maxRetry:       <int>,              // optional, default 0 — per-agent retries on null result
//   retryBaseMs:    <int>,              // optional, default 500 — backoff base
// }
const spec = args || {}
const lenses = spec.lenses || []
const maxRetry = spec.maxRetry || 0
const retryBaseMs = spec.retryBaseMs || 500

// Structural anti-waste knobs (one source: harness/data/orchestration.yaml,
// resolved by the caller and passed in as args — the VM never reads config).
// Both are STRUCTURAL + VISIBLE: a breach surfaces a log() warning in the run,
// never a throw (a throw would kill the run and the recall the fan-out protects).
const groupCap = spec.groupCap || 0            // 0 = disabled (back-compat)
const earlyWrite = spec.earlyWrite || null     // { runId } — when set, each finder flushes

if (groupCap && lenses.length > groupCap) {
  log(`WARN group-cap: ${lenses.length} finders > cap ${groupCap} — regroup by concern (one sub per finding is the anti-pattern)`)
}
if (!earlyWrite || !earlyWrite.runId) {
  log('WARN early-write: not configured — findings live only in return values until consolidation')
}

// Append the early-write flush instruction to a finder prompt. When earlyWrite
// is unset the prompt is returned unchanged (back-compat).
function withEarlyWrite(prompt, group) {
  if (!earlyWrite || !earlyWrite.runId) return prompt
  return prompt + `\n\n[early-write] After each finding, flush it via: write_finding.py --run-id ${earlyWrite.runId} --group ${group} --title "<t>" --body "<b>"`
}

// Render "{{field}}" placeholders from a finding object. Plain string replace —
// no eval, no template engine.
function render(template, finding) {
  return String(template == null ? '' : template).replace(
    /\{\{(\w+)\}\}/g,
    (_, k) => (finding && finding[k] != null ? String(finding[k]) : ''),
  )
}

// Route-all seam (dogfood; NOT pytest-covered — no Node in CI, so drift-linted and
// proven by dogfood / real_gemini). The caller passes args.route = { engine:'gemini',
// purpose, surface }. When engine is gemini and this base workflow is in the surface,
// the FINDER runs through the single chokepoint gemini_companion instead of a native
// pass; the adversarial VERIFY stays native (a second-engine finder cross-checked by
// Claude). A down/inert companion degrades LOUDLY, never a silent fallback.
const route = spec.route || null
function routePrompt(prompt) {
  if (!route || route.engine !== 'gemini') return prompt
  const surf = route.surface
  if (surf && surf !== 'all' && !(surf || []).includes('base-pipeline-verify')) return prompt
  return (
    `Run this finder through the gemini partner lane (the single chokepoint), NOT a native pass:\n` +
    `  Bash: python3 "\${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/gemini_companion.py ${route.purpose || 'review'} -p "<the finder task below>"\n` +
    `Return the companion's JSON verbatim. If its status is "degraded"/"inert", record "degraded to claude" LOUDLY and do the finder yourself — never silently.\n\n` +
    prompt
  )
}

// agent() with deterministic attempt-index backoff. The VM bans Date.now /
// Math.random / new Date, so the delay is base * 2**attempt — no wall-clock,
// no jitter. Inlined (not imported) because the VM forbids module sharing.
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

// Pipeline (no barrier): each lens's findings start verifying the moment that
// lens's finder returns, while other lenses are still finding. The verify stage
// spawns one agent per finding, so a lens returning many findings blows the wave
// past the cap — the one-sub-per-finding anti-pattern. groupCap guards the LENS
// count; this guards the per-lens VERIFY wave. Structural + visible (a log warn),
// never a throw or a silent drop: every finding is still verified — the warn tells
// the caller to regroup so the wave does not balloon next time.
const results = await pipeline(
  lenses,
  (lens) => withRetry(withEarlyWrite(routePrompt(lens.prompt), lens.key), { label: `find:${lens.key}`, phase: 'Find', schema: spec.findingsSchema }),
  (review, lens) => {
    const findingsForVerify = (review && review.findings) || []
    if (groupCap && findingsForVerify.length > groupCap) {
      log(`WARN verify-cap: lens ${lens.key} returned ${findingsForVerify.length} findings > cap ${groupCap} — the verify wave spawns one agent per finding; regroup so the wave does not blow the cap`)
    }
    return parallel(findingsForVerify.map((f) => () =>
      withRetry(render(spec.verifyTemplate, f), { label: `verify:${lens.key}`, phase: 'Verify', schema: spec.verdictSchema })
        .then((verdict) => ({ ...f, lens: lens.key, verdict })),
    ))
  },
)

return { findings: results.flat().filter(Boolean), lensCount: lenses.length }
