# instrumentation — adding trace/log to observe runtime behavior

Load when: manual tracing is not feasible and state/data-flow observation is needed at runtime.

## When instrumentation is needed

- Failure can't be reproduced consistently.
- Failure is deep in the call stack, not visible in current output.
- A real value needs confirming at a specific point in execution flow.
- CI/CD fails but logs insufficient.

## Principles

Add instrumentation to **observe**, not to fix. Remove after the root cause is confirmed (or promote to a permanent debug log if needed for monitoring).

## Stack-agnostic patterns

### Print/log at boundaries

Add a log at each component boundary to identify which component receives bad data:

```
# Python
import sys
print(f"DEBUG [{__name__}]: value={value!r}", file=sys.stderr)

# Shell
echo "DEBUG: value='${value}'" >&2

# JS/TS — use console.error in tests (console.log may be buffered)
console.error('DEBUG entry:', { value, stack: new Error().stack });
```

### Stack trace on-demand

When you need to know "who calls this function":

```python
import traceback
traceback.print_stack(file=sys.stderr)
```

```typescript
console.error('DEBUG stack:', new Error().stack);
```

### Run and filter output

```bash
# Run tests, filter only DEBUG lines
python3 -m pytest harness/tests/ -s 2>&1 | grep 'DEBUG'

# CI/CD — fetch logs from a failed run
gh run view <run-id> --log-failed

# Log file — monitor in real time
tail -f app.log | grep --line-buffered 'ERROR\|WARN\|DEBUG'
```

### DB / storage diagnostics

Use the project stack's CLI (sqlite3, psql, mysql, etc.):

```bash
# sqlite3 example
sqlite3 db.sqlite "SELECT * FROM events ORDER BY ts DESC LIMIT 20;"

# psql example
psql -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

## Log and CI/CD analysis

| Source | Tool | Notes |
|---|---|---|
| GitHub Actions | `gh run list --limit 10` → `gh run view <id> --log-failed` | Filter to the failed step first |
| App logs | `grep --line-buffered`, `awk` | Always use `--line-buffered` when piping |
| Codebase | `docs/codebase-summary.md` (< 2 days old) or `hs:scout` | Read structure before searching for files |

## Log patterns and what they indicate

| Pattern | Likely cause |
|---|---|
| Sudden spike | Deploy / config change / dep update |
| Gradual increase | Resource leak, data growth |
| Periodic | Cron job, scheduled task |
| Single endpoint | Code bug, data issue |
| All endpoints | Infrastructure, DB, network |

## Cleanup after investigation

Remove/comment out debug logs before committing, unless:
- Log useful for production monitoring → promote to appropriate level (INFO/WARN).
- A test assertion requires the output → keep it, document purpose clearly.
