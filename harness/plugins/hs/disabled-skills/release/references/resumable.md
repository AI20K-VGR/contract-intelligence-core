# Resumable / idempotent rerun

Every step probes "already done for this version?" and skips if so. Re-running the same `--version` is always safe.

## The probes

| Step | "done?" probe |
|---|---|
| 1 cut | CHANGELOG has `## [X.Y.Z]` **and** release.json version == X.Y.Z **and** local tag `harness-vX.Y.Z` exists |
| 2 push tag | `git ls-remote --tags origin harness-vX.Y.Z` is non-empty |
| 3 gh release | `gh release view harness-vX.Y.Z` exits 0 |

## Why the cut lock is LOCAL but the push lock is REMOTE

`release.py` runs `commit → tag → push HEAD → push tag` with no try/except. If `push tag` fails after the commit landed, a naive remote-only probe (ls-remote) would see no tag and **re-cut** — and `lock_unreleased` raises `[X.Y.Z] already exists`, wedging the release.

So the cut is considered done from LOCAL evidence (CHANGELOG + local tag + release.json). A rerun there skips step 1, goes straight to step 2 — re-pushes HEAD + tag (an existing tag push is a no-op).

## Failure playbook

- **Push tag failed** → re-run; engine skips cut, re-pushes. No manual fix.
- **gh release failed** → re-run; only step 3 retries.
- Showcase publishing is handled by CI (`sync-showcase.yml`) on push to `main`, not by the release engine — a failed showcase sync is a CI re-run, never a release-step retry.
- **Never** `git tag -d` / delete a remote tag to "start over" — the local-lock design exists precisely so you don't have to.
