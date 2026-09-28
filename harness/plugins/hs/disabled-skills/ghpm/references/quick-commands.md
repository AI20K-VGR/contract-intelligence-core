# Quick Commands

```bash
# Create task
gh issue create --title "feat: add billing webhook retry" \
  --label "type:feature,priority:p1,status:ready,agent:ai-ok" \
  --body-file /tmp/task.md

# Update state
gh issue edit 123 --remove-label status:ready --add-label status:in-progress
gh issue comment 123 --body-file /tmp/handoff.md

# Link branch
gh issue develop 123 --checkout

# Trigger automation
gh workflow run project-triage.yml --ref main -f issue=123
```
