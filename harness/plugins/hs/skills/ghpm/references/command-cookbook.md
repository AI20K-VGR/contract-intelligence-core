# Command Cookbook

Use `gh` for common operations. Use `gh api graphql` when Projects fields require node IDs or typed field updates.

## Repo Snapshot

```bash
gh repo view --json nameWithOwner,defaultBranchRef,owner,url
gh issue list --state open --limit 100 --json number,title,labels,assignees,milestone,updatedAt,url
gh pr list --state open --json number,title,headRefName,baseRefName,reviewDecision,statusCheckRollup,url
gh run list --limit 20 --json databaseId,displayTitle,workflowName,status,conclusion,headBranch,url
```

## Issues

```bash
gh issue create --title "type(scope): concise task" --body-file task.md --label "type:task,priority:p2"
gh issue view 123 --json number,title,body,labels,assignees,state,comments,url
gh issue edit 123 --add-assignee @me --add-label status:ready
gh issue comment 123 --body-file handoff.md
gh issue close 123 --comment "Done: PR #456 merged, checks green."
```

## Projects CLI

`gh project` requires token scope `project`.

```bash
gh auth status
gh auth refresh -s project
gh project list --owner OWNER
gh project view 1 --owner OWNER --format json
gh project field-list 1 --owner OWNER --format json
gh project item-list 1 --owner OWNER --format json --limit 100
gh project item-add 1 --owner OWNER --url https://github.com/OWNER/REPO/issues/123
```

## Project Field Updates

Use GraphQL for precise field writes:

```bash
gh api graphql -f query='
query($owner:String!, $number:Int!) {
  organization(login:$owner) {
    projectV2(number:$number) {
      id
      fields(first:50) { nodes { ... on ProjectV2FieldCommon { id name } } }
      items(first:20) { nodes { id content { ... on Issue { number title url } } } }
    }
  }
}' -F owner=ORG -F number=1
```

Then call `updateProjectV2ItemFieldValue` with the project ID, item ID, field ID, and option ID for single-select fields. For user-owned Projects, replace `organization(login:$owner)` with `user(login:$owner)` in the query.

## Actions Automation

Manual run:

```bash
gh workflow run project-triage.yml --ref main -f issue=123
gh run watch RUN_ID --exit-status
gh run view RUN_ID --json status,conclusion,jobs,url
```

Issue-triggered workflow pattern:

```yaml
name: Project Triage
on:
  issues:
    types: [opened, reopened, labeled, assigned]
permissions:
  issues: write
  contents: read
jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - run: gh issue edit "$ISSUE" --add-label "status:triage"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE: ${{ github.event.issue.html_url }}
```

For Projects mutations from Actions: ensure token permissions + org policy allow project writes. If `GITHUB_TOKEN` insufficient, use a GitHub App token with least privilege.

## Handoff Audit

```bash
gh issue list --search 'label:"agent:needs-context" state:open' --json number,title,url
gh issue list --search 'label:"status:blocked" state:open' --json number,title,assignees,updatedAt,url
gh pr checks PR_NUMBER
git branch --show-current
git status --short
```

Report only evidence you verified.
