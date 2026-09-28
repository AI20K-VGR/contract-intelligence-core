<!-- generated: plugin-readme -->

# hs

SDLC harness — one hs: plugin holding the full skill catalog (spine SDLC loop hs:plan/cook/test/ship/fix/debug/code-review/review-pr/git/scout/understand/setup/triage plus opt-in groups flow/think/research/create/mem/meta and the domain ports ai/devops/stack/uiux/integrations/extra/viz). Groups are install-time logical labels; skills are selected per-skill at install.

**Default:** always-on (the SDLC spine — installed and enabled on every harness).
**Version:** 6.3.0

## Packaging notes

This plugin is **repo-embedded by design**, not marketplace-cache portable: its skills/agents assume the full harness tree at `harness/` (scripts, data, rules) under the project root, and its 17 fail-closed gate hooks are wired per-project in `.claude/settings.json` rather than in a plugin-level `hooks/hooks.json` — a deliberate two-zone choice that keeps gate policy out of a user-scope manifest an agent could otherwise widen via a project-local write (the F3 hole). It still installs cleanly in global mode (one shared `$HARNESS_BIN_ROOT` binary, many projects); it just is not copy-into-`~/.claude/plugins/cache/` portable today. See `plans/260709-1514-cc-docs-standardization/artifacts/investigation/INV-2-plugin-self-containment.md` for the full trade-off.

