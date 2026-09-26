# Tester Report — Repo Hygiene / README Stack (independent verification)

**Scope**: Independent test of two commits on branch `feature/ai2-integration`:
- `b9ec2c7` chore(repo): stop tracking generated artifacts
- `4205154` docs(repo): describe the backend as Python

**Verdict: PASS**

## Environment

- Repo: `C:\Users\dungs\OneDrive\Documents\VSF`
- Branch: `feature/ai2-integration`
- HEAD at test time: `4205154fcf618035b7db579ef2236a9dd07bc64b` (`4205154 docs(repo): describe the backend as Python`)
- HEAD~1: `b9ec2c75e7166c2875bf04b5d0c8e0c0ede66018` (`b9ec2c7 chore(repo): stop tracking generated artifacts`)
- Both target commits are already applied on HEAD; no checkout/reset was needed. No source was modified, nothing was committed.
- Python: 3.13.14 (`python --version`)

## Commands run and exit codes

| # | Command | cwd | Exit code | Result |
|---|---|---|---|---|
| 1 | `python scripts/check_repo_hygiene.py` | repo root | **0** | `PASS: repo hygiene check passed (ls-files clean, check-ignore correct, files intact).` |
| 2 | `python scripts/check_readme_stack.py` | repo root | **0** | `PASS: README.md stack claims are clean (no ./mvnw, Java Spring Boot, or Java 17).` |
| 3 | `uv run pytest -q tests/test_import_lock.py` | `ai-service/` | **0** | `4 passed in 0.22s` |
| 4 | `uv run pytest -q tests/unit/test_package_import_lock.py` | `backend/` | **0** | `1 passed, 1 warning in 0.57s` |

Command 4 warning (non-blocking, does not affect exit code or pass/fail):
```
PytestCacheWarning: cache could not write path ...\backend\.pytest_cache\v\cache\nodeids: [Errno 13] Permission denied
```
This is a local pytest-cache write permission issue on this machine, unrelated to the two commits under test; the test itself still passed and the suite exited 0.

## Git verification

**`git ls-files` for the four now-untracked paths — expected empty:**
```
git ls-files apps/web/node_modules output ocr-result.json result_khoiluong.json
```
Output: *(empty, 0 lines)* — exit code 0. Confirmed none of the four paths are tracked in the index.

**Five generated paths still present on disk (untouched, not deleted by the untrack):**

| Path | Exists on disk |
|---|---|
| `apps/web/node_modules` | True |
| `apps/web/.vite` | True |
| `output` | True |
| `ocr-result.json` | True |
| `result_khoiluong.json` | True |

## Notes

- `git status` on the working tree shows a large number of unrelated modified/untracked files (ai-service, backend, frontend feature work, harness/plans scaffolding, etc.) — these are pre-existing uncommitted work on `feature/ai2-integration`, not touched or introduced by this test run, and are out of scope for this verification.
- `git log`/`git status` emitted `warning: could not open directory ... Permission denied` for several `ai-service/tmp/*` subfolders (stale locked temp dirs from prior runs). These are pre-existing local artifacts unrelated to the two commits under test and did not affect any exit code above.
- No source files were modified. No commits were made.

## Verdict

**PASS** — all four commands exited `0`, `git ls-files` for the four now-ignored paths is empty, and all five generated paths still exist on disk.
