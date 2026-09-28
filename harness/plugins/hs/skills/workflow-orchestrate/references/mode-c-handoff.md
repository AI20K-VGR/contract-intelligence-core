# Mode C (agent teams) — experimental gate, live API, execution hand-off

Backing for the two Mode-C touchpoints in SKILL.md: the experimental-flag gate (Step 1's "Three
modes" note) and the execution hand-off (Step 4). Decision RULES for when C applies at all live
in `references/strategy-decision.md` — this drawer covers what happens once C is picked.

## Experimental gate + live API

Agent Teams is CLI-only and **experimental** — gated by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
(or `--agent-teams`) plus a server statsig — so C is **never auto-launched**: the script always
returns `exec.gate = confirm_required` for it. The live team API is `Agent(name=...)` +
`SendMessage` over one implicit team; **`TeamCreate` / `TeamDelete` were removed in CC
v2.1.178** — never emit them.

## Execution hand-off (Step 4)

Hand off execution to the Agent Teams skill (see SKILL.md **See also**), passing it THIS plan
JSON — do not re-derive the fan-out. Each `groups[].key` becomes one named teammate +
`TaskCreate`; `report_dir` is the team's shared noticeboard; `exec.gate`/`experimental`/
`requires_flag` carry the gate state (the team skill computes per-slice globs). Preflight
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, spawn one worktree-isolated `Agent(name=...)` per
slice, coordinate via `SendMessage` + the task board. Always `confirm_required`; if the flag is
absent, tell the user and re-pick A/B — never silently degrade. The lead then runs the team
skill's coordination loop.