`workflows/*.js` (`ping`, `base-fanout-consolidate`, `base-pipeline-verify`) uses Claude Code's plugin-bundled workflow loading (`<plugin>/workflows/*.js` namespaced `hs:`). This loading path is not yet listed in CC's official file-locations table (https://code.claude.com/docs/en/workflows) — treat it as an undocumented-but-observed convention. The `scriptPath` fallback documented in `harness/rules/orchestration-protocol.md` stays mandatory as the hedge if the convention ever changes.

## Skills (130)

| Invoke | Purpose |
|---|---|
| `/hs:advise` | Advise whether and how to build something through a one-question-at-a-time interview that reframes a raw idea, issue, or URL into exact req… |
| `/hs:afk` | Run a plan/PRD in unattended (AFK) mode — preflight readiness, then route to Ralph sandbox or native fallback; loop commits freely in the m… |
| `/hs:agent-browser` | Automate browsers and apps with agent-browser. |
| `/hs:agentize` | Convert a codebase, feature, or module into an AI-agent-friendly npm CLI and/or MCP server. |
| `/hs:ai-artist` | Generate product mockups, marketing assets, brand visuals, and concept art via Nano Banana with 129 curated prompts. |
| `/hs:ai-multimodal` | Analyze images/audio/video with Gemini API (better vision than Claude). |
| `/hs:ask` | Answer technical and architectural questions with expert analysis. |
| `/hs:autonomous-bell` | Use when starting an unattended /goal or AFK loop that should end itself. |
| `/hs:backend-development` | Build backends with Node.js, Python, Go (NestJS, FastAPI, Django). |
| `/hs:bakeoff` | Empirical bake-off — run 2-4 candidate probes on one mechanical metric, pick the winner by numbers or hand to a human when inside the noise… |
| `/hs:better-auth` | Add authentication with Better Auth (TypeScript). |
| `/hs:bootstrap` | Bootstrap a new project from scratch -- clarify requirements, init git, create doc structure, delegate to hs:plan + hs:cook. |
| `/hs:brainstorm` | Brainstorm solutions with honest trade-off analysis — ideation, architecture decisions, technical debate, feasibility exploration. |
| `/hs:chrome-profile` | Target a real Google Chrome profile for browser automation through Chrome DevTools MCP. |
| `/hs:cleanup` | Remove files an over-install left behind, safely: auto-clear pristine version-dropped files, and decide modified ones interactively (keep o… |
| `/hs:cli` | Operate the harness's own CLIs — hs-run (the step engine) and hs-cli (the config door) — without changing state the user did not ask you to… |
| `/hs:code-review` | Review code with technical rigor — bugs, regressions, security. |
| `/hs:coding-agent-orchestration` | Coordinate multiple coding agents and AI developer tools across one workflow — choose which agent plans, implements, reviews, or tests; spl… |
| `/hs:compound` | Compound the harness's own self-knowledge — telemetry lenses + skill-formalization candidates + open backlog + a completeness critic — into… |
| `/hs:context-engineering` | Manage the context budget — check limits, optimize tokens, coordinate subagents, debug context failures. |
| `/hs:contract-test` | Validate a live contract by running the real probe — call the API/CLI and check status, exit code, and payload — then anchor the result as … |
| `/hs:cook` | Execute an approved plan phase by phase — TDD red→green, generate verification/review-decision artifacts, trace every step. |
| `/hs:copywriting` | Conversion copywriting formulas, headline templates, email copy patterns, landing page structures, CTA optimization, and writing style extr… |
| `/hs:critique` | Multi-lens adversarial critique — fan independent lenses at an artifact, consolidate into one ranked verdict. |
| `/hs:cti-expert` | Analyze cyber threat intelligence and OSINT cases. |
| `/hs:databases` | Design schemas, write queries for MongoDB and PostgreSQL. |
| `/hs:debug` | Systematic debugging with root-cause analysis before fixing. |
| `/hs:deep-swe` | Benchmark a coding model on DeepSWE through Pier and OpenRouter. |
| `/hs:deploy` | Deploy projects to any platform with auto-detection. |
| `/hs:design` | Design brand identity, logos, banners, and visual assets. |
| `/hs:devops` | Deploy to Cloudflare (Workers, R2, D1), Docker, GCP (Cloud Run, GKE), Kubernetes (kubectl, Helm). |
| `/hs:discover` | Shape an ambiguous problem into a discovery brief for hs:plan — research + brainstorm chain -> direction summary, trade-offs, open question… |
| `/hs:dispatch` | Decide who owns a piece of work before any of it starts — answer it directly, route it to one skill, or chain several — and set the quality… |
| `/hs:docs` | Analyze codebase and manage project documentation — init, update, summarize. |
| `/hs:docs-build` | Đổ docs (md+frontmatter) + _index (graph+bands.yaml) + _present (presentation) → public/ (showcase HTML giữ theme/hiệu ứng) + dist/ (flat-m… |
| `/hs:docs-scaffold` | Sinh skeleton doc từ template (frontmatter + heading + > TBD) theo required-set capability-driven. |
| `/hs:docs-seeker` | Look up library/framework documentation via llms.txt (context7.com) — API docs, GitHub repo analysis, latest features. |
| `/hs:docs-standardize` | Validate structural docs (frontmatter + graph invariant) → artifact JSON → gate. |
| `/hs:document-skills` | Create, edit, and analyze office files (.docx, .pdf, .pptx, .xlsx). |
| `/hs:drawio` | Use when the user needs polished, editable diagrams (.drawio XML) with 10,000+ branded shapes (AWS/Azure/GCP/Cisco/Kubernetes/UML/ER/networ… |
| `/hs:eli5` | Explain something so the reader actually gets it — the last answer restated plainly, or a topic, error, or piece of code pitched at a named… |
| `/hs:eval-bootstrap` | Bootstrap a full evals/ framework for THIS repo — deterministic scorer + ground truth + optional advisory LLM judge + CI, API-key-free. |
| `/hs:excalidraw` | Generate editable `.excalidraw` JSON files on canvas (architecture, data flow, system design). |
| `/hs:fable-thinking` | Reasoning protocol distilled from Claude Fable 5. |
| `/hs:find-skills` | Locate and route to the correct hs:* skill — analyze intent, query the hs plugin registry, return the exact invoke command. |
| `/hs:finetune` | Route work that must improve a MEASURED result to the skill that owns that outcome, and hand over the bounded-iteration contract. |
| `/hs:fix` | Fix bugs, test failures, and CI/CD failures with an evidence-based workflow. |
| `/hs:folder-context` | Create a compact subfolder CLAUDE.md and linked AGENTS.md for durable local conventions. |
| `/hs:frontend-design` | Create polished frontend interfaces from designs/screenshots/videos. |
| `/hs:frontend-development` | Build React/TypeScript frontends with modern patterns. |
| `/hs:gemini` | Delegate an advisory or coding job to the gemini partner lane (a pure-python print-mode companion) — research, review, adversarial-review, … |
| `/hs:ghpm` | GitHub project management for humans and AI agents. |
| `/hs:git` | Git operations with conventional commits. |
| `/hs:gkg` | Semantic code analysis with GitLab Knowledge Graph. |
| `/hs:goal` | Prepare a built-in /goal run at authoring time — interview the objective into a NEW self-contained goal.md, arm the autonomy bell, scaffold… |
| `/hs:goal-warmup` | Outcome-locked preflight before a long-running autonomous run. |
| `/hs:google-adk-python` | Build AI agents with Google ADK Python. |
| `/hs:graphify` | Build a queryable knowledge graph from code, docs, and media — architecture analysis, cross-file relationship discovery, token-efficient na… |
| `/hs:handoff` | Create a concise, redacted conversation handoff for a fresh agent session. |
| `/hs:harness-creator` | Create new harness primitives (hook, rule, schema, data, script, agent) — not skills. |
| `/hs:html-video` | Create local MP4 videos from HTML/CSS/JS templates with nexu-io/html-video. |
| `/hs:insights` | Surface read-only usage insights from harness telemetry — hot vs never-used skills, workflow chains, gate-block patterns — and propose end-… |
| `/hs:interview-docs` | Extract a user's vision and decisions into durable project documents through a guided interview. |
| `/hs:issue-to-plan` | Turn a GitHub issue into an audited, validated implementation plan and STOP there — read the issue, scout the codebase, run a five-outcome … |
| `/hs:journal` | Write a technical journal entry — record decisions, failures, and lessons learned after each session. |
| `/hs:llms` | Generate llms.txt files from docs or codebase scanning. |
| `/hs:loop` | In-session self-optimization loop — N iterations against a measurable metric, learns from git history, auto-keep/discard changes. |
| `/hs:manual-test` | Run a session-based manual/exploratory test (SBTM charter → session → debrief) and emit anchored, admissible evidence. |
| `/hs:markdown-novel-viewer` | View markdown files in a calm, book-like reader served via HTTP. |
| `/hs:mcp-builder` | Build MCP servers for LLM external-service integration — FastMCP (Python), MCP SDK (Node/TypeScript), tool design, API integration, resourc… |
| `/hs:media-processing` | Process media with FFmpeg (video/audio), ImageMagick (images), RMBG (AI background removal). |
| `/hs:mermaidjs` | Text-based Mermaid.js v11 diagrams INLINE in markdown -- flowchart, sequence, class, ER, state, gantt, architecture -- renders natively on … |
| `/hs:mintlify` | Build and maintain Mintlify documentation sites. |
| `/hs:mobile-development` | Build mobile apps with React Native, Flutter, Swift/SwiftUI, Kotlin/Jetpack Compose. |
| `/hs:partner` | Delegate an advisory or coding job to the ccs partner lane — a second full-Claude session run by a named provider (minimax/ds/km/gm/...), p… |
| `/hs:payment-integration` | Integrate payments with SePay (VietQR), Polar, Stripe, Paddle (MoR subscriptions), Creem.io (licensing). |
| `/hs:plan` | Create a verified implementation plan — research, constraint-scan, phase design, red-team, and validate before cook. |
| `/hs:plans-kanban` | View a file-based kanban board for all plans in plans/ — grouped by status (pending / in-progress / completed), navigate into a plan, check… |
| `/hs:port` | Extract, compare, port, or adapt a feature from a GitHub repository or local repo path into the current project. |
| `/hs:predict` | 5 expert personas independently debate a proposed change before implementation, catching architectural, security, performance, and UX risks… |
| `/hs:preview` | Explain a change or architecture with a diagram when visuals are clearer than prose — flow/architecture, before-after, sequence; output to … |
| `/hs:problem-solving` | Structured unblocking — identify the block type, choose the right technique, reframe before resuming implementation. |
| `/hs:project-management` | Track plan progress, update task status, manage tasks, generate reports, coordinate docs updates. |
| `/hs:project-organization` | Organize files, directories, and content structure in any project. |
| `/hs:prompt` | Write one optimized, ready-to-paste prompt for any AI tool from a rough idea, or fix/adapt/split an existing prompt. |
| `/hs:react-best-practices` | Apply React and Next.js performance optimization patterns from Vercel Engineering. |
| `/hs:release` | Cut a harness release end to end: cut version, push tag, pack dist/ + gh release. |
| `/hs:remember` | Capture the session's real knowledge — decisions made, non-obvious facts learned, user feedback — into the right durable home (DEC ledger, … |
| `/hs:remotion` | Build video content with Remotion in React. |
| `/hs:repomix` | Pack a codebase or subtree into an AI-friendly digest (XML, Markdown, plain, JSON). |
| `/hs:research` | Verified technical research — pose a question, gather multiple sources, verify evidence, synthesize a report. |
| `/hs:retro` | Generate data-driven retrospective reports from git history — velocity, code health, hotspots, plan progress. |
| `/hs:review-pr` | Review a GitHub PR or GitLab MR (forge auto-detected from the git remote) — diff, CI, correctness, security, breaking changes, anti-slop. |
| `/hs:rops` | Run builds, tests, benchmarks, containers or any other heavy command on a remote machine over ssh + rsync (optionally through tmux), from A… |
| `/hs:rule-author` | Author a safe per-repo review-rule override in the layer-b folder docs/standards/ — detect conflicts with the shipped standards, narrow an … |
| `/hs:scenario` | Decompose a feature/code path across 15 dimensions to generate edge cases, risks, and test targets before implementation. |
| `/hs:scout` | Fast codebase exploration using parallel agents — find files, locate code, gather context before implementing or debugging. |
| `/hs:security-scan` | Scan codebase for security issues — hardcoded secrets, dependency CVEs, injection/authz gaps, STRIDE+OWASP. |
| `/hs:sequential-thinking` | Multi-step analysis with revision — decompose complex problems, verify hypotheses, adjust direction mid-stream. |
| `/hs:setup` | Configure this project's harness settings — terminal voice, guard/stage policy, output language — through the validated config CLIs. |
| `/hs:shader` | Write GLSL fragment shaders for procedural graphics. |
| `/hs:shape` | Bridges an approved PO story spec (hs:spec) into dev-task decomposition (serves 1-1/1-n/n-1), roadmap+effort rollup, market-experiment spec… |
| `/hs:ship` | Gated ship pipeline: review PASS → verification PASS → human approval → push/pr. |
| `/hs:shopify` | Build Shopify apps, extensions, and themes with Shopify CLI, GraphQL Admin API, Polaris UI, Liquid, webhooks, billing, and app configuratio… |
| `/hs:show-off` | Create preference-aware self-contained HTML pages to showcase work. |
| `/hs:skill-creator` | Create or update hs:* skills for the harness — SKILL.md, frontmatter, thin-core, references, validate via catalog.py. |
| `/hs:sowat` | Analyze recently implemented work and related issues like a product owner. |
| `/hs:spec` | Interview-driven product spec hierarchy (Vision/BRD/PRD/Epic/Story) with traceability, validation, and visualization for product owners. |
| `/hs:stitch` | AI design generation with Google Stitch. |
| `/hs:sumup` | Summarize completed implementation, failures, workarounds, decisions, behavior, architecture, usage, follow-ups, and next steps. |
| `/hs:tanstack` | Build with TanStack Start (full-stack React framework), TanStack Form (headless form management), and TanStack AI (AI streaming/chat). |
| `/hs:team` | Orchestrate parallel Agent Teams — research, cook, review, debug with multiple independent teammates. |
| `/hs:tech-graph` | Generate publish-grade static technical diagrams (SVG+PNG, 8 styles) — architecture, data flow, sequence, agent/memory, concept map — for e… |
| `/hs:techstack` | Detect the target repo's tech stack (languages, test command, package manager, CI) so the harness adapts instead of assuming pytest. |
| `/hs:test` | Run and validate tests for the current change — unit/integration profiles, concise QA report, 100% pass gate. |
| `/hs:threejs` | Build 3D web experiences with Three.js. |
| `/hs:triage` | Orchestrate the defect lifecycle — reproduce, classify, and gate bugs via hs:scout→hs:debug→hs:fix→hs:test. |
| `/hs:ui-styling` | Style UIs with shadcn/ui components (Radix UI + Tailwind CSS). |
| `/hs:ui-ux` | UI/UX design intelligence for web and mobile: style, color, typography, layout, accessibility, interaction, responsive behavior, forms, cha… |
| `/hs:understand` | Orchestrate codebase comprehension before touching code — chain hs:repomix, hs:scout, hs:context-engineering to build a codebase map. |
| `/hs:use` | Run an install-disabled (off) skill from its stash + report; delegate discovery to hs:find-skills. |
| `/hs:use-mcp` | Discover and execute MCP server tools. |
| `/hs:vibe` | One command takes a GitHub issue or feature request through the whole SDLC spine — worktree, planned gates, cook or fix, code-review, ship … |
| `/hs:voice` | Switch the terminal voice for this session — persona, harshness, explanation depth, no-markdown, or a full persona bundle (a named characte… |
| `/hs:watzup` | Generate short handoff reports from Git branches, remote refs, worktrees, unfinished plans, and roadmap docs. |
| `/hs:web-design-guidelines` | Review UI code for Web Interface Guidelines compliance. |
| `/hs:web-frameworks` | Build with Next.js (App Router, RSC, SSR, ISR), Turborepo monorepos. |
| `/hs:web-testing` | Web testing with Playwright, Vitest, k6. |
| `/hs:workflow-orchestrate` | Design a spawn strategy for a delegated task — pick subagents vs Workflow vs Agent Teams, size and group the fan-out, batch-consolidate, ea… |
| `/hs:worktree` | Create, inspect, and clean up isolated git worktrees. |

Each skill's full contract lives in its `SKILL.md`; load-on-demand detail lives under the skill's `references/`. This index is generated — regenerate with `harness/scripts/generate_plugin_readme.py`.
