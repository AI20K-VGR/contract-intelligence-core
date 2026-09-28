# Restart reminder — say this out loud

Guard and stage policy are **env-bound** (`HARNESS_GUARD_POLICY` / `HARNESS_STAGE_POLICY`): the pre-push hook scrubs every `HARNESS_*` before judging a push, so these must NOT be live-discovered — they only take effect on a **new session**. After changing guard or stage, tell the user plainly:

> Guard/stage changed — restart the session (or open a new terminal) for it to take effect. Voice,
> roster, and output language are live and need no restart.

**`/clear` vs full restart — offer this as the LAST step of setup (don't skip it).** They are not the same thing:

- **`/clear`** wipes the conversation context and re-fires the `SessionStart` hooks (`source: "clear"`), so the harness's injected voice/rules/active-settings block is re-built fresh. Use it after a long setup to (a) drop the now-stale setup transcript and (b) make the in-context voice block match the values you just wrote (live knobs already took effect for the hooks; `/clear` only refreshes
  the *injected reminder* a reader sees). `/clear` does NOT restart the process.
- **Full restart** (`exit` then `claude`, or a new terminal) is REQUIRED for env-bound changes — guard, stage, solo/team posture — and for component **plugin** enable/disable, because Claude Code binds settings.json `env` and indexes plugin skills at process start. `/clear` re-runs SessionStart but does NOT re-bind the process environment, so it is NOT enough for these. (A config FILE that an
  existing env var already points to is re-read live — that part needs neither.)

Say it plainly at the end: *"Voice/output/roster/cook/critique are live now. Run `/clear` to drop this setup conversation and refresh the injected voice block. If you changed guard, stage, posture, or a plugin component, do a full restart (`exit` + `claude`) — `/clear` alone won't pick those up."*

The same restart applies to a skill re-enabled via `hs-cli skills --enable <skill>` (post-collapse every skill ships in the one `hs` plugin and disable is dir-omission, not a per-plugin toggle): Claude Code indexes the plugin's skills at session start, so a restored skill's `/hs:<skill>` command only appears after a restart.

The `setup_nudge` SessionStart hook also surfaces this automatically when settings.json wires those env vars but the running session does not match them.
