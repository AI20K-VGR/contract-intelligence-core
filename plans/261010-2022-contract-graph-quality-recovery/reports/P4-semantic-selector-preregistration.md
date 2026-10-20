# P4 semantic selector diagnostic preregistration

Date: 2026-10-11

The user requested that the remaining recall blockers be resolved. This additional dev-only diagnostic is authorized as a scope extension and is preregistered before a live request:

- Run ID: `P4-semantic-selector-dev21-v1`
- Split: all 21 locked dev documents; no held-out access
- Requested model: `cx/gpt-5.5`
- Candidate output: at most 40 ranked pairs per document
- Budget: one HTTP request, 550 seconds, 500,000 tokens
- Use: measure semantic candidate recall before considering implementation
- Output: local ignored state only; pair IDs / aggregate metrics may be reported

This diagnostic does not count as classifier quality, does not lower any candidate or Wilson recall floor, and does not authorize runtime integration. Existing consent, citation, direction, span and duplicate-value safety gates remain required.
