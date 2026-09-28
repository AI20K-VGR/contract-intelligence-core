---
name: hs:release
injectable: false
description: "Cut a harness release end to end: cut version, push tag, pack dist/ + gh release. Owner-only build step; pauses for confirmation before every outward-facing action. Use when cutting a new harness version."
allowed-tools: [Bash, Read, AskUserQuestion]
argument-hint: "[X.Y.Z] [--apply] [--yes]"
disable-model-invocation: true
metadata:
  compliance-tier: workflow
---

# hs:release — cut a harness release (interactive)

Human-facing wrapper over `release/release_orchestrator.py` (the engine, the single source of the 3-step sequence). This skill is the **owner's door**; the auto path (`/goal`) calls the script directly with `--yes`. The engine lives in `release/` (build-toolkit) and never ships in the bundle.

The engine is idempotent — a re-run probes "already done for this version?" and skips. Your job: drive it step by step, insert the human confirm at the two outward-facing beats.

## The 3 steps (hard order, the engine enforces it)

Before step 1, `preflight()` hard-gates the cut. Besides green CI + skill structure + clean tree + gh auth, it also **refuses the cut while the Decision Register has unreconciled drift** (new DECs / flips since the last reconcile marker).
Clear it by running the `@decision-reconciler` agent, then `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_reconcile.py --mark`, and re-run. It further
**refuses the cut while structural docs fail** — it runs the `hs:docs-standardize` gate (`docs_gate.py --fresh`) so a missing-frontmatter / broken-graph doc under `docs/` aborts before publish. Release VERIFIES doc structure; it never regenerates content — refresh stale docs as a separate reviewed commit, then cut. Both gates are release-local (owner-only) — they never touch a normal
ship/deploy.

1. **cut** — `release.py` locks CHANGELOG `[Unreleased]→[X.Y.Z]`, bumps release.json
   + plugin/marketplace versions, regenerates the plugin index READMEs (so the
   shipped README's version + skill list never freeze), rebuilds manifest AFTER those edits, writes a LOCAL tag.
2. **push tag** *(outward)* — push harness HEAD + tag to origin with `--no-verify` (owner self-bypasses the pre-push gate). The push to `main` also triggers CI `sync-showcase.yml`, which auto-publishes the committed `public/` to the release repo — showcase is no longer a release step.
3. **pack + release** *(outward)* — pack `dist/` (tarball + `.sha256` + install.sh), extract release notes, `gh release create`.

## How to run

Always start with the dry-run checklist — it shows posture + per-step idempotency state, writes nothing:

```bash
python3 release/release_orchestrator.py --version X.Y.Z          # dry-run
```

Then drive the apply path. **Before step 2 and step 3** (the outward beats), ask the operator with AskUserQuestion — 3 options, non-technical Vietnamese, recommended first:

- **Review trực tiếp** (xem checklist/diff trước khi đẩy) — recommended
- **Approve** (đẩy luôn)
- **Reject** (dừng, không đẩy)

On Approve, continue the engine with `--yes`:

```bash
python3 release/release_orchestrator.py --version X.Y.Z --apply --yes
```

Without `--yes` the engine **stops at the confirm gate** (exit `NEEDS_CONFIRM`) before any push — a backstop if the skill forgets to ask.

## Owner-only outward steps

Personal-first: releases are owner-only — the engine runs outward commands itself (push, `gh release create`) behind the confirm gate. Never call this bypassing review: the confirm gate IS the review surface for an owner-only step.

## If a step fails mid-way (rerun playbook)

Re-run the same `--version`. The engine distinguishes a **local cut** (CHANGELOG section + local tag + release.json) from a **remote tag** (`git ls-remote`): a push that died after the cut re-pushes instead of re-cutting (which would raise `already exists`). Never roll back a tag. Details: `references/resumable.md`.

## References (load on demand)

| Drawer | When |
|---|---|
| `references/preflight.md` | What the preflight gate checks before the cut |
| `references/resumable.md` | Idempotency probes + rerun-after-failure playbook |

## Boundaries

- Do not edit `release.py` / `build.py` / `install.py` — the engine only subprocess-calls them.
- Do not invent a version — `--version` is required for the apply path; the engine aborts rather than guess semver.
- Outward actions (push, `gh release create`) only after a confirm. Never share tokens or secrets in command examples.
