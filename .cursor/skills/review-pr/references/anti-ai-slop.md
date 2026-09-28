# Anti-slop taxonomy — load-bearing reference

Concrete taxonomy of slop patterns that LLM-assisted PRs commonly introduce. Load when: diff >300 lines, >=2 inline flags in SKILL.md are triggered, or the PR creates >2 new files in `utils/`/`helpers/`.

---

## Section 1: Structural slop -> flag **Important**

One bad call here infects many later files. Always flag.

### 1.1 Dumping-ground new files
**Pattern**: New file at `utils/helpers.ts`, `lib/common/index.ts`, `services/manager.ts`.
**Problem**: A generic name means no domain anchor. The next agent dumps more into it.
**Detection**: `git diff --name-status --diff-filter=A` for new files with generic names.
**Fix**: Rename by domain (`token-bucket-rate-limit.ts`), or move the function into its single caller file.

### 1.2 Parallel reimplementation
**Pattern**: New `formatDate()` / `slugify()` / HTTP retry wrapper when the repo already has one.
**Problem**: Two implementations diverge over time — a bugfix in one won't reach the other.
**Detection**: Grep the repo for the function name or similar behavior before approving a new utility.
**Fix**: Use the existing one. If it is insufficient -> extend, do not fork.

### 1.3 Premature abstraction
**Pattern**: Interface + factory + builder + adapter for a feature with 1 implementation and <=2 callers.
**Problem**: Abstraction cost (indirection, mental load, test surface) is paid before any payoff.
**Detection**: Count concrete implementations of the new interface. 1 = premature.
**Fix**: Inline the concrete type. Add the abstraction when a second implementation actually appears.

### 1.4 Config flag for a constant
**Pattern**: Env var or config field `ENABLE_X`, `USE_NEW_Y` for behavior that should be hardcoded.
**Problem**: Never gets turned off — becomes doc lag + foot-gun.
**Detection**: For any new config field, ask "will this ever be flipped in production? If not, why does it need a flag?"
**Fix**: Pick a value, hardcode it. Remove the flag plumbing.

### 1.5 Schema/contract change without migration
**Pattern**: PR adds a NOT NULL column, renames a field, or changes a response shape — with no migration and no shim.
**Problem**: Breaks deployed clients or existing data.
**Detection**: Diff touches a DB schema, API DTO, public type, or persisted config format.
**Fix**: Add a migration, deprecation path, or versioned contract.

### 1.6 God-file growth
**Pattern**: A 180-line file grows to 450 in a single PR. Exceeds the project's size limit.
**Problem**: File becomes unreadable, context load expensive, next agent has less working room.
**Detection**: `wc -l` on modified files in the diff vs. the project's size convention.
**Fix**: Split before merging. Group related additions into a new, focused module.

### 1.7 Phantom dependencies
**Pattern**: `package.json`/`go.mod`/`requirements.txt` adds a dep — but the diff does not actually import it, or imports it for a single call that stdlib already covers.
**Problem**: Supply chain risk, install size, transitive vulnerability — for nothing.
**Detection**: Cross-check dep additions with actual `import`/`require` lines in the diff.
**Fix**: Remove the dep, inline the trivial call, or use stdlib.

---

## Section 2: Micro slop -> flag **Suggestion**

Does not block merge, but call it out. Aggregate is rot.

### 2.1 Defensive paranoia
`try/catch` wrapping code that cannot throw. Null check on a typed-non-null param.
**Fix**: Remove the guard. Trust types and stdlib.

### 2.2 Catch-and-swallow
`catch (e) { console.log(e) }`, `catch { return null }`, `except: pass`.
**Fix**: Handle meaningfully (retry, fallback, user message) or propagate. Log-and-continue is a bug factory.

### 2.3 Comment paraphrase
`// increment counter` next to `counter++`. `// returns the user's name` above `getUserName()`.
**Fix**: Remove it. Comments should explain *why*, not narrate *what*.

### 2.4 Generic error messages
`"An error occurred. Please try again."`, `throw new Error("Failed")`.
**Fix**: Include operation, inputs, failure mode. `"failed to fetch user %d: %w"`.

### 2.5 One-line wrappers
`function getName(u) { return u.name }`. Adds indirection, hides nothing.
**Fix**: Inline it. Remove the wrapper.

### 2.6 Reimplementing stdlib
Custom `chunk`, `range`, `groupBy`, `debounce`, `deepEqual` when stdlib/dep already covers it.
**Fix**: Use stdlib/dep.

### 2.7 Silencing the linter
`any` widening, `@ts-ignore`, `@ts-expect-error`, `// eslint-disable`, `# noqa` added to hide a warning instead of resolving it.
**Detection**: `git diff | grep -E '^\+.*(any|@ts-ignore|@ts-expect-error|eslint-disable|noqa|nolint)'`
**Fix**: Resolve the underlying issue. Only use with a comment explaining why the linter is wrong.

### 2.8 Phantom test coverage
Test exercises lines without a meaningful assertion: `expect(result).toBeTruthy()` on a value that is always truthy.
**Fix**: Assert actual behavior — value, side effect, error.

### 2.9 Mock-of-a-mock
80% of the setup is mocks; the assertion verifies the mock was called — not that the SUT did the right thing.
**Fix**: Use the real implementation when possible. Mock only at integration boundaries.

### 2.10 Unused symbols
New imports, exports, params, or variables in the diff that nothing references.
**Detection**: Language linter (`tsc --noUnusedLocals`, `go vet`, `pyflakes`, `ruff`).
**Fix**: Remove them.

