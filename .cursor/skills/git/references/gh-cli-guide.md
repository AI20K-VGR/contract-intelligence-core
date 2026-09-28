# GitHub CLI guide

## Authentication

```bash
gh auth login        # Interactive login
gh auth status       # Check auth status
gh auth logout       # Logout
```

## Pull Requests

### Create PR

```bash
# Basic
gh pr create --base main --head feature-branch --title "feat: add login" --body "Summary"

# With HEREDOC body
gh pr create --base main --title "feat(auth): add OAuth" --body "$(cat <<'EOF'
## Summary
- Added OAuth2 provider support
- Implemented token refresh

## Test plan
- [ ] Unit tests pass
- [ ] Manual login test
EOF
)"

# Draft
gh pr create --draft --title "WIP: new feature"

# Assign reviewers
gh pr create --reviewer @user1,@user2

# Add labels
gh pr create --label "bug,priority:high"
```

### View / Review PR

```bash
gh pr list                    # List PRs
gh pr view 123                # PR details
gh pr view 123 --web          # Open in browser
gh pr checkout 123            # Checkout PR locally
gh pr diff 123                # View diff
gh pr status                  # Your PRs + reviews
```

### Merge PR

```bash
gh pr merge 123               # Merge commit
gh pr merge 123 --squash      # Squash commits
gh pr merge 123 --rebase      # Rebase merge
gh pr merge 123 --auto        # Auto-merge when checks pass
gh pr merge 123 --delete-branch  # Delete branch after merge
```

### PR comments

```bash
gh pr comment 123 --body "LGTM!"
gh api repos/{owner}/{repo}/pulls/123/comments  # View all
```

## Issues

```bash
gh issue list                 # List issues
gh issue view 42              # Issue details
gh issue create --title "Bug" --body "Description"
gh issue develop 42 -c        # Create branch from issue
```

## Repository

```bash
gh repo view                  # Current repo info
gh repo clone owner/repo      # Clone
gh browse                     # Open repo in browser
gh browse path/to/file:42     # Open file at specific line
```

## Workflow runs

```bash
gh run list                   # List workflow runs
gh run view <run-id>          # Run details
gh run watch                  # Watch running workflow
gh run rerun <run-id>         # Re-run failed workflow
```

## JSON output (scripting)

```bash
gh pr list --json number,title,author
gh pr view 123 --json commits,reviews
gh issue list --json number,title --jq '.[].title'
```

## Common patterns

### Create PR with auto-merge

```bash
gh pr create --fill && gh pr merge --auto --squash
```

### Close stale PRs

```bash
gh pr list --state open --json number -q '.[].number' | xargs -I {} gh pr close {}
```
