# review-pr — `--reply` mode (post the review to GitHub)

Pre-flight (on failure → print locally, warn user, do NOT fail whole skill):

```bash
command -v gh >/dev/null 2>&1 || { echo "gh CLI not installed — printing locally"; exit 0; }
gh auth status >/dev/null 2>&1 || { echo "gh not authenticated — printing locally"; exit 0; }
```

Body: Summary + Risk + Findings + Verdict. Footer:
`*Posted by /hs:review-pr at <ISO-8601 UTC>*` — timestamp from `date -u +"%Y-%m-%dT%H:%M:%SZ"`.
Body cap: ≤60,000 chars; if exceeded → truncate Findings, append `[truncated — N findings omitted]`.

Map verdict → gh flag (pipe the body via stdin to avoid shell-quoting issues):

| Verdict | gh command |
|---|---|
| Approve | `gh pr review "$PR_REF" --approve --body-file -` |
| Request changes | `gh pr review "$PR_REF" --request-changes --body-file -` |
| Comment | `gh pr review "$PR_REF" --comment --body-file -` |

Self-PR fallback: `--approve` returns HTTP 422 → retry with `--comment`; note downgrade in chat.

`--fix --reply`: only post the final re-review when the loop converges. On a blocker → still post; verdict reflects remaining findings, body records the blocker for the human reviewer.
