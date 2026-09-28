# Skill Routing

What the loaded skill catalog cannot tell you on its own: which two skills an intent
could plausibly land on and which one wins, what ORDER they run in, and the leaf
skills nothing else routes into. Pick ONE skill per distinct user intent.

---

## Domain routing — read the catalog, not a copy

Every skill carries its own `description` in frontmatter, and the runtime loads all
130 of them. A hand-written domain tree here duplicates that catalog and drifts from
it silently: measured on the tree this rule used to carry, **55 of 64 rows** said no
more than the skill's own description already did.

So: to find the skill for a technical domain, match the intent against the loaded
descriptions. Reach for `/hs:find-skills` when nothing obvious matches, or when the
skill may be install-disabled (its description is then absent from the loaded set —
that is the case a description scan CANNOT answer and this rule can).

What the catalog cannot tell you is below: which skills are easy to CONFUSE with each
other, and which ORDER they run in.

### Pairs that look interchangeable and are not

| If the intent is... | not | but |
|---|---|---|
| a small local diff, pre-commit | `/hs:review-pr` | `/hs:code-review` |
| a GitHub PR / GitLab MR, with CI | `/hs:code-review` | `/hs:review-pr` |
| find where something lives, fast | `/hs:understand` | `/hs:scout` |
| build a map of an unfamiliar repo | `/hs:scout` | `/hs:understand` |
| a concrete red test or stack trace | `/hs:debug` | `/hs:fix` |
| behaviour is wrong, cause unknown | `/hs:fix` | `/hs:debug` |
| pick between approaches, none chosen | `/hs:plan` | `/hs:brainstorm` |
| approach chosen, needs phases | `/hs:brainstorm` | `/hs:plan` |
| the problem itself is still vague | `/hs:plan` | `/hs:discover` |
| copy behaviour from another repo | `/hs:research` | `/hs:port` |
| a number must get better by iterating | `/hs:cook` | `/hs:finetune` |
| the skill is off / cannot be found | `/hs:use` | `/hs:find-skills` first |

### Usage Notes

- Pick ONE skill per distinct user intent.
- When a task spans two domains ("build + deploy"), name the primary skill and mention
  the secondary rather than invoking both.
- A domain skill slots between the workflow skills: `/hs:plan` → domain skill → `/hs:cook`.

---

## Workflow routing — by task intent

When orchestrating multi-step tasks, consider these workflow sequences. Skills are listed in typical execution order.

### Core Development Workflow

```
/hs:plan → /hs:cook → /hs:test → /hs:code-review → /hs:ship → /hs:journal
```

| User Intent | Suggested Start |
|-------------|----------------|
| "implement feature X", "build X", "add X" | `/hs:plan` then `/hs:cook` |
| "execute this plan" | `/hs:cook <plan-path>` |
| "quick implementation" | `/hs:cook --fast` |

### Bugfix Workflow

```
/hs:scout → /hs:debug → /hs:fix → /hs:test → /hs:code-review
```

| User Intent | Suggested Start |
|-------------|----------------|
| "X is broken", "error in X", "bug in X" | `/hs:fix` (auto-scouts internally) |
| "CI is failing", "tests broken" | `/hs:fix --auto` |
| "investigate why X happens" | `/hs:scout` then `/hs:debug` |

### Investigation Workflow

```
/hs:scout → /hs:debug → /hs:brainstorm → /hs:plan
```

| User Intent | Suggested Start |
|-------------|----------------|
| "understand how X works" | `/hs:scout` |
| "why is X happening" | `/hs:debug` |
| "explore options for X" | `/hs:brainstorm` then `/hs:plan` |

### Post-Implementation Checklist

After completing implementation work, consider:
- `/hs:code-review` — review changes before merging
- `/hs:ship` — run full shipping pipeline (tests, review, version, PR)
- `/hs:journal` — document decisions and lessons learned
- `/hs:sowat` — ask whether the RIGHT thing was built, not whether it works
- `/hs:sumup` — recap the implementation for a human reader (`/hs:handoff` is the
  agent-facing counterpart)

### Advisory & Intake

Before committing to build — reframe, decide, or intake:

| User Intent | Suggested Start |
|-------------|----------------|
| "should I build X?", "second opinion", "sanity-check this idea" | `/hs:advise` (one-question-at-a-time interview → honest verdict) |
| "turn this GitHub issue into a plan", "triage issue #N" | `/hs:issue-to-plan` (audit gate → plan, stops before implement) |
| "reason carefully about X", "this needs rigor, not a fast answer" | `/hs:fable-thinking` (evidence-typed, adversarial reasoning protocol) |
| "no obvious owner", "this spans several areas", "where does this go?" | `/hs:dispatch` (classify → route → set the gate the risk earns) |
| "about to leave it running", "am I ready to start a long run?" | `/hs:goal-warmup` (Ready / Blocked / Decision-required before autonomy) |
| "explain that plainly", "ELI5", "explain this to my PM" | `/hs:eli5` (pitch an explanation at a named audience) |
| "generate an image", "make artwork for this" | `/hs:ai-artist` (image generation, distinct from `/hs:ui-ux` design work) |
| "write the landing copy", "headline / CTA / email campaign" | `/hs:copywriting` (conversion copy, distinct from `/hs:docs` technical writing) |

### Setup Skills

Before starting implementation in a shared codebase:
- `/hs:worktree` — create isolated worktree for the feature/fix
- `/hs:scout` — discover relevant files and code patterns
- `/hs:compound` — build the change so the next one is cheaper, not just this one

### Leaf skills — one line each, no tree

These have no handoff edge from another skill: nothing routes INTO them, so this
list is their only inbound edge and the reason it survives the cut. One line, the
distinguishing fact only — the skill's own `description` carries the rest.

- `/hs:databases` schema + query design · `/hs:web-frameworks` Next.js App Router / RSC ·
  `/hs:tanstack` TanStack Start/Form · `/hs:react-best-practices` React perf patterns ·
  `/hs:mobile-development` React Native / Flutter / SwiftUI
- `/hs:payment-integration` Stripe / Polar / SePay · `/hs:shopify` apps, Polaris, Liquid ·
  `/hs:use-mcp` discover + run MCP tools · `/hs:google-adk-python` Google ADK agents
- `/hs:design` brand identity, logos · `/hs:stitch` AI design generation ·
  `/hs:shader` GLSL / procedural graphics · `/hs:html-video` render a page or deck to video
- `/hs:llms` generate llms.txt · `/hs:mintlify` Mintlify docs site ·
  `/hs:markdown-novel-viewer` read long-form specs in a browser ·
  `/hs:interview-docs` author docs by interviewing whoever knows
- `/hs:release` cut a versioned release · `/hs:eval-bootstrap` stand up an eval suite ·
  `/hs:prompt` write or sharpen a prompt · `/hs:folder-context` read one folder's own
  conventions before editing it · `/hs:cti-expert` OSINT / threat-intel investigation

### The harness's own surfaces

These act on the harness rather than on your code:
- `/hs:cli` — which `hs-run`/`hs-cli` subcommands read, which mutate, and what may
  never be run unattended
- `/hs:cleanup` — sweep what a disabled or removed skill left behind
- `/hs:deep-swe` — long-horizon autonomous engineering on one repo
- `/hs:ghpm` — drive GitHub issues, projects and milestones from here
