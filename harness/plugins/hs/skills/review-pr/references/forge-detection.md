# Forge detection (GitHub `gh` ↔ GitLab `glab`)

This is a **tier-1** (developer-tool) capability: `hs:review-pr` reviews a PR/MR on whichever forge the repo uses. **Independent** of the tier-2 orchestrator's GitLab support — a separate **declared seam** (deferred): enabling GitLab here does NOT enable it there.

Detect the hosting forge **before any review command**, then use exactly one CLI for the rest of the run. Never mix `gh` and `glab` in a single review.

```bash
REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
case "$REMOTE_URL" in
  *gitlab*) echo "FORGE=gitlab CLI=glab" ;;
  *github*) echo "FORGE=github CLI=gh" ;;
  *)        echo "FORGE=unknown CLI=unknown REMOTE=$REMOTE_URL" ;;
esac
```

## Detection rules

- Remote hostname/path has `gitlab` → use `glab` + GitLab **MR** terms.
- Remote hostname/path has `github` → use `gh` + GitHub **PR** terms.
- GitHub Enterprise and self-managed GitLab supported when the remote URL clearly contains `github`/`gitlab`.
- **Unknown forge** → inspect all remotes (`git remote -v`); ask the user only if repo state can't answer it. Do NOT guess — a wrong-forge command is worse than a question.
- Verify the selected CLI exists and is authenticated before running:
  - GitHub: `command -v gh` and `gh auth status`
  - GitLab: `command -v glab` and `glab auth status`
- If the selected CLI is missing/unauthenticated, stop with the install/auth command needed. Do NOT silently fall back to the other forge.

## Command mapping

| Operation | GitHub (`gh`) | GitLab (`glab`) |
| --- | --- | --- |
| View metadata | `gh pr view "$PR_REF" --json ...` | `glab mr view "$PR_REF"` (text) — for JSON: `glab api "projects/:fullpath/merge_requests/<iid>"` |
| List / search prior work | `gh pr list --state all --search "<terms>" --json ...` | `glab mr list --all --search "<terms>"` |
| Fetch diff | `gh pr diff "$PR_REF"` | `glab mr diff "$PR_REF"` |
| Check out branch | `gh pr checkout "$PR_REF"` | `glab mr checkout "$PR_REF"` |
| Read comments | `gh pr view "$PR_REF" --comments` | `glab mr view "$PR_REF" --comments` |
| Post comment / approve | `gh pr review "$PR_REF" ...` | `glab mr note "$PR_REF" -m "<body>"` (comment); `glab mr approve "$PR_REF"` (approval) |
| CI / pipeline status | `gh pr checks "$PR_REF"` | `glab ci status` (on the MR branch) — or the pipeline field via `glab api "projects/:fullpath/merge_requests/<iid>"` |

## GitLab notes (probed against `glab` 1.36.0 **and** 1.115.0)

`glab` grew JSON output between these two. Both are in the wild, so both are here — and
the mapping table above stays on `glab api`, which is the one path that works on either.

- `glab mr view` accepts an MR id or branch. Flags on both: `-c/--comments`, `-p/--page`, `-P/--per-page`, `-s/--system-logs`, `-w/--web`, `-R/--repo`.
  - **1.36** prints text only — no `--output`/`--jq`. **1.115** adds `-F/--output text|json` and `--jq`.
  - Writing for one glab means writing for the reader who has the other, so use `glab api` (REST v4) unless you know the version in front of you.
- `glab mr list` defaults to open MRs; add `-A/--all` for duplicate/prior-work searches, filter with `--search "<string>"`. Same split: no JSON flag on 1.36, `-F/--output json` + `--jq` on 1.115. `glab api` covers both.
- `glab mr note` (alias `glab mr comment`) posts a comment: `glab mr note "$PR_REF" -m "<body>"`; `--unique` skips duplicates. This form works on **both** — but on 1.115 it is DEPRECATED, not removed.
  - Measured on 1.115: it still reaches the API and warns `Flag --message has been deprecated, use 'glab mr note create' instead` (it 404s on a nonexistent project, so the flag parsed and the call went out).
  - `mr note --help` on 1.115 no longer lists `-m` at all — the flag is documented under `mr note create`. Do not read its absence from that help as removal.
  - 1.36 has no `note create`/`note list`. 1.115 adds `create`/`delete`/`list`/`reopen`/`resolve`, all EXPERIMENTAL — which is why the recommendation does not move to them yet.
  - When the deprecation becomes a removal, switch to `glab mr note create "$PR_REF" -m "<body>"`. Read comments via `glab mr view "$PR_REF" --comments` on either.
- GitLab has no direct `gh pr checks` equivalent: read pipeline state via `glab ci status` or MR JSON via `glab api`.
