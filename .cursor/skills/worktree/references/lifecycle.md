# Worktree lifecycle

## Creation

```bash
git worktree add <path> -b <branch> [base-branch]
```

- `<path>`: new directory, typically a sibling of the main repo
- `-b <branch>`: create a new branch from `base-branch`
- `base-branch`: defaults to HEAD if not specified

Verify after creation:

```bash
git worktree list --porcelain
```

Important fields: `worktree`, `HEAD`, `branch`, `bare`, `detached`.

## Working inside a worktree

Each worktree has its own working directory but shares the repo's `.git/`. The same branch cannot be checked out in two worktrees simultaneously — git reports "already checked out".

To commit/push from inside the worktree, use `hs:git` (secret scan, conventional commit, push gate via `"${HARNESS_BIN_ROOT:-.}"/harness/install/git-pre-push-hook.sh`).

## Health check

```bash
git worktree list           # overview
git -C <path> status        # dirty/clean state
git -C <path> log --oneline -5   # quick divergence check
git -C <path> rev-list --count HEAD..origin/<base>   # commits behind upstream
```

A worktree is "unhealthy" if:
- The path no longer exists on the filesystem (stale)
- The branch was deleted from remote but metadata still exists
- There are forgotten uncommitted changes

## Deletion

Two situations:

| Situation | Command |
|-----------|---------|
| Clean worktree | `git worktree remove <path>` |
| Worktree has uncommitted changes | Ask user → `git worktree remove --force <path>` |

After the directory is removed, git cleans up the metadata automatically. If deleted manually (rm -rf) without going through `git worktree remove`, run `git worktree prune` to clean up.

## Prune

```bash
git worktree prune --dry-run    # preview — ALWAYS run first
git worktree prune              # execute stale cleanup
git worktree prune -v           # verbose (shows each item cleaned)
```

Prune only deletes metadata in `.git/worktrees/` — does not touch the external filesystem. Safe to run at any time.