### 2.11 Magic numbers
`if (retries > 7)`, `setTimeout(fn, 3600000)`.
**Fix**: Name the constant. `const MAX_RETRIES = 7`.

### 2.12 Style inconsistency
New code uses arrow functions / camelCase / a different formatter than the rest of the file.
**Fix**: Match the surrounding file.

---

## Section 3: Process slop — look at the whole diff

### 3.1 Scope mismatch
PR title says "fix typo" but diff is +800/-60 across 12 files — author didn't watch the agent, or title is wrong.
**Action**: Request the PR be split into focused commits, or the title/description rewritten.

### 3.2 Unrelated files
A "Fix auth bug" PR also rewrites a logging helper + reorders imports in 5 unrelated files.
**Action**: Request the unrelated changes moved to a separate PR.

### 3.3 Tests missing or skipped
Production code changes; no test changes. Or existing tests have `it.skip()` / `t.Skip()` / `@pytest.mark.skip` on tests that were previously passing.
**Action**: Block until tests cover the new path, or the skip is justified in PR description.

### 3.4 Docs claim features that do not exist
A README, changelog, or doc update describes behavior that is not implemented.
**Action**: Remove the aspirational docs, or block — implementation incomplete.

### 3.5 LLM-style fluff in commit messages
"Improve code quality and enhance maintainability", "Refactor for clarity", "Update various files".
**Action**: Informational. Suggest conventional-commits format with the actual change described.

---

## Section 4: Phrasing findings

**Good**:
- "This abstraction has 1 caller and 1 implementation — the indirection adds 15 lines of test surface without enabling a second use case. Consider inlining until a second caller appears."
- "Naming the file `utils/helpers.ts` invites future additions. Files like this commonly grow to 1000+ lines. Rename to `<domain-specific-name>.ts`."
- Offer an alternative. Do not just flag — say what good looks like.
- "This is a Suggestion, not a blocker. If you have a use case for a second implementation, keep it."

**Bad**:
- "This is AI slop." — accusatory, unhelpful, often wrong.
- "This violates DRY/YAGNI/SOLID." — state the concrete cost instead of invoking a principle.
- "Please refactor." — vague. Refactor *how*?

---

## Section 5: When NOT to flag

Witch-hunting is the opposite failure mode. Calibrate:

- **Null checks at system boundaries** (API input, external response) are correct — do not flag them as paranoia.
- **One-line wrappers** can be worth it when they name a domain concept. `isWeekend(d)` is fine.
- **Try/catch around legacy code** with unknown failure modes is a reasonable hedge while the code is being understood.
- **Intentional abstraction** when the author knows a second implementation is coming in the next PR. Ask, do not assume.
- **Verbose error messages** are appropriate at log/user boundaries.
- **Repetitive code** is fine when the alternative (abstraction, metaprogramming) costs more than the duplication. Rule of three.
- **Magic numbers in tests** are often more readable than named constants.

Rule of thumb: if you cannot articulate a **concrete cost** for the pattern in this codebase -> do not flag.

---

## Section 6: Stack-specific appendix

### 6.1 Go
- `fmt.Errorf("doing X: %w", err)` wrapping with `%w` preserves the chain. `%v` *loses* it. Flag the latter.
- `if err != nil { return err }` is canonical Go — **do not** flag as defensive paranoia.
- `interface{}` / `any` param when a concrete type would suffice -> flag.
- `for rows.Next()` loop missing `rows.Err()` check — required by `database/sql`. Bug, not slop.
- Goroutine launched without a lifetime owner (no `context`, no `wg`, no channel return) — leak risk.
- Mutex by value embedded in a struct that gets copied — silent data race.

### 6.2 React / TypeScript
- `useEffect` with empty deps doing data fetching — usually want `useEffect` + `AbortController`, or the project's data-fetch lib.
- `useState` for derived state should be a memoized computation.
- Inline anonymous functions in props are usually fine — do not flag as a performance issue unless profiling shows it.
- `any` in component props — flag. Components are the public contract of the UI layer.
- New context provider for state that 2 siblings share — premature.
- Component file >200 lines mixing data fetching + business logic + rendering — split.

### 6.3 Tailwind / CSS
- Arbitrary values (`h-[473px]`, `text-[#3a5b71]`) — use design tokens instead.
- `!important` to override — almost always wrong; find the source of the cascade conflict.
- `h-screen` on mobile-facing UI — breaks on iOS Safari. Prefer `h-dvh`.
- Fixed `grid-cols-N` without a mobile breakpoint — use `grid-cols-1 sm:grid-cols-2 lg:grid-cols-N`.
- `<input>` with `text-sm` only — font-size <16px triggers iOS Safari auto-zoom. Use `text-base md:text-sm`.

### 6.4 SQL / migrations
- String concatenation building SQL with user input — injection. Always parameterize.
- `SELECT *` in production queries — fragile, fetches unused columns.
- Non-idempotent migrations — use `IF NOT EXISTS` / `IF EXISTS`.
- NOT NULL column added without a DEFAULT or backfill — breaks deployed code.
- Index on a low-cardinality column without justification — wasteful.
- `ORDER BY` / `WHERE` on an unindexed column in a hot query — performance landmine.

---

## How to use this reference

1. Read the relevant section per the slop signals from SKILL.md's inline checklist.
2. Match the pattern to a section here.
3. Use the phrasing guide (Section 4) to write the finding.
4. Apply the severity rule: structural (§1, §3) -> Important; micro (§2) -> Suggestion.
5. If unsure whether to flag -> re-read Section 5 first.
