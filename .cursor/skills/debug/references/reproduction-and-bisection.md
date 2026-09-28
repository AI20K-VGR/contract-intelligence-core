# reproduction-and-bisection — reproducing failures and finding the causing commit

Load when: the `--bisect` flag is used, or it is unclear which commit caused the regression.

> The bundled tools below (`find_flaky.py`, `bisect_run.py`, `find_polluter.py`, `shrink_failure.py`) live in this skill's own `scripts/` directory, next to this drawer. The `python3 scripts/<tool>.py` commands assume that skill directory is your working directory — prefix an absolute path to the skill's `scripts/` if you invoke them from elsewhere.

## Stable reproduction first

Before bisecting, the failure must be reproduced consistently:

1. Record exact steps to trigger the failure.
2. Run ≥ 3 times to confirm not flaky — for a test, quantify with the bundled tool:

```bash
python3 scripts/find_flaky.py harness/tests/test_x.py::test_y -n 20
# STABLE_FAIL / STABLE_PASS -> safe to bisect; FLAKY (mixed) -> stabilize first (exit 1)
```

3. Cannot reproduce → add instrumentation (`instrumentation.md`) to collect more data.

**Do not bisect a flaky failure** — results will mislead; `find_flaky` confirms it before wasting a bisection (`find_polluter` handles the passes-alone-fails-in-suite case).

## git bisect — find the commit that caused the regression

Use when you know: "commit A works, commit B fails, but it is unclear which intermediate commit is the cause."

```bash
git bisect start
git bisect bad                    # current commit: failing
git bisect good <commit-hash>     # known-good commit

# Git automatically checks out the midpoint commit
# Run tests / verification
python3 -m pytest harness/tests/test_feature.py -q

git bisect good   # if it passes
git bisect bad    # if it fails

# Repeat until git reports the first bad commit
git bisect reset  # end session, return to HEAD
```

Automate the whole search with the bundled tool — it validates the refs (good must be an ancestor of bad), drives `git bisect run`, prints the first bad commit, and ALWAYS resets the bisect state afterwards (even on error), so the tree is never left mid-bisect:

```bash
python3 scripts/bisect_run.py --good <known-good-ref> -- python3 -m pytest harness/tests/test_feature.py -q
# FIRST BAD COMMIT: <sha> <subject>
python3 scripts/bisect_run.py --good v1.2.0 --dry-run -- ./repro.sh   # preview the plan, mutate nothing
```

## Finding the test that pollutes others (test isolation)

When a test passes in isolation but fails when run with the suite → shared state is leaking:

```bash
# Run tests one by one, stop when the polluter is found
# Adjust the glob pattern to match the project's runner
python3 -m pytest harness/tests/ -q --tb=no -p no:randomly 2>&1 | grep -E 'FAILED|ERROR'

# Or use pytest-randomly with a fixed seed to reproduce
python3 -m pytest harness/tests/ -q -p randomly --randomly-seed=1234
```

Automate the binary search with the bundled tool — it confirms the target passes alone, reproduces the failure with the full earlier set, then bisects (O(log n) runs, not O(n)) to the single polluter:

```bash
python3 scripts/find_polluter.py harness/tests/test_feature.py::test_victim
# -> POLLUTER: harness/tests/test_other.py::test_that_leaks_state
```

Fallback (manual): run progressively smaller subsets until the test causing the state leak is isolated.

## Minimize the failing input (delta-debugging)

When the repro is a large input (a payload, a generated file, a long sequence of steps) and it is unclear which part actually triggers the failure, shrink it to a 1-minimal reproducer — removing any single remaining unit makes the failure disappear. The bundled tool applies Zeller's ddmin and backs up the original to `<input_file>.orig`:

```bash
# the command must exit 0 while the input STILL reproduces ("interesting")
python3 scripts/shrink_failure.py crash_input.txt -- ./repro.sh        # reduce by lines (default)
python3 scripts/shrink_failure.py payload.bin --char -- ./repro.sh     # reduce by characters
# -> reduced 412 -> 3 lines (1-minimal). Original saved to crash_input.txt.orig
```

Confirm the failure is deterministic first (`find_flaky.py`) — a flaky oracle makes the search lie.

## Failing repro test — required output of hs:debug

After the root cause is identified, write a test that reproduces the failure (rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md`):

```python
# Python/pytest example — test must FAIL before the fix
def test_reproduces_root_cause():
    """Reproduces: <one-line description of root cause>."""
    # Arrange: set up the conditions that cause the bug
    # Act: trigger the failure
    # Assert: confirm current wrong behavior
    #         (this test MUST fail to prove the root cause)
    assert result == expected_wrong_value  # <- intentional failure
```

Checklist before handing off to `hs:fix`:
- [ ] Test fails intentionally when run with `python3 -m pytest <path> -q`.
- [ ] Test is as simple as possible — does not test unrelated behavior.
- [ ] Test name describes the root cause, not just the symptom.
- [ ] Test path is recorded in the report at `plans/reports/<slug>-debug-report.md`.

## Connection to hs:fix

The failing repro test is the **primary input** for `hs:fix`:

```
/hs:fix <path-to-failing-test>
```

`hs:fix` implements the fix to turn the test from red to green, then runs the full suite.
