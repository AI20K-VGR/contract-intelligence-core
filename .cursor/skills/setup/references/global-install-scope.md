# Global/courier install — localized config is BIN-GLOBAL, `--global` is a separate STOP

## Localized config under a shared engine

**Global / courier install (`HARNESS_BIN_ROOT` points at a shared engine):** the localized-config knobs — terminal voice, guard/stage policy, output language — are **BIN-GLOBAL by design**, NOT per-project.
Their CLIs resolve the target file relative to the shared engine (`$HARNESS_BIN_ROOT/harness/data/…`, off `__file__`), so a knob you write here reaches **EVERY project that shares this binary** — not confined to this repo's `.harness/` (only runtime STATE + trace are per-project).
Deliberate: guard policy is the write floor, so a per-project writeable override would let it be widened with a Bash-write. Consequences:

- Before writing ANY localized-config knob under a shared bin, SAY it is bin-global — the change hits every co-tenant project, not just this one — and get explicit intent (the same care `--global` demands).
- To scope ONE knob to just this project, do NOT write the shared file: wire an explicit `HARNESS_XXX` env override (`HARNESS_TERMINAL_VOICE`, `HARNESS_GUARD_POLICY`, `HARNESS_OUTPUT`, …) pointing at a project-local file in this repo's `.claude/settings.json` (NOT `settings.local.json` — CC clobbers that file on every permission approval; both are gitignored, so settings.json is equally private).
- If the shared bin was hardened read-only (`--harden-bin`), the CLIs CANNOT write it (write_guard blocks the `$HARNESS_BIN_ROOT/**` zone) — the per-project `HARNESS_XXX` override is then the ONLY way to change posture.

## `--global` — shared engine-binary state (a separate scope from the config knobs above)

`--global` governs the shared ENGINE-BINARY state (install / repoint / recipient bootstrap), separate from the config-file scope above. setup never installs or repoints the engine itself — it assumes phase-7 recipient bootstrap already placed the shared binary.

If (and only if) the user passes `--global`, STOP and re-confirm with an `AskUserQuestion` before touching any shared-bin engine state: state plainly that it affects EVERY project sharing this binary, show what would change, and proceed only on an explicit yes. Treat a missing re-confirmation as a hard stop.
