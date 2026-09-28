# Git Queries — hs:retro

Bash commands to collect raw data. Run in order. Record `0` or `N/A` if a command returns nothing — never invent numbers.

`$SINCE` and `$UNTIL` are resolved in Step 1 of SKILL.md.

## Velocity

```bash
# Total commits in the period
git log --since="$SINCE" --until="$UNTIL" --oneline | wc -l

# Commits by day (to visualize distribution)
git log --since="$SINCE" --until="$UNTIL" --format="%ai" \
  | cut -d' ' -f1 | sort | uniq -c

# Number of days with at least one commit
git log --since="$SINCE" --until="$UNTIL" --format="%ai" \
  | cut -d' ' -f1 | sort -u | wc -l

# Files changed (unique)
git log --since="$SINCE" --until="$UNTIL" --name-only --format="" \
  | sort -u | grep -c .
```

## Code Health

```bash
# LOC added / removed / net
git log --since="$SINCE" --until="$UNTIL" --numstat --format="" \
  | awk 'NF==3 {add+=$1; del+=$2} END {print "added="add, "removed="del, "net="add-del}'

# File hotspots — top 10 most-changed files
git log --since="$SINCE" --until="$UNTIL" --name-only --format="" \
  | sort | uniq -c | sort -rn | head -10

# Test file changes (harness pattern: test_ prefix or /tests/ dir)
git log --since="$SINCE" --until="$UNTIL" --name-only --format="" \
  | grep -E "(test_|_test\.|/tests/|\.test\.|\.spec\.)" | wc -l

# Total file changes (to compute ratio)
git log --since="$SINCE" --until="$UNTIL" --name-only --format="" \
  | grep -v "^$" | wc -l
```

## Commit Type Distribution

```bash
# Conventional commit type distribution
git log --since="$SINCE" --until="$UNTIL" --format="%s" \
  | sed 's/(.*//' | sed 's/:.*//' | sort | uniq -c | sort -rn
```

## Author Breakdown (only with --team)

```bash
# Commits by author
git log --since="$SINCE" --until="$UNTIL" --format="%ae" \
  | sort | uniq -c | sort -rn

# List of active authors
git log --since="$SINCE" --until="$UNTIL" --format="%ae" \
  | sort -u
```

## Compare Period (only with --compare)

Re-run all queries above using `$PREV_SINCE` / `$PREV_UNTIL`. Store results in corresponding `PREV_*` variables to compute deltas.

## Plans Sentinel

```bash
# Create sentinel file with $SINCE timestamp
touch -t $(date -d "$SINCE" +%Y%m%d%H%M.%S 2>/dev/null \
  || date -jf "%Y-%m-%d" "$SINCE" +%Y%m%d%H%M.%S) /tmp/retro-since-sentinel

# Plan files modified in the period
find plans/ -name "*.md" -newer /tmp/retro-since-sentinel 2>/dev/null | head -20

# Task completion from checkboxes
grep -r "\- \[x\]" plans/ 2>/dev/null | wc -l
grep -r "\- \[ \]" plans/ 2>/dev/null | wc -l
```

## Notes

- `git log` excludes merge commits unless `--merges` is passed.
- For large repos, add `--max-count=5000` to avoid timeouts.
- If `gh` CLI is unavailable: skip issue metrics and record `N/A` in the corresponding table cells.
