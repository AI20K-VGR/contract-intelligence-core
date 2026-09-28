# Risk ceremony

A diff that touches auth, a schema migration, secret handling, or a public API contract is high-risk no matter how small. The risk rubric derives a tier from the changed files and the cook/review skills enforce the matching ceremony.

## Derive

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/risk_rubric.py --root . <changed_file> [<changed_file> ...]
```

Returns `{tier, gates_hit, flags, ceremony}`:
- `tier` — `tiny` | `normal` | `high_risk`
- `gates_hit` — hard gates the diff tripped (auth/migration/secret/api_contract)
- `ceremony` — `{require_plan, require_security_scan, require_non_author_review}`

## Enforce (skill-level, v1)

When `tier == high_risk` (or `ceremony.require_security_scan`):

1. Run `hs:security-scan` and ensure a `security-scan.json` artifact exists with verdict PASS.
2. Confirm the reviewer is **not** the author before writing the review verdict.
3. Require an active plan (`require_plan`).

When `tier == normal`: require a plan; quick review is enough. When `tier == tiny`: lightweight review, no extra ceremony.

## Boundary (read this before claiming a guarantee)

This is **skill-enforced**, not a hard gate. `security-scan` is not in any stage's `stage-policy.yaml requires:`, so a high-risk change *can* reach a stage gate without a security-scan artifact if the skill step is skipped (the same accepted AI-applied gap as the review-rules layer). Do not describe the ceremony as a guarantee. The v2 cutline (deferred): have the rubric append `security-scan`
to a high-risk stage's effective `requires:` so the gate enforces it. The rubric is off-switchable (`enabled: false` in `"${HARNESS_BIN_ROOT:-.}"/harness/data/risk-rubric.yaml`).

