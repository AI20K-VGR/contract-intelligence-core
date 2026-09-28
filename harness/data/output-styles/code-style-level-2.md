---
name: professional (level 2)
description: Production-oriented code — proper types, error handling, design patterns named, trade-offs visible. Minimal hand-holding.
---

# Code Style Level 2 — Professional Code Register

This profile shapes generated CODE verbosity and format only.
It does NOT alter prose tone (see audience profiles) or evidence tokens.

---

## MANDATORY CODE DIRECTIVES

### Code Quality
1. Show production-quality code: proper types/interfaces, error handling, edge cases.
2. Use design patterns when they add value; name them.
3. Include type annotations where applicable.

### Comment Density
1. Comment only on non-obvious architectural decisions — not implementation details.
2. Self-documenting code is preferred over dense comments.

### Structure
1. Separate concerns clearly — each function/class does one thing.
2. Trade-offs visible: if a choice was made, a one-line comment names the reason.

### Growth Signals
1. Mention relevant patterns by name.
2. Briefly note alternative approaches where they exist.

---

## FORBIDDEN at this code level

1. NEVER explain basic programming syntax or fundamentals.
2. NEVER over-comment implementation-obvious lines.
3. NEVER show trivial examples — use realistic complexity.
4. NEVER alter prose paragraphs, evidence tokens, or file:line anchors.

---

## Worked Example (code register)

**Question:** "How should I handle API errors in my service layer?"

```python
def get_user(user_id: str) -> Result[User]:
    try:
        return Ok(api.get(f"/users/{user_id}").data)
    except TimeoutError:
        return Err("upstream_timeout", retryable=True)     # caller decides retry
    except ApiError as e:
        log.warning("get_user %s -> %s", user_id, e.code)
        return Err(e.code, retryable=e.code in RETRYABLE)
```

A Result type separates the happy path from failure; comments mark only the decisions.
