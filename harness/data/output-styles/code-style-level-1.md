---
name: guided-code (level 1)
description: Mentoring code style — explain the "why" before the "how", name patterns, moderate comments, link to docs.
---

# Code Style Level 1 — Guided Code Register

This profile shapes generated CODE verbosity and format only.
It does NOT alter prose tone (see audience profiles) or evidence tokens.

---

## MANDATORY CODE DIRECTIVES

### Explanation Order
1. Explain the WHY before showing the code (one sentence).
2. Name the pattern or technique being used ("We use the factory pattern here because…").

### Comment Density
1. Comment non-obvious logic — not every line, but any line a reader might question.
2. Keep comments focused on intent, not restatement.

### Block Size
1. Keep code blocks under 30 lines; split larger examples.
2. Show before/after comparisons when refactoring.

### Naming and Imports
1. Meaningful variable and function names that express intent.
2. Explain what each import/dependency does on first use.

### Teaching Elements
1. Note common mistakes at the call site ("Common pitfall: forgetting to await here").
2. Suggest what to try next at the end of each code section.

---

## FORBIDDEN at this code level

1. NEVER show advanced patterns without building up to them.
2. NEVER omit error handling from production examples.
3. NEVER alter prose paragraphs, evidence tokens, or file:line anchors.

---

## Worked Example (code register)

**Question:** "How should I handle API errors in my service layer?"

```python
def get_user(user_id):
    try:
        response = api.get(f"/users/{user_id}")   # call the upstream service
        return response.data
    except TimeoutError:
        # transient — the caller can retry
        return {"error": "upstream timed out"}
    except Exception:
        # unexpected — log and surface a safe message
        log.exception("get_user failed")
        return {"error": "could not load user"}
```

Comments explain the *why*, not every line — the reader knows basic control flow.
