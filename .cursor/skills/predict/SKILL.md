---
name: hs:predict
injectable: true
description: 5 expert personas independently debate a proposed change before implementation, catching architectural, security, performance, and UX risks early. Use before large features or high-risk changes.
argument-hint: "<proposal> [--files <glob>] [--chain reason | --chain probe]"
allowed-tools: [Read, Grep, Glob, Bash, Write]
metadata:
  compliance-tier: knowledge
---

# hs:predict — Multi-persona analysis before implementation

Five expert personas independently analyze a proposed change, debate conflicts, then converge on a verdict of **GO / CAUTION / STOP** — before a single line of code is written.

## When to use

- Before implementing a large or high-risk feature
- Before a significant architecture refactor
- When evaluating competing technical approaches
- To check assumptions in a proposed design

## When NOT to use

- Small, low-risk changes (use `hs:debug` for bugs, `hs:plan` for decided work)
- Work that has already been approved with no open design questions
- Pure dependency upgrades that do not change the API
- **Decision is load-bearing AND a mechanical metric exists AND probes are cheap** → escalate to `hs:bakeoff`. predict = fast/cheap LLM verdict; bake-off = real-number decision when persona-guess is too risky.

---

## 5 Personas

| Persona | Focus | Core questions |
|---------|-------|----------------|
| **Architect** | System design, scalability, coupling | Does it fit the architecture? Can it scale? What new coupling is introduced? |
| **Security** | Attack surface, data protection, auth boundaries | What can be abused? Where is data exposed? Are auth boundaries intact? |
| **Performance** | Latency, memory, queries, bundle size | Latency impact? N+1 queries? Memory leaks? Bundle bloat? |
| **UX** | User experience, accessibility, error states | Is it intuitive? What do error states look like? Accessible on mobile? |
| **Devil's Advocate** | Hidden assumptions, simpler alternatives | Why not do nothing? What is the simplest option? Which assumptions could be wrong? |

---

## Debate process

1. **Read the proposal** — from the argument or provided file
2. **Read related code** if file paths are given (grep affected areas)
3. **Each persona analyzes independently** — personas must not influence each other in this phase.
   - **Route first through `hs:workflow-orchestrate`** (before any spawn) — state `reason` (why this
     persona debate), `strategy` (mode + base + persona→count), `scope` (proposal surface + fixed
     5-persona count). This persona set is **config-fixed**, so the route is the cheap challenge layer:
     consume `route_depth` — `light` → proceed via the base below; `agent` → escalate the
     `@workflow-orchestrator` agent before spawning. The exact sizing commands + the
     `groupCap`/`earlyWrite` handoff live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.
   - **ultracode opt-in present** → fan the 5 personas out via the shared
     `Workflow({name:"hs:base-fanout-consolidate", args:{lenses, findingsSchema, dedupKeyFields}})`
     (one lens per persona; deterministic fan-out + mechanical dedup; `scriptPath` if the name is not
     registered). Persona prompts are built as data, not callbacks.
   - **opt-in absent** (mandatory fallback — Workflows are plan-gated) → inline-Task fan-out, exactly
     as today. **Stamp** the path that ran (`Workflow(name)` | `Workflow(scriptPath)` |
     `inline-Task fallback`). Resolve the opt-in per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.
4. **Identify consensus points** — where all (or >=4) personas agree
5. **Identify conflicts** — where personas disagree meaningfully
6. **Weigh trade-offs** — for each conflict, assess which concern has higher impact
7. **Deliver verdict** — GO / CAUTION / STOP with actionable recommendations
8. **Persist** — `Write plans/reports/<slug>-predict-report.md` (the Prediction Report below) — gives `--chain` a file to append and `hs:plan` a path to attach.

---

## Output

Saved to `plans/reports/<slug>-predict-report.md`:

```
## Prediction Report: [proposal name]

## Verdict: GO | CAUTION | STOP

### Consensus points (all personas agree)
- [Point 1]
- [Point 2]

### Conflicts & resolutions

| Topic | Architect | Security | Performance | UX | Devil's Advocate | Resolution |
|-------|-----------|----------|-------------|-----|-----------------|------------|
| [Issue] | [View] | [View] | [View] | [View] | [View] | [Recommendation] |

### Risk summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| [Risk description] | Critical/High/Medium/Low | [Concrete action] |

### Recommendations
1. [Action — reason]
2. [Action — reason]
```

---

## Verdict levels

| Verdict | Meaning |
|---------|---------|
| **GO** | All personas agree, no critical risks, proceed with confidence |
| **CAUTION** | Concerns exist but are manageable — mitigations identified, proceed carefully |
| **STOP** | Unresolved critical issue found — redesign or gather more information before proceeding |

**STOP triggers** (any one of these is sufficient):
- Security: identified auth bypass or data exposure with no viable mitigation
- Architect: identified fundamental design incompatibility requiring significant rework
- Performance: identified unacceptable latency or query explosion with no workaround
- Devil's Advocate: discovered a wrong assumption that invalidates the entire approach

---

## Chain modes (`--chain`)

When verdict is **CAUTION**, a refinement loop can activate:

| Flag | Purpose | When to use |
|------|---------|-------------|
| `--chain reason` | Subjective refinement loop — generate -> critique -> synthesize -> blind judge -> loop until convergence | CAUTION with subjective trade-offs (architecture, design) |
| `--chain probe` | Mine missing requirements — harvest unstated constraints + assumptions | CAUTION/STOP due to missing constraints or unclear assumptions |

Detailed protocol: `references/chain-modes.md`.

---

## Harness integration

| Next step | Skill | How |
|-----------|-------|-----|
| Create implementation plan | `hs:plan` | Attach Recommendations as constraints for the planner |
| Expand risk scenarios | `hs:scenario` | Feed the Risk table as the feature description |

---

## Examples

```
/hs:predict "Add WebSocket for real-time notifications"
/hs:predict "Migrate auth from JWT to session cookies"
/hs:predict "Add multi-tenancy to the database layer"
/hs:predict "Replace REST API with GraphQL" --files src/api/**/*.ts

# Chain modes
/hs:predict "Choose auth lib: Passport vs Better Auth" --chain reason
/hs:predict "Switch from REST to GraphQL" --chain probe
```
