<!-- >>> harness onboarding (generated; edits between markers are overwritten on reinstall) >>> -->

## SDLC harness

This repo runs a file-based **SDLC harness** for Claude Code. The engine is either vendored here or shared from one global install, so every path below is written `$E/harness/...` where **`$E` is `"${HARNESS_BIN_ROOT:-.}"`** — spell it that way and it resolves in both layouts; a bare `harness/...` is a dead path under a global install.

- **Probe before you build on a guess** — when a load-bearing assumption CAN be checked (spike a slice, run the real tool, read the source), do that FIRST, before designing on top of it. A claim you have not exercised for real is `[ASSUMED]` (unchecked training knowledge is `[PRIOR]`), never OBSERVED: label it honestly and gate it behind one real run — never report "works" from reasoning alone.
- **Skills** — drive the workflow with `/hs:<name>` (`/hs:plan`, `/hs:cook`, `/hs:test`, `/hs:ship`, `/hs:review-pr`). `/hs:find-skills` lists them.
- **Off skills** — a fresh install ships DEFAULT-OFF; the rest are stashed under `$E/harness/plugins/hs/disabled-skills/<name>/` and `/hs:find-skills --list` tags them `[OFF]`. An off skill cannot be run: read its stash SKILL.md, or `hs-cli skills --on <name>`.
- **`hs-run`** (`$E/harness/bin/`) — the step engine: `hs-run <domain> next` returns a JSON envelope (`state`, `next_action`, `artifacts`, `refs`) and an exit rung — `0` done, `10` needs the model, `11` step remains, `2` broken. Read it; do not re-derive the step.
- **`hs-cli`** (same dir) — config/admin: `skills --on/--off` (restart to apply), `components`, `migrate`, `trust`.
- **Both need their roots** — `HARNESS_BIN_ROOT` (engine) and `HARNESS_DATA_ROOT` (data, default `.harness/`). Called by bare path without them, the engine walks UP for `plans/` and answers for the WRONG project.
- **Rules** — shared conventions load on demand from `$E/harness/rules/` (routing in this file's project section, or ask a skill).
- **Hooks** — gates/telemetry wired in `.claude/settings.json`; knobs in `$E/harness/data/*.yaml`. `/hs:setup` configures voice, policy, output.

<!-- <<< harness <<< -->
