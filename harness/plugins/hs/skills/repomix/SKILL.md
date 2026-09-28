---
name: hs:repomix
injectable: true
description: >-
  Pack a codebase or subtree into an AI-friendly digest (XML, Markdown, plain,
  JSON). Use for LLM context snapshots, external library audits, or large review prep.
  Pairs with hs:scout.
allowed-tools: [Bash, Read, Write, Grep, Glob]
metadata:
  compliance-tier: workflow
argument-hint: "[path] [--style xml|markdown|plain|json] [--include <glob>] [--dry-run]"
---

# hs:repomix — pack a codebase into an AI-friendly digest

Packs a repo or subtree into a single file for loading into an LLM. The `repomix` CLI is an **optional external dependency**, feature-detected at runtime; missing -> install instructions, not hard-fail.

> **The artifact is a temporary build output** — do NOT commit the digest to git.
> `harness/state/` is in `.gitignore`; use `tmp/` or a path outside the repo.

## When to use

| Situation | Action |
|---|---|
| Onboarding a new codebase, need the full picture | pack everything, `--style markdown` |
| Implementing a feature, need module context | pack subtree `--include "src/module/**"` |
| Reviewing an external library | `--remote owner/repo` via npx |
| Auditing for secrets before deploy | pack + security check (enabled by default) |
| Context nearing limit, need compression | pair with `hs:context-engineering` |

## CLI check

```bash
# Feature-detect
repomix --version 2>/dev/null || echo "MISSING — install: npm i -g repomix"
```

If the CLI is missing -> recommend installing it, fall back to reading files manually (`hs:scout` + Read per file), and report `[NO_CLI_FALLBACK]` in the output.

## Workflow

1. **Determine scope** — local repo, subtree, or remote? Accept path/glob from the user or ask via AskUserQuestion if missing.

2. **Check tokens first** — load `references/output-handling.md`; estimate expected token count before running on a large repo. If the budget is tight -> suggest narrowing scope or using `--remove-comments --no-line-numbers`.

3. **Run pack** — see `references/invocation-patterns.md` for example commands covering each situation (subtree, remote, security audit, doc context).

4. **Check output** — review token count in the summary; if over budget -> refine `--include` / `-i` and rerun. Do not pass a digest larger than the budget to the LLM without warning.

5. **Confirm safety** — security check is enabled by default (Secretlint); if warnings appear -> review the flagged files before using the digest. Do not use `--no-security-check` unless the user explicitly requests it.

6. **Return results** — absolute path of the digest file, token count, and warnings (if any). If the digest exceeds the context budget -> suggest `hs:context-engineering` to decide which parts to load.

## Common flags

| Flag | Meaning |
|---|---|
| `--style xml\|markdown\|plain\|json` | output format |
| `--include "glob,glob"` | pack only matching files |
| `-i "glob,glob"` | additional ignores beyond .gitignore |
| `--remove-comments` | reduce tokens by stripping comments |
| `--no-line-numbers` | reduce tokens further |
| `--remote owner/repo` | pack a GitHub repo without cloning |
| `--copy` | copy to clipboard instead of writing a file |
| `--token-count-tree [N]` | view token distribution by directory tree |
| `--no-security-check` | disable secret scanning (use with care) |

## Batch mode (multiple repos)

For packing several repos/subtrees in one pass (e.g. auditing a set of vendored deps or a multi-repo review), use the batch processor instead of one-off CLI calls:

```bash
# Local repos, one shot
python3 ${CLAUDE_SKILL_DIR}/scripts/repomix_batch.py /path/to/repo1 /path/to/repo2 --style markdown -o repomix-output/

# Remote GitHub repos
python3 ${CLAUDE_SKILL_DIR}/scripts/repomix_batch.py owner/repo1 owner/repo2 --remote

# From a config file: [{"path": "...", "output": "custom.xml"}, {"path": "owner/repo", "remote": true}, ...]
python3 ${CLAUDE_SKILL_DIR}/scripts/repomix_batch.py -f repos.json
```

Same `--style` / `--include` / `--ignore` / `--remove-comments` / `--no-security-check` flags as the single-repo CLI (see Common flags below); `.env` resolution follows the same precedence as `resolve_env` (process env > skill `.env` > skills-root `.env` > repo-root `.env`). Prints a success/failed summary at the end — a non-zero exit means at least one repo in the batch failed to pack.

## Boundaries

- Do NOT commit the digest to git — all output is a temporary build artifact.
- Do not modify code based on digest content — this skill prepares context; it does not implement. To implement -> `hs:cook`.
- Do not run `--remote` on a private repo without explicit user confirmation.
- Finish: absolute path of the digest + token count + security warnings (if any) + suggested next step (hs:context-engineering / pass to LLM / implement).

## HARD-GATE (real wiring)

- **harness/state never-in-git**: `harness/state/` is in `harness/.gitignore` — writing digests there is git-safe.
- **No harness gate blocks repomix** — this skill is a pure tool wrapper; compliance rests on not committing artifacts (DRY, dev discipline).
- **hs:context-engineering** (`harness/plugins/hs/skills/context-engineering/`): run BEFORE to check the budget, run AFTER if the digest is larger than expected.
- **hs:scout** (`harness/plugins/hs/skills/scout/`): run BEFORE repomix if file location must be confirmed before deciding on pack scope.
