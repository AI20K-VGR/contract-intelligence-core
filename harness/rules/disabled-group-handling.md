# Disabled-skill handling

Load when a skill reference points at a skill that may be install-disabled (omitted).

After the 2.0.0 collapse every skill lives in one `hs` plugin. A fresh
install picks skills per-skill: the 13-skill spine is always present, and any other
skill can be OMITTED at install — its dir is simply not copied, which is the only
disable that works for plugin skills on this Claude Code. The former themed/ck-port
groups are just install-time labels now, not separate plugins.

Because skills still reference each other (the SDLC handoffs are a contract), a
reference like `hs:critique` or `hs:remember` can name a skill that was omitted at
install. **This is not a broken reference.** The handoff still stands — never delete
or rewrite it to make a green check.

## First: discover what is off

Skills can be off without you knowing which. To see the off catalog:

```bash
python3 harness/scripts/disabled_skills.py --list      # names + descriptions
/hs:find-skills --list                                 # live + off (tagged [OFF])
```

`hs:find-skills` owns off-skill discovery and routing; it tags every off match
`[OFF — gọi: /hs:use <name>]`.

## When you hit a reference to a disabled (omitted) skill

Three ways forward — pick by context:

1. **Run it through the proxy** (preferred for a one-off — no state change):
   `/hs:use <skill>` loads the off skill (and its off deps) from the stash and performs
   its prose exactly, without re-enabling it. This is the sanctioned front door to an off
   skill; do NOT call the raw `/hs:<skill>` (it is blocked/absent for an off skill).

2. **Re-enable the skill** (preferred when it will be used repeatedly):
   `hs-cli skills --enable <skill>` (e.g. `--enable critique`). The dir is restored
   from the disabled stash together with its declared deps; to add several at once,
   re-run the installer with `--skills` / `--skill-groups`.

3. **Read the skill inline** (a manual fallback): open the stash copy
   `harness/plugins/hs/disabled-skills/<skill>/SKILL.md` (an omitted skill's dir lives in
   the stash, NOT under `skills/`) and perform its steps directly. The skill's instructions
   are plain files — an omitted skill only means its dir was not installed, not that the
   knowledge is gone (the source tree still ships it).

## What never to do

- Do **not** drop the cross-skill reference or replace it with prose to dodge a
  resolver check — that erases the handoff contract.
- Do **not** treat a disabled-skill reference as a dangling/typo'd reference in
  review or migration tooling.

## The nudge

`harness/hooks/disabled_ref_nudge.py` (nudge class, advisory, fail-open) watches the
session context for `hs:<skill>` references whose skill was omitted at install (read
from `harness/state/install-omitted-skills.json`) and prints a one-line reminder
pointing at the two options above. It never blocks; a reference to an omitted skill
is a normal, expected state, not an error.
