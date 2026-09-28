---
name: hs:setup
injectable: false
description: "Configure this project's harness settings — terminal voice, guard/stage policy, output language — through the validated config CLIs. Use when onboarding a fresh install or changing a configuration decision. Reads config-reference.md and reminds about the session-restart need for env-bound guard/stage changes."
allowed-tools: [Bash, Read, Grep, Glob]
argument-hint: "[full | short | show | none] [--global]"
metadata:
  compliance-tier: workflow
---

# hs:setup — project posture configuration

Walks the user through the harness's tunable posture, writing choices via the validated config CLIs (never hand-edit YAML in-session). The authoritative index of every knob, its file, default, and env override is `docs/harness/config-reference.md` — read it before presenting options so the defaults you quote are correct.

For onboarding (fresh install) or later changes; re-invoking re-shows the menu.

**Where you stand**: run `hs-run setup next`. It reads what disk can answer about this
project's posture, names the state, and carries the `rules` and `references` THAT state
needs. Read what the envelope names, and only that. But satisfying the envelope is **not
enough** to have configured anything: it routes DOCUMENTS, while the config file on disk
is what a setup step changes — write it through the CLI that owns it.

## Scope — localized config is BIN-GLOBAL under a shared install (read FIRST)

**Self-host (bin == project — a plain dev checkout, `HARNESS_BIN_ROOT` unset):** writes land in your one repo, so "project posture" is exact — rest of this caveat is moot.

**Global / courier install (`HARNESS_BIN_ROOT` points at a shared engine):** the localized-config knobs — terminal voice, guard/stage policy, output language — are **BIN-GLOBAL by design**, NOT per-project: a knob you write here reaches EVERY project that shares this binary.
Before writing one, SAY it is bin-global and get explicit intent. Full reach, the per-project `HARNESS_XXX` env escape hatch, and the hardened-read-only-bin case: **see `references/global-install-scope.md`**.

## STOP — `--global` needs re-confirmation before touching shared-bin engine state

`--global` governs the shared ENGINE-BINARY state (install / repoint / recipient bootstrap) — separate from the config-file scope above; setup itself never installs/repoints the engine.
If (and only if) the user passes `--global`, STOP and re-confirm with an `AskUserQuestion` before touching any shared-bin engine state — treat a missing re-confirmation as a hard stop. Full detail: **see `references/global-install-scope.md`**.

## Where to start

Run `hs-run setup next`. It names the first condition that is not yet satisfied — a missing dependency, a pre-split key in the live config, an untrusted repo — and routes what that condition needs. When it answers `configured`, the mechanical part is done and everything below is the user's to choose.

## Layer-0 — archetype onboarding (run this first on a fresh install)

Present the 10 archetypes from `"${HARNESS_BIN_ROOT:-.}"/harness/data/voice-presets.yaml`, apply the chosen one, then proceed to Layer-0.6 (or Layer-1 on "fine-tune"). The mandatory "adjust anything?" refinement step + the list/apply commands: **see `references/archetype-onboarding.md`**.

## Layer-0.6 — pick a character (persona bundle → delegate to `/hs:voice`)

A **persona bundle** gives the session a named CHARACTER — opt-in, OFF by default. On a fresh onboard OFFER it, then **delegate to `/hs:voice`** (it owns the character + RELATIONSHIP interview; do NOT re-implement here).
Order matters — run AFTER the preset, since a preset CLEARS an active bundle. Bin-global like every localized knob above: it sets the character for EVERY project of this user, so say so first.

## Layer-0.5 — personal-first is the default

The harness is **personal-first**: local never blocks the HUMAN at commit/push/ship — it generates receipts (plan-graph / verification / review-decision) and traces; quality is enforced at REMOTE CI. The AGENT cage stays (guard `enforcement=block` + the safety floors). There is no solo-vs-team posture question and no reviewer roster to configure.

## Layer-0.7 — skill onboarding (fresh default-off install)

A fresh install ships **default-off** (49 ON, the other 80 stashed, reachable via `/hs:use`). Surface the split, offer to re-enable whole clusters (`AskUserQuestion` over `skill-defaults.yaml` `clusters:` → `hs_cli.py skills --enable <csv>`), never auto-enable.
Protocol: `references/skill-onboarding.md`.

## Preamble — pick the depth (present in the project's output language)

Present these four options first and wait for the choice:

1. **Full** — walk every group (voice, guard/stage, roster, output language, DoD/test-policy) with current value + default, running the per-step coherence lint after each group and the consolidated coherence pass at the end (see "Coherence lint").
2. **Short** — only the three that matter most on day one: review-policy profile (default/thorough/ship-grade), guard preset, output language.
3. **Show meanings + defaults** — read `config-reference.md` back to the user, change nothing.
4. **None** — exit without changes.

## The groups and their CLIs

Quote the CURRENT resolved value before asking for a new one (run the read form, no `--set`).

**Path form (courier):** the `harness/scripts/*.py` tools and `harness/data/*.yaml` files below are named by their engine-relative path. Under a courier/global install the engine is NOT at `./harness`, so run/read them through the env:
`python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/<tool>.py …` (a bare `harness/…` resolves from the repo CWD and misses; the `${…:-.}` fallback keeps a self-host clone running from `.`).

