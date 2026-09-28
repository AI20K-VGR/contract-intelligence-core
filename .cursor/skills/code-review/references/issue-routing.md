---
name: issue-routing
description: Taxonomy and procedure for routing code-review findings to BACKLOG (needs-user) vs hs:fix (auto-fix)
---

# Issue routing — finding category → handling route

Within each review round, every confirmed finding is classified by category before acting. The classifier (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_issue_router.py`) returns one of two routes:

- **`needs-user`** — the finding touches a user decision. Do NOT auto-fix. Escalate.
- **`auto-fix`** — the finding is a clear correctness or quality issue. Drive `hs:fix`.

This concretises the review-discipline rule
**"User decisions are not silently undone"** (threshold / library / scope / schema / pricing / compliance / UX trade-off): when a finding would reverse one of those decisions, the agent must surface it to the human and wait, never apply the change silently.

---

## Category taxonomy

| Category | Route | Reason |
|---|---|---|
| `contract` | `needs-user` | API surface / interface agreement — a change breaks callers the reviewer cannot audit |
| `threshold` | `needs-user` | Numeric limit, coverage floor, budget cap — user-set and intentional |
| `scope` | `needs-user` | Which files / modules / services are in or out — a policy decision |
| `schema` | `needs-user` | Data shape, field names, types — downstream consumers depend on these |
| `pricing` | `needs-user` | Cost model, tier boundary, billing rule — business decision |
| `compliance` | `needs-user` | Regulatory / legal / security-policy requirement — cannot be self-decided |
| `trade-off` | `needs-user` | Explicit design trade-off (latency vs throughput, accuracy vs speed) — user chose |
| `correctness` | `auto-fix` | Code does the wrong thing vs its own spec — safe to fix TDD |
| `bug` | `auto-fix` | Defect causing incorrect behaviour — safe to fix TDD |
| `dry` | `auto-fix` | Duplication that a refactor eliminates without behaviour change |
| `cleanup` | `auto-fix` | Dead code, unused imports, formatting — no behaviour change |
| `consistency` | `auto-fix` | Naming / style diverges from the surrounding pattern |
| `security` | `auto-fix` | Clear vulnerability with a correct fix (e.g. injection, secret in log) |
| `robustness` | `auto-fix` | Unhandled error / edge case where the correct handler is unambiguous |
| `edge` | `auto-fix` | Missing edge-case coverage with a clear correct value |
| `test-quality` | `auto-fix` | Test is weak, brittle, or misleading — safe to tighten |
| *(unknown)* | `needs-user` | Safe default: an unrecognised category is escalated, never auto-fixed |

Run the classifier:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_issue_router.py --category <category>
```

---

## Round procedure

For each confirmed finding in a review round:

1. **Classify** the finding: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_issue_router.py --category <cat>`
2. Branch on the returned route:

### `needs-user` path

The finding is NOT applied. Escalate to the human.

- **Interactive session**: call `AskUserQuestion` with the finding title, the impacted user decision, and the options (fix as suggested / keep as-is / alternative). Wait for the answer before proceeding. Do not apply the change speculatively.
- **Headless / no-TTY**: record the finding through the backlog register at the repo root:

  ```
  python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/backlog_register.py add \
    --text "<title>: <one-sentence description> — report: plans/reports/<report-file>" \
    --type review --priority <P0|P1|P2|P3>
  ```

  The text must include a link to the review report under `plans/reports/` so the human has full context when they pick it up. Do NOT create a standalone report file for this entry alone — the review report IS the context.

In both cases: record the finding and its route in the review report under `plans/reports/`. Never silently drop a `needs-user` finding.

### `auto-fix` path

The finding is actionable without user input. Apply it:

1. Write a failing test that pins the correct behaviour (red).
2. Implement the fix until the test passes (green).
3. Commit the test + fix pair: `fix(<scope>): <description>` — conventional commit, no AI references, no plan/phase labels.
4. Continue the review round.

The existing `hs:fix` TDD path (`recall-mode.md` fix axis) drives this. The fix is committed only when its test is green; a partial or speculative edit is never committed.

---

## Safe-default guarantee

Any category not in either taxonomy table resolves to `needs-user`. This guarantees that a reviewer adding a new category cannot accidentally route it to `auto-fix` before the table is updated and reviewed. Unknown = escalate.
