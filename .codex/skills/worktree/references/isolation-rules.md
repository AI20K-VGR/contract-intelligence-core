# Parallel isolation rules

Worktrees allow working on multiple branches simultaneously in the same repo. The rules below prevent conflicts and data loss.

## File ownership rules

- Each worktree owns its own branch — do not edit the same file in two worktrees simultaneously without a clear merge strategy.
- Shared config files (`harness-hooks.yaml`, `stage-policy.yaml`, `pyproject.toml`) should only be modified in one worktree at a time.
- Schemas (`harness/schemas/*.json`) and migrations: serialize — not parallel.

## Branch rules

- Each worktree must be on a different branch. Git refuses to check out the same branch twice.
- Do not rebase/force-push a branch that is checked out in another worktree.
- When merging a worktree branch into main: use `hs:git pr` to create a PR, do not merge directly from inside the worktree.

## Git environment isolation

A worktree shares the repository's object store with its siblings. When a shell (or a hook the harness spawns — e.g. a pre-push gate runs `git diff`) inherits `GIT_*` variables from a parent that was scoped to a *different* worktree, git writes to the wrong tree and produces corruption that is painful to debug. Unset these before any git command issued from inside a worktree:

- `GIT_DIR`
- `GIT_WORK_TREE`
- `GIT_INDEX_FILE`
- `GIT_OBJECT_DIRECTORY`
- `GIT_ALTERNATE_OBJECT_DIRECTORIES`
- `GIT_COMMON_DIR`
- `GIT_NAMESPACE`

Before any **destructive** operation (`reset`, `clean`, `checkout -f`, `worktree remove`), confirm you are on the branch you think you are with an **exact-match** check — do not trust the prompt or a substring match:

```bash
[ "$(git rev-parse --abbrev-ref HEAD)" = "<expected-branch>" ] || { echo "wrong branch"; exit 1; }
```

A fuzzy match (`grep feature`) passes on `feature-old` as well as `feature` — only an exact string equality protects the wrong tree from a destructive command.

## Harness artifact rules

The push gate (`harness/install/git-pre-push-hook.sh`) runs independently in each worktree — each worktree needs its own artifacts (`verification.json`, `artifact-review-decision.json`). Do not share artifacts between worktrees.

`harness/state/` is append-only JSONL — no RMW (read-modify-write) on state files.

**State resolves to the HOST, not per worktree.** A linked worktree (its `.git`
is a FILE, not a dir) redirects `state/` back to the host repo — both flavours: the
hook flavour to `<host>/harness/state`, the script flavour to `<host>/.harness/state`.
Detection reads the `.git` file (no `git` spawn on the hot path), is memoized, and is
fail-open — any surprise layout falls back to the old per-worktree behaviour.
`HARNESS_STATE_DIR` still wins over the redirect. Many worktrees share ONE state store
and never fragment or lose trace/telemetry when a worktree is removed.

**Concurrent writes shard by session, not by lock.** With N worktrees on one host
store, trace/telemetry writes carrying a real session go to a per-session shard
(`trace-YYYYMMDD-<disc>.jsonl`, `<sink>-<disc>.jsonl`) — each an independent
hash-chain from its own genesis — so concurrent sessions never contend on a single
daily file. A write with no session keeps the shared legacy file, which stays atomic
because a single JSONL line is under `PIPE_BUF` (4096 B). Every reader unions the
legacy file with its shards; `verify_trace_chain` walks legacy and each shard as
separate chains.

**A worktree carries the runtime, not the test suite.** `.worktreeinclude`
deliberately omits `harness/tests` and `harness/e2e` — a worktree only needs to RUN
the harness; the pytest suite runs at the host (or the tracked dogfood checkout),
not inside a carried worktree.

## Completion rules

Before deleting a worktree:
1. Confirm no uncommitted changes remain (or they have been stashed/discarded intentionally).
2. Confirm commits have been pushed to remote (or merged into the target branch).
3. Run `git worktree remove <path>` — do not delete manually with `rm -rf` to avoid stale metadata; if already deleted manually, run `git worktree prune`.

## Coordination with hs:cook

`hs:cook` executes a plan in a specific context. When using worktrees:
- Execute only one `hs:cook` phase per worktree at a time.
- Two worktrees must not cook the same phase if that phase modifies shared files (hooks, scripts, schemas).
- Do not run `hs:afk` in parallel on the same plan from two different worktrees.