| Group | Knobs | Tool | Takes effect |
|---|---|---|---|
| Terminal voice | persona, voice_level, terminal_voice_level, no_markdown, interview_rigor, action_prompting | delegate to `/hs:voice` — it owns the whole voice surface | **live** — no restart |
| Output prose | language (en\|vi), humanize, audience (off\|0–5), code_style (off\|0–5) | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --set k=v` | live — read per invocation |
| Cook execution | parallel (bool), parallel_max (int>0) | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/cook_config.py --set k=v` | live — read per cook run (chain: `--parallel` flag > `HARNESS_COOK_PARALLEL` > this file) |
| Critique | mode (advisory\|gate) | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/critique_config.py --set mode=v` | live — read per critique run; **mode=gate writes a verdict but does NOT enforce** until a stage lists `critique-consensus` in its `requires:` |
| Guard policy | preset (strict\|balanced\|lenient), per-guard off\|warn\|block | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/guard_config.py set-preset <p>` / `set <guard> <mode>` | **restart** (env-bound) |
| Stage policy | per-stage artifact requirements / hard | edit `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` (hand edit; git-visible) | **restart** (env-bound) |
| Hook components | runtime on/off for hook-backed features (rbac, decision-capture, docs-ssot, …) | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/component_config.py --set <name>=enabled\|disabled` (read: `show` / `list`) | **live** (hook self-skips on the flag) |
| Gemini partner lane | master, mode, write, stop_review_gate, `route_all_injection`; purposes→tier; `loop` {max_rounds, default_mode} | hand-edit `"${HARNESS_BIN_ROOT:-.}"/harness/data/gemini-partner.yaml` (dev override `$HARNESS_GEMINI_PARTNER`) | **restart** (env-bound) |

**Gemini partner lane (opt-in, ships OFF).** Inert while `master: off` — leave it unless the user wants a second-engine pass. Blast-radius axes (`write: sandbox_write`, `route_all_injection: on`) and the one-time `injectable` allowlist bootstrap: **see `references/gemini-lane-onboarding.md`**.

`code_style` (in output.yaml, not the voice file) is the one output knob **NOT scope-fenced** — shapes generated CODE only, not chat/report prose (that is `audience`); profiles in `"${HARNESS_BIN_ROOT:-.}"/harness/data/output-styles/`. Treat a non-off value as a deliberate save.

**Advisory nudges / gates — discover live, do NOT trust a static list.** Toggleable nudge/gate hooks span THREE control planes (class-default · `harness-hooks.yaml` `enabled` · guard-policy mode); a repo's `settings.json` can be stale so a hook shipped on disk may not be wired.
READ the live state before surfacing nudges in Full mode; flip a nudge by hand in `harness-hooks.yaml` (not `--set`). Method, control model, drift checks, and the goal-cycle nudge convention: **see `references/hook-discovery.md`**.

`component_config.py` governs **hook components** only — features backed by a hook self-skip on an `enabled:false` flag (live, no restart). It does NOT add or remove SKILLS. Post-collapse every skill ships in the one `hs` plugin; a skill is on by being present on disk and off by install-omission, and is toggled after install with `hs-cli skills --enable/--disable <skill>` (restart to re-index
— see the restart reminder). So "turn on viz/uiux/devops" is a **skill** action (`hs-cli skills` / install selection), NOT a component toggle — do not route it through `component_config`.

Read forms (no write): `output_config.py --file <path>`, `guard_config.py show`; the voice side is `/hs:voice`.

## Restart reminder — say this out loud

Guard and stage policy are **env-bound**, so they only take effect on a **new session**; voice and output language are live. Full details, the `/clear` vs full-restart distinction, and the plugin-re-enable case: **see `references/restart-reminder.md`**. After changing guard or stage, say out loud:

> Guard/stage changed — restart the session (or open a new terminal) for it to take effect.

## Trust this repo for shell-detector auto-fire

A standards rule may carry a **shell detector** — an arbitrary command the review-time runner executes. `/hs:setup` is the deliberate "this repo is mine" moment, so it is the one place that grants trust.

Run the trust step in the open (never silently):

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/hs_cli.py trust "$(pwd)"
```

Mention how to inspect or undo it: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/hs_cli.py trust --list`.

## Boundaries

- Always write through the CLIs (`*_config.py --set`, `guard_config.py`) so validation runs and the change is a clean git diff. Do not hand-edit the YAML from inside the session.
- An unknown key or out-of-range value exits non-zero and writes nothing — report the failure, do not retry blindly.
- Setting `voice_level` 6–9 is a deliberate save; there is no second prompt. The universal-harm floor holds at every level regardless.
- This skill changes CONFIG, never code or evidence. Gate decisions still follow the written files.

## Review and test gate config (4 tiers — surface during Full or when asked)

The MAIN tier (review-policy, code-review, test-policy/DoD) affects the ship gate — surface it on day one. Full tier tables, the posture-aware DoD walk, and the tier-1/tier-2 override-surface decision: **see `references/gate-config.md`**.
Write scope is a deny-list: a `workflow-subagent` edits project source out of the box (no lane setup), refused only the hard floor.

## Coherence lint — warn on a config that fights itself (per-step + final)

After each group AND once at the end (Full mode), check the written config for internal incoherence or a mismatch to who the user is — too strict/loose for solo/team, prose register vs code/voice expertise split, voice asking for challenge but rigor set light. Warn and ASK, never silently correct; user decisions hold. Full check list + framing: **see `references/coherence-lint.md`**.

## Related skills

- `hs:techstack`: read-only stack detection — run first on a non-Python repo so posture matches the real test command.
- `hs:rule-author`: for authoring new compliance standards or shell-detector rules — invoked from setup's TIER 3 SHOW step when the user wants to change `standards.yaml`.
