# Defect Reproduction — Protocol for hard-to-reproduce defects

## When to load this file

- Defect cannot be reproduced after 2 attempts.
- Flaky defect (sometimes fails, sometimes passes).
- Defect only occurs in a specific environment (CI, production, another machine).

## Step-by-step reproduction protocol

### Step R1 — Gather more data from the user

AskUserQuestion with specific questions (not open-ended):

```
1. When did the defect last occur? On which branch/commit?
2. What changed recently (code, config, dependency, env)?
3. On which machine / environment? CI or local?
4. Are there logs / screenshots / CI artifacts? (specific paths)
5. Frequency: always / intermittent / only after condition X?
```

### Step R2 — Check the environment

```bash
# Branch + commit
git log --oneline -5
git status

# Python / runtime version
python3 --version

# Dependency state
pip list | grep -E "<suspected-package>"

# Relevant env vars (do not print secrets)
env | grep -E "HARNESS_|CI|PYTEST" | sort
```

### Step R3 — Controlled reproduction

Try in priority order:

1. **Minimal command** — 1 test case, 1 file, isolated.
   ```bash
   python3 -m pytest harness/tests/<file>::<test> -xvs
   ```
2. **Add verbose/debug output** — enable logging, increase verbosity.
3. **Run multiple times** — detect flakiness:
   ```bash
   python3 -m pytest harness/tests/<file>::<test> -x --count=10
   ```
4. **Reproduce on CI** — push the branch, view full CI log via `gh run view`.

### Step R4 — Flaky defects

Flaky signal: pass/fail is unstable with the same input.

Common causes:
| Cause | How to check |
|---|---|
| Race condition / timing | Run with lower `--timeout`; add a small sleep to confirm |
| Shared state between tests | Run test in isolation vs full suite |
| Test ordering | `pytest --randomly-seed=0` vs different seed |
| External dependency | Mock/stub → if flakiness stops = external problem |
| File system state | Clean tmp before each run |

Flakiness not caused by code logic → record and document, **do not fast-fix** — understand the root cause first.

### Step R5 — Still cannot reproduce

After trying R1-R4:

1. Record all data collected (nothing omitted).
2. Ask the user via AskUserQuestion:
   - **Continue with current data** (Recommended if enough data to hypothesize)
   - **Gather more logs/instrumentation** — user adds logging then re-runs
   - **Move to backlog** (`backlog_register.py add`) — defect not critical enough to spend more resources now
3. Do NOT guess at root cause without a stable reproduction.

## CI-only failures

Defect only appears on CI:

```bash
# View most recent CI run log
gh run list --limit 5
gh run view <run-id> --log-failed

# Compare CI env vs local
gh run view <run-id> --json jobs --jq '.jobs[].steps'
```

Check:
- [ ] CI using a different Python version?
- [ ] CI missing an env var?
- [ ] CI has a stale artifact cache?
- [ ] Test isolation differs from local (run order, tmp dir)?

## Reproduction step output

When reproduction succeeds, record in the report:
```
Reproduction command: <minimal command>
Environment: <OS, Python version, branch, commit>
Frequency: <always / X/10 runs>
Baseline output: <exact paste>
```

Report → `plans/reports/<slug>-triage-repro-report.md`. Then continue to triage Step 2 (hs:scout).
