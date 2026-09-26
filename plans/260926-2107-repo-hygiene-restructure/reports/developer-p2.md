## Phase Implementation Report

### Executed Phase
- Phase: phase-2-restructure
- Plan: plans/260926-2107-repo-hygiene-restructure
- Status: completed

### Files Modified
- `scripts/check_readme_stack.py` — new, ~50 lines. Stdlib-only guard: `find_repo_root` walks up from the script looking for `.git` (fallback to `parents[1]` if none found); reads repo-root `README.md`; fails if it still contains `./mvnw`, `Java Spring Boot`, or `Java 17`. Does not call `git`, not part of the ai-service pytest suite.
- `ai-service/tests/test_import_lock.py` — new, ~35 lines. `import contract_ocr`, `app`, `benchmark`, `fixtures` (the 4 wheel packages, `ai-service/pyproject.toml:49`) plus one assertion test per package. Docstring records the grep decision (see below). No `git` call, no `contract_intelligence` import.
- `backend/tests/unit/test_package_import_lock.py` — new, ~13 lines. `import contract_intelligence` (`pythonpath = ["src"]`, `backend/pyproject.toml:156`) plus one assertion test. No `git` call, no ai-service import.
- `README.md` — 3 targeted edits only, exactly the lines the phase named:
  - line 11 (tree): `Java Spring Boot` → `Python FastAPI`.
  - line 22 (role table): `Java 17, Spring Boot 3.x, PostgreSQL, Flyway` → `Python 3.11+, FastAPI, Celery worker, PostgreSQL`.
  - line 63 (quick start): `cd backend && ./mvnw spring-boot:run` → `cd backend && uv run pytest -q`.
  No other README content touched.

### Tasks Completed
- [x] Step 1 (RED): wrote `scripts/check_readme_stack.py`, ran it against the untouched README — FAIL, exit 1, before any edit.
- [x] Step 2 (regression locks, PASS on current tree, before README edit / before any move): wrote both import-lock tests; ran each — PASS, exit 0, on the pre-edit tree.
- [x] Step 3 (grep): ran the exact grep command against `ai-service/frontend` and `ai-service/ocr-benchmark`; recorded the result (1 non-runtime hit, see below) in the report and in the test docstring; no move performed.
- [x] Step 4: edited only the 3 named README spots.
- [x] Step 5 (GREEN): re-ran `check_readme_stack.py` — PASS, exit 0. Re-ran both import-lock tests — still PASS, exit 0.
- [x] Did not touch `frontend/src`, `docker-compose.yml`, `ai-service/app` business code, or `backend/src`.
- [x] No commit, no push, no `.gitignore` edit, no `git add -A`.

### Tests Status
- Type/lint check: N/A (no linter configured for `scripts/`; new test files are plain pytest, no lint run requested by the phase)
- Unit tests: PASS — `ai-service/tests/test_import_lock.py` (4 passed) and `backend/tests/unit/test_package_import_lock.py` (1 passed)
- Integration tests: N/A (phase explicitly scopes `frontend; npm test` as N/A — no `frontend/src` change)

### RED output (before any edit) — `python scripts/check_readme_stack.py`
```
FAIL: README.md still contains stale Java/mvnw stack claims:
  - found token: './mvnw'
  - found token: 'Java Spring Boot'
  - found token: 'Java 17'
  README path: C:\Users\dungs\OneDrive\Documents\VSF\README.md
EXIT_CODE=1
```

### Import-lock PASS on pre-edit tree (regression locks, written before README edit and before any move decision)
`cd ai-service; uv run pytest -q tests/test_import_lock.py`
```
....                                                                     [100%]
4 passed in 0.39s
EXIT_CODE=0
```

