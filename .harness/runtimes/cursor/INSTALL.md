# cursor install — what is here and what is not

12 registration group(s) carried over; 4 did not.

## Before this install does anything

Writing the hooks file does not install the hooks. Check how this runtime admits a hook — several require an explicit grant before one runs — and treat the install as unfinished until you have.

## Skills shipped with this install

Loaded verbatim by the runtime and listed to the model under the name each one declares:

- `advise`
- `afk`
- `bakeoff`
- `brainstorm`
- `cleanup`
- `cli`
- `code-review`
- `context-engineering`
- `cook`
- `critique`
- `debug`
- `discover`
- `docs`
- `eli5`
- `eval-bootstrap`
- `fable-thinking`
- `find-skills`
- `fix`
- `gemini`
- `git`
- `goal-warmup`
- `handoff`
- `loop`
- `manual-test`
- `partner`
- `plan`
- `predict`
- `problem-solving`
- `prompt`
- `remember`
- `research`
- `review-pr`
- `rule-author`
- `scenario`
- `scout`
- `security-scan`
- `sequential-thinking`
- `setup`
- `ship`
- `sowat`
- `sumup`
- `techstack`
- `test`
- `triage`
- `understand`
- `use`
- `voice`
- `workflow-orchestrate`
- `worktree`

## Agent roles shipped — and the cage that did not come with them

Each agent's prose, description and effort bound travel. The per-agent TOOL allowlist does not: this runtime's role schema has no field for it, so a role here may use any tool. What follows is what each agent is restricted to on its home runtime and is NOT restricted to here.

- `advisor` — tools NOT enforced here: Glob, Grep, Read, Write, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task
- `brainstormer` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, Task, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `code-reviewer` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, Task, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `code-simplifier` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task
- `critique-consolidator` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, Task, TaskGet, TaskUpdate, TaskList, SendMessage
- `debugger` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `decision-reconciler` — tools NOT enforced here: Glob, Grep, Read, Bash, Task, Edit
- `developer` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `docs-manager` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `escalation-consultant` — tools NOT enforced here: Glob, Grep, Read, Bash, WebFetch, WebSearch, Write, Task
- `gemini-relayer` — tools NOT enforced here: Bash, Read
- `git-manager` — tools NOT enforced here: Glob, Grep, Read, Bash, Task, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `grid-axis-selector` — tools NOT enforced here: Glob, Grep, Read, Write, TaskGet, TaskUpdate, TaskList, SendMessage
- `grid-filler` — tools NOT enforced here: Glob, Grep, Read, Write, TaskGet, TaskUpdate, TaskList, SendMessage
- `independent-revalidator` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `journal-writer` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `market-fit-critic` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, Task, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `partner-relayer` — tools NOT enforced here: Bash, Read
- `planner` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `product-value-critic` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, Task, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `project-manager` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, WebFetch, WebSearch, Task, TaskCreate, TaskGet, TaskUpdate, TaskList, TodoWrite, SendMessage, Skill
- `red-teamer` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `researcher` — tools NOT enforced here: Glob, Grep, Read, Write, Edit, Bash, WebFetch, WebSearch, Task, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Skill
- `spec-craft-critic` — tools NOT enforced here: Glob, Grep, Read, Bash
- `spec-tech-critic` — tools NOT enforced here: Glob, Grep, Read, Bash
- `tester` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `ui-ux-designer` — tools NOT enforced here: Glob, Grep, Read, Edit, MultiEdit, Write, NotebookEdit, Bash, WebFetch, WebSearch, TaskCreate, TaskGet, TaskUpdate, TaskList, SendMessage, Task, Skill
- `workflow-orchestrator` — tools NOT enforced here: Glob, Grep, Read, Bash, TaskGet, TaskList, SendMessage

## Gates that are NOT protecting you here

Each of these is registered in the harness as a blocking gate and has no counterpart on this runtime. They are absent from the install rather than present and inert, because a gate that cannot fire is indistinguishable from one that protects.

- cursor: compliance gate `spawn_provenance_workflow_guard` (group PreToolUse:Workflow) would register and never fire on cursor — every matcher atom is gone (Workflow (not on this runtime)). A gate that cannot fire reads exactly like one that protects.
- cursor: compliance gate `disabled_skill_router` (group PreToolUse:Skill) would register and never fire on cursor — every matcher atom is gone (Skill (not on this runtime)). A gate that cannot fire reads exactly like one that protects.

## Every registration that did not carry over

- `UserPromptExpansion` — the target declares no userPromptExpansion event under any name it declares, so nothing registered on it can run there
- `Notification` — the target declares no notification event under any name it declares, so nothing registered on it can run there
- `PreToolUse:Workflow` — no tool this group matches on exists on the target (Workflow (not on this runtime)), so the registration would be inert
- `PreToolUse:Skill` — no tool this group matches on exists on the target (Skill (not on this runtime)), so the registration would be inert

## Where this runtime reads each kind

Paths are the runtime's own, measured from its emitted tree. Scope: **project**.

- hook registration — `.cursor/hooks.json`
- skills — `.cursor/skills`
- agent roles — `.cursor/agents`
- rules — `.cursor/rules`

Reads none of: project instructions, skills (second copy — this runtime reads both). Nothing of that kind is in this tree, because a file written where nothing loads it reads as installed. Not dropped either: the harness tree the install copies carries every one of them under `harness/`, and the skill bodies point at them there. A second copy here would be a copy that drifts from the one the gates read.

## Events this runtime raises that nothing here uses

Measured on the runtime, not inferred: it also raises `preCompact`. The harness registers on none of them, so nothing in this install runs at those points. This is unused capability, not a limit — a later registration has somewhere to go.

## What was measured about this runtime

Each line was observed on this runtime's own emitted tree, not inferred from another one.

- **no payload shim** — The emitted hook scripts read `data.tool_input` / `data.tool_name` — the Claude snake_case vocabulary — and nothing in the emitted tree translates into it. Either the runtime already speaks that shape, or every gate fail-opens silently. NOT MEASURED against a live runtime; do not emit a compliance gate here until it is.
- **rule attachment unverified** — This runtime's rule format documents a frontmatter that decides WHEN a rule attaches — always, on a glob, or on the model asking for it. Measured: the upstream emitter writes none, on any of its eight rule files, and ours writes none either, so the two exports stand or fall together. What none of that settles is whether a rule with no frontmatter attaches at all, which could not be probed without the runtime. Read the rules as material a human can point the model at, not as guidance that is loading itself.
- **statusline not carried** — The upstream ships a statusline renderer into this runtime — measured, 23 JavaScript files across the three targets it does that for. Ours is not a renderer: it is a configuration file for a third-party statusline tool that only the home runtime runs. Carrying it here would mean writing a renderer in this runtime's own language and keeping it, which is the same cost as the hook bridge and buys a status bar. Nothing about the gates depends on it.
