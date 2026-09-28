---
name: eli5 (level 0)
description: Maximum hand-holding for generated code — every line commented, tiny blocks, expected output shown, beginner-safe naming.
---

# Code Style Level 0 — ELI5 Code Register

This profile shapes generated CODE verbosity and format only.
It does NOT alter prose prose tone (see audience profiles) or evidence tokens.

---

## MANDATORY CODE DIRECTIVES

### Comment Density
1. Add a comment explaining what EVERY single line does.
2. Use plain English in comments — no jargon, no abbreviations.
3. The comment MUST say WHY, not just what the line is (e.g., not just `# assign x`).

### Block Size
1. Keep code blocks to 5–10 lines maximum.
2. Break larger examples into numbered steps, each shown and explained separately.
3. Show the expected output / return value after EVERY block.

### Naming
1. Use long, self-describing variable names (`numberOfApples`, not `n`).
2. Avoid single-letter names except universally understood loop counters (`i`, `j`).

### Structure
1. Start with the simplest possible version; add complexity gradually.
2. End each code section with: "Try changing X to see what happens!"

---

## FORBIDDEN at this code level

1. NEVER show a block longer than 10 lines without a mid-block explanation.
2. NEVER use unexplained abbreviations in names.
3. NEVER skip showing expected output.
4. NEVER alter prose paragraphs, evidence tokens, or file:line anchors.

---

## Worked Example (code register)

**Question:** "How should I handle API errors in my service layer?"

```python
# We call another service that can fail, so we handle every case carefully.
def get_user(user_id):
    try:
        # Ask the API for the user
        response = api.get(f"/users/{user_id}")
        return response.data          # It worked — hand back the data
    except TimeoutError:
        # The service was too slow — tell the caller kindly, do not crash
        return {"error": "The service is slow right now, please try again."}
    except Exception:
        # Anything else went wrong — still return something friendly
        return {"error": "Sorry, we could not load that user."}
```

Every line is commented because at this level we are learning what each part does.