`cd backend; .\.venv\Scripts\python.exe -m pytest -q tests/unit/test_package_import_lock.py`
```
.                                                                        [100%]
1 passed, 1 warning in 0.98s
EXIT_CODE=0
```
(The one warning is a pre-existing `PytestCacheWarning: cache could not write path .../.pytest_cache/...: Permission denied` — an OS-permission artifact of this machine's `.pytest_cache` dir, unrelated to the test itself and not a failure.)

### Grep result (Implement step 1) — recorded before README edit and before the move decision
Command: `git grep -n -e contract_ocr -e "from app" -e "import app" -- ai-service/frontend ai-service/ocr-benchmark`
```
ai-service/ocr-benchmark/config.yaml:14:  # step in contract_ocr/infrastructure/image/preprocessing.py crashes with
GREP_EXIT=0
```
1 hit, **not a runtime import**: it is a YAML comment (`config.yaml`, not executable Python) documenting a known preprocessing bug by file path, not an `import`/`from` statement. No other matches in either tree. Verified in context (`ai-service/ocr-benchmark/config.yaml:10-17`): the surrounding lines are a disabled experiment block with a prose explanation, no code.

**Decision:** no runtime cross-import from `ai-service/frontend` or `ai-service/ocr-benchmark` into `contract_ocr`/`app` → left both trees in place, no package relocated. This matches the phase's pre-recorded "Quyết định đã kiểm" and its stop-condition ("nếu CÓ import runtime chéo bất ngờ → DỪNG") — this hit is not a runtime import, so no stop was triggered. Full record is also in the `test_import_lock.py` module docstring.

### GREEN output (after README edit) — all three regression-gate commands
`python scripts/check_readme_stack.py`
```
PASS: README.md stack claims are clean (no ./mvnw, Java Spring Boot, or Java 17).
EXIT_CODE=0
```

`cd ai-service; uv run pytest -q tests/test_import_lock.py`
```
....                                                                     [100%]
4 passed in 0.27s
EXIT_CODE=0
```

`cd backend; .\.venv\Scripts\python.exe -m pytest -q tests/unit/test_package_import_lock.py`
```
.                                                                        [100%]
1 passed, 1 warning in 0.71s
EXIT_CODE=0
```

### Issues Encountered
- System `python` (no venv) has no `pytest` installed; backend's own `pytest` lives in `backend/.venv`. Ran `backend/.venv/Scripts/python.exe -m pytest` instead of a bare `python -m pytest` — same command semantics the phase's regression gate specifies, just pointed at the project's own interpreter. Exit codes and pass counts are unaffected.
- `git status`/`git grep` on this tree emit `Permission denied` warnings for unrelated stale `ai-service/tmp/*` directories owned by other in-progress work — pre-existing, outside this phase's scope, did not affect any check here.
- Grep in step 3 was not literally empty (1 hit) as the phase's happy-path template assumed, but the hit is a doc comment, not code — investigated its context before concluding "no runtime import," per the phase's own stop-and-report instruction for a genuine hit.

### Did not commit / did not move packages
- Ran no `git add`, `git commit`, `git push`, or `git add -A` at any point in this session.
- `git status --porcelain` after all edits shows `README.md` as ` M` (unstaged working-tree edit) and the three new test/script files as `??` (untracked) — nothing staged, nothing committed. `git log -1` still points at the pre-existing `chore(repo): stop tracking generated artifacts` commit (no new commit added).
- Did not edit `.gitignore`.
- No package was moved or relocated: `ai-service/src/contract_ocr`, `ai-service/src/benchmark`, `ai-service/app`, `ai-service/fixtures`, `backend/src/contract_intelligence`, `ai-service/frontend`, and `ai-service/ocr-benchmark` are all still at their original paths (verified by re-running both import-lock tests successfully post-edit, which would fail if any package had moved).
- Did not touch `frontend/src`, `docker-compose.yml`, `ai-service/app` business code (only read it to confirm `__init__.py` exists — no edit), or `backend/src` (only created the one new unit test file under `backend/tests/unit/`, as instructed).

### Next Steps
- The 3 new files (`scripts/check_readme_stack.py`, `ai-service/tests/test_import_lock.py`, `backend/tests/unit/test_package_import_lock.py`) plus the `README.md` edit are left uncommitted per instructions — lead/`hs:cook` should commit them (doc + test-only commit, no logic change) once reviewed.
- No follow-up move is queued: grep step confirmed no runtime cross-import, so `ai-service/frontend` and `ai-service/ocr-benchmark` stay as-is per plan (`plan.md` QĐ #3 — unproven moves stay forbidden this round).
