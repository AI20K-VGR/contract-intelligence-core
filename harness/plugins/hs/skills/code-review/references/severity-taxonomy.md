---
name: severity-taxonomy
description: Severity levels and anti-slop taxonomy for hs:code-review
---

# Severity taxonomy and anti-slop

## Severity levels

| Level | Definition | Required action |
|---|---|---|
| **Critical** | Production bug, security vuln, data loss, breaking contract | Fix before merge — no exceptions |
| **Important** | Wrong logic, missing validation, structural slop, perf landmine | Should fix; if not, record reason in rationale |
| **Suggestion** | Style, micro slop, minor optimization | Nice-to-have; does not block |

Anti-slop severity rule: **structural** slop → Important; **micro** slop → Suggestion.

---

## Structural slop (Important)

Each instance below contaminates multiple files — always flag.

| Pattern | Signal | Fix |
|---|---|---|
| Dumping-ground file | New file under `utils/`, `helpers/`, `lib/common/`, `*manager.*` with no domain anchor | Rename to something domain-specific or move into the file that calls it |
| Parallel reimpl | New `formatDate()`, `slugify()`, HTTP retry when the repo already has one | Use the existing one; if it falls short, extend it, do not fork |
| Premature abstraction | Interface+factory+builder with 1 impl, 2 callers | Inline the concrete type; add the abstraction when a real second impl appears |
| Config flag instead of constant | `ENABLE_X`, `USE_NEW_Y` for behavior that should be hardcoded | Pick a value, hardcode it, remove the flag plumbing |
| Schema change without migration | NOT NULL column, renamed field, changed response shape — no migration/shim | Add a migration or deprecation path |
| God-file growth | File exceeds the project size limit (typically 200 LOC) in one PR | Split before merge |
| Phantom dependency | Dep added to manifest but diff does not import it, or import used for one call that stdlib already covers | Remove dep; inline the call or use stdlib |

---

## Micro slop (Suggestion)

Each instance is small — in aggregate they become rot.

| Pattern | Fix |
|---|---|
| Defensive paranoia — try/catch around non-throwing code; null check on a typed-non-null | Remove the guard; trust the types and stdlib |
| Catch-and-swallow — `catch (e) { log(e) }` or `except: pass` | Handle meaningfully or propagate |
| Comment paraphrase — `// increment counter` next to `counter++` | Remove; comments explain *why*, not *what* |
| Valueless one-line wrapper | Inline it; remove the wrapper |
| Stdlib reimpl — `chunk`, `range`, `groupBy` when stdlib/dep already provides it | Use stdlib/dep |
| Lint suppression — `@ts-ignore`, `# noqa`, `//nolint` to hide a warning | Fix the root cause; use suppression only with a comment explaining why the linter is wrong |
| Phantom test — assertion always passes, mock-of-mock does not verify real behavior | Assert actual values / side effects |
| Unused symbols — new import, export, param, or var that nobody uses | Remove |
| Magic numbers | Give them a named constant |

---

## Process slop (PR-level)

| Signal | Action |
|---|---|
| Title "fix typo" but diff is +800/−60 | Request split or rewrite of title/description |
| PR "fix auth" alongside an unrelated logging helper rewrite | Request separate PR |
| Production code changed with no test changes | Block until new path has test coverage |
| Doc describes a feature the diff does not implement | Remove aspirational doc or block for missing implementation |
| Commit message LLM-fluff ("improve code quality") | Informational — recommend conventional commits |

---

## When NOT to flag

Avoid witch-hunting. Flag only when you can state a **concrete cost**:

- Null check at a system boundary (API input, external response) is correct — not paranoia.
- A one-line wrapper that names a real domain concept has value.
- Try/catch around legacy code whose failure modes are not yet understood is a reasonable hedge.
- An intentional abstraction when a second impl is arriving in the next PR — ask, do not assume.
- A "thin" test may be a deliberate smoke test for a path that is difficult to test deeply.
- Magic numbers in tests are often more readable than a named constant.

**Rule of thumb**: if you cannot state a concrete cost, do not flag it.

---

## How to phrase a finding

**Good**: state the cost + alternative + acknowledge the judgment call.
```
"This abstraction has 1 caller and 1 impl — the indirection adds 15 lines of test
surface without enabling a second use-case. Recommend inlining until a second caller appears."
```

**Avoid**: "AI slop." / "Violates DRY." / "Please refactor." / "I don't like this."
