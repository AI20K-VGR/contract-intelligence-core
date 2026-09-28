---
name: input-mode-resolution
description: Resolve hs:code-review arguments to determine mode and diff source
---

# Input mode resolution

## Argument resolution table

| Argument | Mode | Diff command |
|---|---|---|
| `--pending` | Pending changes | `git diff HEAD` (staged + unstaged) |
| `#123` or PR URL | PR review | `gh pr diff 123` |
| String of 7+ hex chars | Commit review | `git show <hash>` |
| `codebase` | Full scan | `hs:repomix` compact → analyze entire repo |
| No argument | Recent context | changes in current context |

## Resolution order

1. Strip flags (`--fix`, `--reply`, `--spec <path>`) from the argument string.
2. Remaining string:
   - Starts with `#` or contains `github.com/…/pull/` → **PR mode**
   - Matches `/^[0-9a-f]{7,}$/` → **Commit mode**
   - Equals `codebase` → **Codebase scan mode**
   - Equals `--pending` → **Pending mode**
   - Empty → check whether recent diff exists in context; if yes → **Recent mode**;
     if no → `AskUserQuestion` with the 5 options below.

## AskUserQuestion when no argument is provided

Header: `Review Target`
Question: `What would you like to review?`

| Option | Description |
|---|---|
| Pending changes | Review staged/unstaged (`git diff HEAD`) |
| PR number | Enter PR number → fetch diff |
| Commit hash | Enter hash → `git show` |
| Full codebase scan | Scan entire repo (slower) |
| Recent changes in context | Use diff already present in context |

## Fetching the diff by mode

**Pending**
```bash
git diff HEAD
git diff --cached   # staged only (add if distinction is needed)
```

**PR**
```bash
gh pr view "$PR_REF" --json title,body,author,baseRefName,headRefName,files,additions,deletions,changedFiles
gh pr diff "$PR_REF"
gh pr checks "$PR_REF" 2>/dev/null || echo "No checks found"
```

**Commit**
```bash
git show "$HASH" --stat
git show "$HASH"
```

**Codebase**
```
→ delegate to hs:repomix to compact the repo
→ analyze compact output
```

## Scope gauge

After obtaining the diff, assess scope:
- **< 3 files**: scout optional
- **3-10 files**: scout required before review
- **> 10 files or security-sensitive**: scout + full checklist workflow (load `references/review-dimensions.md` in full)

The gap between actual scope (additions/deletions) and the PR description is its own signal — a description of "fix typo" paired with a +800-line diff is process slop; flag it immediately.
