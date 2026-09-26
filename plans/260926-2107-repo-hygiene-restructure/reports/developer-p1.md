## Phase Implementation Report

### Executed Phase
- Phase: phase-1-hygiene
- Plan: plans/260926-2107-repo-hygiene-restructure
- Status: completed

### Files Modified
- `scripts/check_repo_hygiene.py` — new, ~150 lines. Cross-platform hygiene guard: `find_repo_root` walks up from the script looking for `.git`; if `git` binary is missing or `git rev-parse --is-inside-work-tree` fails, prints a one-line `SKIP:` reason and exits 0. When git works: asserts `git ls-files` empty for the 5 artifact paths, asserts `git check-ignore -q` succeeds for cache patterns (`node_modules/x`, `output/foo`, `ocr-result.json`, `result_khoiluong.json`, `.pytest-review-r2-ai2/x`, `.uv-cache-x/y`, `backend/backend/x`), asserts `git check-ignore -q` FAILS for real existing source paths (`frontend/src/App.tsx`, `frontend/src/data`), and asserts the 5 untracked paths still exist on disk. Exit 0 only if every assertion passes.
- `.gitignore` — appended a block titled `# ---------- Repo hygiene (P1) ----------` (unstaged working-tree edit only) with exactly: `/node_modules/`, `/apps/web/node_modules/`, `/apps/web/.vite/`, `/output/`, `/ocr-result.json`, `/result_khoiluong.json`, `.pytest-*`, `.uv-cache-*`, `backend/backend/`, `/tmp/`, `.tmp-*`. No existing rules removed; `!docs/assets/**` (line 15) untouched; no bare `/apps/` rule added; `frontend/src/data` not ignored (verified negative check passes).
- Git index (via `git rm --cached`, not staged as file content changes): `apps/web/node_modules/**` (448 entries), `apps/web/.vite/**` (2 entries), `output/**` (15 entries), `ocr-result.json`, `result_khoiluong.json` — all untracked from the index, none deleted from disk. No `-f` used.
- `tmp/hygiene-backup/` — new backup copies of `output/`, `ocr-result.json`, `result_khoiluong.json`, made **before** any `git rm --cached` (tmp/ is gitignored, not staged).

### Tasks Completed
- [x] Tests Before (RED): wrote `scripts/check_repo_hygiene.py` first; ran it against the untouched tree; confirmed it failed on both the tracked-artifact assertions and the check-ignore assertions.
- [x] Appended the "Repo hygiene (P1)" `.gitignore` block with exactly the listed patterns; kept `!docs/assets/**`; no `/apps/` rule; `frontend/src/data` left un-ignored.
- [x] Asserted all 5 live paths existed on disk BEFORE any `git rm` (manual check, then re-verified via the script's own on-disk assertion post-rm).
- [x] Backed up `output/`, `ocr-result.json`, `result_khoiluong.json` into `tmp/hygiene-backup/` before touching the index.
- [x] `git rm -r --cached -- apps/web/node_modules apps/web/.vite output` (no `-f`).
- [x] `git rm --cached -- ocr-result.json result_khoiluong.json` (no `-f`).
- [x] Tests After (GREEN): re-ran the script; PASS, exit 0.
- [x] Did not stage/modify `backend/src`, `frontend/src`, `ai-service/app`, `docker-compose.yml`, or any uncommitted AI2 files (verified via `git status --short`: they remain unstaged " M" / "??" exactly as before this session).
- [x] No commit, no push, no `git add -A`.

### Tests Status
- Type/lint check: N/A (single stdlib-only Python script, no project linter configured for `scripts/`)
- Unit tests: N/A (phase gate is the script itself, run directly — see RED/GREEN below)
- Integration tests: N/A (frontend suite explicitly marked N/A for this phase per phase doc — P1 does not touch `frontend/src`)

**RED (before implement) — `python scripts/check_repo_hygiene.py`, exit 1:**
```
FAIL: repo hygiene check failed:
  - expected `git ls-files apps/web/node_modules` to be empty, found 448 tracked file(s): [...]
  - expected `git ls-files apps/web/.vite` to be empty, found 2 tracked file(s): [...]
  - expected `git ls-files output` to be empty, found 15 tracked file(s): [...]
  - expected `git ls-files ocr-result.json` to be empty, found 1 tracked file(s): ['ocr-result.json']
  - expected `git ls-files result_khoiluong.json` to be empty, found 1 tracked file(s): ['result_khoiluong.json']
  - expected `git check-ignore -q node_modules/x` to succeed (ignored), got exit code 1
  - expected `git check-ignore -q output/foo` to succeed (ignored), got exit code 1
  - expected `git check-ignore -q ocr-result.json` to succeed (ignored), got exit code 1
  - expected `git check-ignore -q result_khoiluong.json` to succeed (ignored), got exit code 1
  - expected `git check-ignore -q .pytest-review-r2-ai2/x` to succeed (ignored), got exit code 1
  - expected `git check-ignore -q .uv-cache-x/y` to succeed (ignored), got exit code 1
  - expected `git check-ignore -q backend/backend/x` to succeed (ignored), got exit code 1
EXIT_CODE=1
```

**GREEN (after implement) — `python scripts/check_repo_hygiene.py`, exit 0:**
```
PASS: repo hygiene check passed (ls-files clean, check-ignore correct, files intact).
EXIT_CODE=0
```

### Issues Encountered
- None. Tracked-file counts matched the plan's pre-recorded baseline exactly (448 / 2 / 15 / 1 / 1), so no drift to reconcile.
- `git status` on this tree emits many `Permission denied` warnings for unrelated stale `ai-service/.pytest-*` and `tmp/ai2-*` directories owned by other in-progress work; these are pre-existing, outside this phase's scope, and did not affect the hygiene checks (they are separately covered by the new `.pytest-*` / `/tmp/` ignore patterns going forward).

### Five live paths — confirmed still on disk after untrack
Checked immediately before backup, and again after both `git rm --cached` invocations:
```
apps/web/node_modules exists: True
apps/web/.vite       exists: True
output               exists: True
ocr-result.json      exists: True
result_khoiluong.json exists: True
```
All five existed on disk before the backup/rm sequence and still exist on disk after. No `-f` was used anywhere; nothing was deleted from the working tree — only removed from the git index.

### No commit / no push
- Did not run `git commit`, `git push`, or `git add -A` at any point.
- `.gitignore` edit is an unstaged working-tree change (`git status` shows ` M .gitignore`, not staged).
- The 5 artifact-group removals are staged in the index as `D ` (cached delete) — that is the intended `git rm --cached` effect, left for `hs:cook`/the lead to commit as the dedicated hygiene commit.
- `scripts/check_repo_hygiene.py` is untracked (`??`), not staged.
- Verified via `git status --short` that no pre-existing product-source changes (`backend/src/**`, `frontend/src/**`, `ai-service/app/**`, `docker-compose.yml`, uncommitted AI2 files under `backend/src/contract_intelligence/extraction/application/dtos/ai2_analysis_dtos.py`, `frontend/src/components/DossierAnalysisPanel.tsx`, `frontend/src/pages/AnalysisCenterPage.tsx`, etc.) were touched, staged, or modified by this run — they remain exactly as they were before this session started.

### Next Steps
- Phase 2 depends on this phase's clean index + `backend/backend/` gitignore pattern; both are now in place for `test_repo_layout.py` to build on.
- The dedicated hygiene commit (index removals + `.gitignore` block + new script) is left uncommitted per instructions — `hs:cook`/lead should commit it as its own commit, separate from any logic change.
