# codex install — what is here and what is not

7 registration group(s) carried over; 9 did not.

## Tools that execute here without firing a hook

Nothing below can be gated on this runtime: it runs and no hook event is raised for it. This is not something the harness can close — there is no event to register on.

- `write_stdin` — writes into a session that `exec_command` opened with `tty: true`, and raises no hook event at all. Measured with a wildcard PreToolUse+PostToolUse registration: the string `rm -rf /tmp/probe-canary` sent through `exec_command` reached the hook 1/1 times; the SAME string typed into a live `bash` session through `write_stdin` reached it 0/1 times, the only hook payload of the run being `{"command": "bash"}`. So one `exec_command` with `tty: true` puts every later command past every gate registered on Bash.

Consequence for the gates that DID survive here (`bash_safety_guard`, `floor_bash_guard`, `gate_stage`, `plannotator_wrapper_guard`, `protected_ref_guard`, `simplify_gate`): each one reads the tool call it is registered on, so anything reaching the runtime through the tools above passes them unseen. Treat their coverage as conditional on the model not using those tools, which is an assumption, not an enforcement.

## Before this install does anything

Writing the hooks file does not install the hooks. On this runtime a hook arrives untrusted, pinned to a hash of its own content, and does not run until it is trusted — an edit to the file un-trusts it again. Grant trust through the runtime's own interactive startup review, and treat the install as unfinished until you have. The only non-interactive override is the per-invocation flag --dangerously-bypass-hook-trust; the config key `bypass_hook_trust` parses and does nothing.

## Project instructions

`AGENTS.md` points at `CLAUDE.md` rather than copying it, so the two cannot drift apart.

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

- codex: compliance gate `privacy_read_guard` (group PreToolUse:Read|NotebookRead) would register and never fire on codex — every matcher atom is gone (Read (not on this runtime), NotebookRead (not on this runtime)). A gate that cannot fire reads exactly like one that protects.
- codex: compliance gate `write_guard` (group PreToolUse:Write|Edit|MultiEdit) would register and never fire on codex — every matcher atom is gone (Write (not on this runtime), Edit (not on this runtime), MultiEdit (not on this runtime)). A gate that cannot fire reads exactly like one that protects.
- codex: compliance gate `model_guard` (group PreToolUse:Agent|Task) would register and never fire on codex — every matcher atom is gone (Agent (never measured on this runtime), Task (never measured on this runtime)). A gate that cannot fire reads exactly like one that protects.
- codex: compliance gate `spawn_provenance_workflow_guard` (group PreToolUse:Workflow) would register and never fire on codex — every matcher atom is gone (Workflow (never measured on this runtime)). A gate that cannot fire reads exactly like one that protects.
- codex: compliance gate `disabled_skill_router` (group PreToolUse:Skill) would register and never fire on codex — every matcher atom is gone (Skill (never measured on this runtime)). A gate that cannot fire reads exactly like one that protects.

## Every registration that did not carry over

- `PostToolUse:Write|Edit|MultiEdit` — no tool this group matches on exists on the target (Write (not on this runtime), Edit (not on this runtime), MultiEdit (not on this runtime)), so the registration would be inert
- `UserPromptExpansion` — the target declares no UserPromptExpansion event under any name it declares, so nothing registered on it can run there
- `Notification` — the target declares no Notification event under any name it declares, so nothing registered on it can run there
- `PreToolUse:Write` — no tool this group matches on exists on the target (Write (not on this runtime)), so the registration would be inert
- `PreToolUse:Read|NotebookRead` — no tool this group matches on exists on the target (Read (not on this runtime), NotebookRead (not on this runtime)), so the registration would be inert
- `PreToolUse:Write|Edit|MultiEdit` — no tool this group matches on exists on the target (Write (not on this runtime), Edit (not on this runtime), MultiEdit (not on this runtime)), so the registration would be inert
- `PreToolUse:Agent|Task` — no tool this group matches on exists on the target (Agent (never measured on this runtime), Task (never measured on this runtime)), so the registration would be inert
- `PreToolUse:Workflow` — no tool this group matches on exists on the target (Workflow (never measured on this runtime)), so the registration would be inert
- `PreToolUse:Skill` — no tool this group matches on exists on the target (Skill (never measured on this runtime)), so the registration would be inert

## Where this runtime reads each kind

Paths are the runtime's own, measured from its emitted tree. Scope: **project**.

- hook registration — `.codex/hooks.json`
- skills — `.codex/skills`
- agent roles — `.codex/agents`
- project instructions — `AGENTS.md`

Reads none of: rules, skills (second copy — this runtime reads both). Nothing of that kind is in this tree, because a file written where nothing loads it reads as installed. Not dropped either: the harness tree the install copies carries every one of them under `harness/`, and the skill bodies point at them there. A second copy here would be a copy that drifts from the one the gates read.

## Events this runtime raises that nothing here uses

Measured on the runtime, not inferred: it also raises `PreCompact`, `PermissionRequest`, `PostCompact` and `SessionEnd`. The harness registers on none of them, so nothing in this install runs at those points. This is unused capability, not a limit — a later registration has somewhere to go.

## What was measured about this runtime

Each line was observed on this runtime's own emitted tree, not inferred from another one.

- **hook trust** — Writing the hooks file does not install the hooks. On this runtime a hook arrives untrusted, pinned to a hash of its own content, and does not run until it is trusted — an edit to the file un-trusts it again. Grant trust through the runtime's own interactive startup review, and treat the install as unfinished until you have. The only non-interactive override is the per-invocation flag --dangerously-bypass-hook-trust; the config key `bypass_hook_trust` parses and does nothing.
