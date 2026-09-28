# Project-specific compliance rules — worked example

> **This pattern is now structured.** The review-rules layer (`code-review/references/review-rules-layer.md`) loads diff-applicable rules from the operational standards tree (`harness/standards/areas/*.std.yaml`, `zone: operational`) and writes `rule-scan.json`. Add a per-repo rule via the rule-author skill (writes `standards.user.yaml`). File kept as worked example of the rule shape.

The project-context step ("### 2. Read project context") in SKILL.md is intentionally generic — each project has its own architecture patterns, ID conventions, SQL store rules, and UI rules.

This file is a **worked example** from a production project (Go gateway + React/Tailwind admin UI) showing how to encode project-specific reviewer rules. **Copy this pattern into your project docs** (e.g. `docs/code-standards.md`, `CLAUDE.md`), reference it from your project's review instructions.

Reviewers must adapt these rules to *your project* — don't flag PRs in an unrelated codebase for not following the conventions shown here.

---

## Example: Architecture patterns

**Cache invalidation MUST use the pubsub pattern**:

```go
msgBus.Broadcast(bus.Event{
    Name:    protocol.EventCacheInvalidate,
    Payload: bus.CacheInvalidatePayload{Kind: ..., Key: ...},
})
```

Don't thread a direct reference to the cache struct (e.g. `*ContextFileInterceptor`) through constructors. The subscriber in `cmd/gateway_managed.go` dispatches to the correct cache layer.

**Why project-specific**: the violation still works locally (cache clears) but breaks multi-instance (only the instance that received the request clears its cache). The pubsub pattern fans out across the message bus.

**Lesson**: identify patterns where the "obvious" implementation works in dev but breaks in prod. Encode them.

---

## Example: ID scoping

`store.UserIDFromContext(ctx)` returns a **different value** by context:
- **In DM**: individual user ID (`"123456"`)
- **In group chat**: group-scoped compound ID (`"group:telegram:-1002541239372"`)

The individual sender is available separately via `store.SenderIDFromContext(ctx)`.

When reviewing code using UserID, verify:
1. Correct ID type for the purpose — `UserID` for scoping/isolation, `SenderID` for identifying the actual person
2. Group chat behavior correct — all group members share the same UserID
3. Code filtering/storing by `user_id` works correctly with the `"group:channel:chatID"` format

**Lesson**: if IDs change shape by context, document it here. A reviewer can't catch this from a diff alone.

---

## Example: SQL store safety

When a PR touches `store/pg/*.go`, migrations, or any DB query:

- User input MUST use parameterized queries (`$1, $2, ...`) — no string concatenation or `fmt.Sprintf` for SQL values
- Queries MUST be optimized — no N+1, no unnecessary full table scans
- Columns in WHERE, JOIN, ORDER BY MUST use an existing index — cross-check with migration files
- `rows.Err()` MUST be checked after every `for rows.Next()` loop (Go `database/sql`)
- Nullable columns MUST use pointer types (`*string`, `*time.Time`) in Scan destinations

**Lesson**: SQL store conventions are the highest-leverage place to encode rules — bugs here cost prod data.

---

## Example: i18n compliance

- New user-facing strings in Go code MUST use `i18n.T(locale, i18n.MsgXxx, args...)` — do not hardcode English in error responses
- New user-facing strings in React MUST use `t("namespace.key")` via `useTranslation()`
- New i18n keys MUST be added to ALL 3 locale files (en, vi, zh) for both backend (`internal/i18n/catalog_{en,vi,zh}.go`) and frontend (`ui/web/src/i18n/locales/{en,vi,zh}/`)
- `slog` messages and `console.log` stay in English (internal logs, not user-facing)

**Lesson**: if you support multiple locales, "added a string in English only" is a regression. Encode the catalog paths.

---

## Example: Web UI compliance (React + Tailwind + Radix)

When a PR touches the web UI:

- `h-dvh` MUST be used instead of `h-screen` — `h-screen` breaks on mobile (content hidden behind browser chrome / virtual keyboard)
- All `<input>`, `<textarea>`, `<select>` MUST use `text-base md:text-sm` (16px on mobile) — font-size <16px triggers iOS Safari auto-zoom
- Edge-anchored elements MUST use `safe-top`, `safe-bottom`, `safe-left`, `safe-right` for notched devices
- Icon buttons MUST have >=44px touch target on touch devices
- `<table>` MUST be wrapped in `<div className="overflow-x-auto">` with `min-w-[600px]` on the table
- Grid layouts MUST be mobile-first: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-N`
- Dialogs: full-screen on mobile (`max-sm:inset-0`), centered on desktop (`sm:max-w-lg`)
- Scrollable areas MUST use `overscroll-contain` to prevent background scroll bleed
- Portal dropdowns inside dialogs using `createPortal` MUST add `pointer-events-auto`
- Charts MUST use `formatBucketTz()` from `lib/format.ts` with `Intl.DateTimeFormat` — no `date-fns-tz` dependency
- Package manager: MUST use `pnpm` (not `npm`) for `ui/web/`
- File size: component files should stay under 200 lines — split if exceeded

**Lesson**: encode mobile-first conventions, a11y minimums, safe-area handling, package-manager rules — easy to forget, tedious to enforce manually.

---

## How to encode project-specific rules in your repo

1. Write rules in your project's `docs/code-standards.md` or `CLAUDE.md`
2. Reference them from your project's review instructions
3. Update when patterns change — stale rules generate false-positive findings
4. Cross-check: when a reviewer cites a rule, the referenced path/file must still exist — move it with the code.

A reviewer is only as good as its rules. Invest here.
