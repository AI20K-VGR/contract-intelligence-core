---
name: review-dimensions
description: Review dimension checklist for the code-reviewer agent — correctness, security, performance, maintainability, testing, anti-slop
---

# Review dimensions

Full checklist for the Stage 2 quality review. The `hs:code-reviewer` agent loads this file during review; each dimension is an independent lens — no lens is skipped even when the diff is small.

---

## 1. Correctness

- Logic errors, off-by-one, nil/null dereference without a guard
- Missing error handling or swallowed errors
- Race conditions in concurrent code
- Unhandled edge cases (empty list, zero, max value, concurrent writes)
- API contract mismatch: caller assumption does not match callee guarantee (nullability, shape, timing)
- Backwards compatibility: silent breaking change in exported interface, DB schema, config format, or response shape

**Supplemental behavioral checklist (agent self-checks before submitting):**
- [ ] Concurrency: race condition, shared mutable state, async ordering
- [ ] Error boundaries: exception caught-and-handled or propagated explicitly
- [ ] API contracts: caller/callee assumptions match
- [ ] Backwards compat: no silent breaking change
- [ ] Fact-checked (when plan exists): file path, symbol name, and claims in plan
      verified via grep — do not assume from plan text

---

## 2. Security

- Injection: SQL, XSS, command injection, SSRF, path traversal
- Hardcoded secrets or credentials in the diff
- Missing input validation at system boundaries (not only at the UI layer)
- Authentication/authorization gap: sensitive operation must check both identity AND permission, not just one
- Data leaks: PII, secrets, internal stack traces reaching an external consumer

**Trust-boundary checklist:**
- [ ] External inputs validated before use
- [ ] Auth + authz check complete on every sensitive path
- [ ] No PII/secret in logs or responses

---

## 3. Performance

- N+1 query: unbounded loop calling DB/service
- Missing index on a hot filter/order column
- Unbounded memory growth (append in loop, load entire collection)
- Incorrect async handling: blocking call in async context, missing await
- Incorrect or absent cache invalidation

---

## 4. Maintainability

- Readability: intent is clear without reading the implementation
- Modularity: SRP — module/file does one thing
- Naming: file/module/function names accurately describe actual responsibility
- File size: exceeds project limit (typically 200 LOC in one PR) → flag

**Anti-slop structural patterns (Important):**

| Pattern | Signal |
|---|---|
| Dumping-ground file | New file under `utils/`, `helpers/`, `*manager.*` with no domain anchor |
| Parallel reimpl | Function already exists in repo; a copy is added |
| Premature abstraction | Interface+factory+builder with 1 impl, ≤2 callers |
| Config flag vs constant | `ENABLE_X` for behavior that should be hardcoded |
| Schema/contract change without migration | NOT NULL column, field rename, response shape change |

**Anti-slop micro patterns (Suggestion):**

Defensive paranoia · catch-and-swallow · comment paraphrase · valueless one-line wrapper
· stdlib reimpl · lint suppression (`@ts-ignore`, `# noqa`) · phantom test coverage · unused symbols · magic numbers

Full taxonomy + how to phrase findings: `references/severity-taxonomy.md`.

---

## 5. Testing

- Does the new path have test coverage?
- Do existing tests still pass?
- Are edge cases tested?
- Phantom coverage: assertion that is always true, mock-of-mock that does not verify real behavior
- Production code changed without test changes → block

---

## 6. Project-specific compliance

Read before reviewing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/harness-contract.md`.

Context (not a gate): `docs/code-standards.md` is prose, loaded for orientation only. Its ENFORCEABLE directives live as layer-b rules under `docs/standards/` (the `rule-scan` already checks them) — do not treat the prose doc itself as a pass/fail gate.

Check the diff against project conventions:
- Architecture pattern (append-only JSONL, actor+ts record, fail-closed gate)
- HOOK_CLASS constant in hook files
- Store: append-only, no RMW
- Human-editable config = YAML; machine-written data = JSON/JSONL
- Wording invariants (harness-contract.md)
- Conventional commits, no AI references in messages

---

## 6a. Architecture (structural diffs only)

When the diff is **structural** — it intersects `standards.yaml drift.structural_globs` (the shipped generic set, or a repo's `.harness-dev` override) — load `docs/system-architecture.md` and judge whether the change respects the described component map, layer boundaries, and store & hook contracts.

- Does the change place code in the layer the component map assigns it to (hook ≠ lib ≠ CLI; a compliance gate fails closed, telemetry/nudge fail open)?
- Does it cross an import boundary the architecture forbids (e.g. a hook importing skill code, or the harness `ref`-ing a `.claude/` runtime path)?
- Does it change a store contract (append-only JSONL, actor+ts) or a gate posture the doc documents?
- Did an architecture-bearing change land with `docs/system-architecture.md` / `docs/code-standards.md` untouched (stale-map risk)?

Record the judgment as `architecture_review{checked, doc_sha, drift[]}` in `review-decision.json`. This is a **presence gate**: `artifact_check` blocks a hard stage when a structural diff carries no `architecture_review.checked==true`. The `doc_sha` is audit-only — never sha-matched at ship, so doc churn does not invalidate a passing review.

---

## 7. Named footgun angles (recall lenses)

High-recall reviews (effort ≥ medium) spawn these as named lenses — each hunts a failure mode the happy-path review and the author both tend to miss:

| Angle | What it hunts |
|---|---|
| **Removed-behavior auditor** | A deleted/short-circuited branch, guard, or validation. Every removed line is a behavior change until proven dead — diff the BEFORE behavior, not just the AFTER. |
| **Cross-file tracer** | Trace both directions: every **caller** of a changed signature/contract (does the new shape break them?) AND every **callee** the change now relies on (does it actually guarantee what the caller assumes?). Depth-1 minimum. |
| **Wrapper/proxy correctness** | A wrapper, adapter, decorator, or proxy that silently drops an argument, swallows an error, changes defaults, or fails to forward a new param of the thing it wraps. |
| **Language-pitfall** | Language-specific traps: truthiness/`0`/`""`/`None` confusion, mutable default args, integer division, float compare, off-by-one, async/await dropped, shadowed builtins, `==` vs `is`. |

These reuse existing agents (no new lens agent) — see `references/recall-mode.md`.

## When to load the full checklist

- Diff ≥ 10 files, OR
- ≥ 2 anti-slop signals detected, OR
- PR creates ≥ 2 new files in dumping-ground dirs, OR
- A security-sensitive path is modified

Below these thresholds: quick scan across all 6 lenses, flag per severity taxonomy.
