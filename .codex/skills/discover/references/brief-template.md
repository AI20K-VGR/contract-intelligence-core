# Brief template — discovery brief

Use this template in step 4 of hs:discover. Save to `plans/<slug>/discovery-brief.md`. Do not create markdown files outside `plans/` (CI invariant, `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`).

## Slug convention

`<YYYYMMDD>-<3-5-word-kebab>-discovery` — example: `20260615-cache-invalidation-discovery`.

---

## Template

```markdown
# Discovery Brief — <problem / feature name>

**Date:** <YYYY-MM-DD>
**Status:** draft | finalized

---

## 1. Problem framing

> Short description: what is the problem, who is affected, why it needs to be solved.
> No more than 5 sentences.

**Root cause (if known):**
**Current impact:**
**Deadline / urgency:**

---

## 2. Hard constraints

| Constraint | Type | Notes |
|---|---|---|
| (example: must be compatible with Python >=3.10) | technical | |
| (example: no external dependencies) | policy | |

---

## 3. Evidence summary

**Research report:** `<absolute path plans/reports/...>` _(or [SKIPPED --quick])_

Key findings in 3-5 bullets:
- ...

---

## 4. Option space

| # | Approach | Pros | Cons | Complexity |
|---|---|---|---|---|
| A | ... | | | low/medium/high |
| B | ... | | | |

---

## 5. Chosen direction + rationale

**Chosen direction:** Option <X> — <short name>

**Why:**
1. ...
2. ...

**Accepted trade-off:**
- Trade-off: ... because ...

**DEC recorded:** <ID if applicable, or "none — not an architectural call">

---

## 6. Open questions

> Questions without answers yet — must be answered before or during planning.

- [ ] ...
- [ ] ...

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ... | high/medium/low | ... | ... |

---

## 8. Explicitly OUT of scope

- Not doing: ...
- Not doing: ...

_(Everything not listed here is undecided, not approved.)_

---

## Handoff -> hs:plan

This brief is input for `hs:plan`. When calling plan:
```
/hs:plan <absolute-path-to-this-brief>
```
Remember `/clear` first to avoid planning-carryover bias
(`"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` #5).
```

---

## Checklist before marking "finalized"

- [ ] Problem framing clear: who, what, why
- [ ] Hard constraints fully listed
- [ ] Evidence summary has report link (or [SKIPPED])
- [ ] Option space has >=2 directions (except --quick single-option)
- [ ] Chosen direction has rationale, not just an empty preference
- [ ] Open questions listed — do not pretend everything is known
- [ ] OUT of scope clearly stated — prevents scope creep into planning
