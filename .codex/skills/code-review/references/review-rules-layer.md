# Review-rules layer

The structured rule layer the reviewer applies to a diff. It replaces the old "read a prose project-rules file and eyeball it" step with a loader selecting exactly the rules that apply to changed files, plus an artifact recording what was checked and found.

## When it runs

Inside `hs:code-review` (and `hs:review-pr`) after the edge-case scout and before the verdict. It does not replace the quality review — it adds a rule-driven pass whose result feeds the verdict.

## Steps

1. **Collect changed files** from the diff being reviewed:
   - `--pending` → `git diff --name-only` (staged + unstaged)
   - PR → `gh pr diff <n> --name-only`
   - commit → `git show --name-only --format= <sha>`

2. **Load the applicable rules** from the operational standards tree:
   ```python
   from rule_view import load_rules_dual
   result, source = load_rules_dual(root, changed_files)
   ```
   Returns `{rules, rules_applied, langs}` (`source` is `tree`, or `tree-error` if the consumer failed — fail-soft, never blocks the review). `rules` carries each operational rule-leaf's fields (scope/severity/enabled/detector + description/rationale — the ALWAYS/NEVER/PREFER directives to check). The consumer reads the std SSOT tree (`harness/standards/areas/*.std.yaml`, `zone: operational`),
   applies any `standards.user.yaml` per-repo overrides, keeps only enabled rules, and selects those whose scope intersects the diff (language is derived from scope, not a stored field).

3. **Judge each applied rule against the diff.** For each rule, read its body and check the changed lines against its directives. Record every violation as:
   ```json
   {"rule_id": "STD-REVIEW-COMMON-RG1-R2", "severity": "critical", "file": "app/log.py",
    "line": 42, "finding": "logs an auth token", "directive": "NEVER log secrets/tokens"}
   ```
   `directive` is optional but preferred — `rule_id` is file-level and a rule body holds many directives, so citing the exact one makes the finding auditable.

4. **Write the artifact** `plans/<active-plan>/artifacts/rule-scan.json` via `rule_view.build_rule_scan(root, changed_files, violations=...)` (it records `rules_applied`, derives the verdict, stamps reviewer/ts, and writes
   `changed_files` — the coverage-gate's only diff source). Schema:
   `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-rule-scan.json`:
   ```json
   {"rules_applied": ["STD-REVIEW-COMMON-RG1-R2","STD-REVIEW-PY-RG1-R1"],
    "violations": [ ... ],
    "verdict": "BLOCKED",
    "reviewer": "user:<actor>",
    "ts": "<iso8601>",
    "changed_files": ["app/log.py"]}
   ```

5. **Set the verdict from severity**:
   - any violation with `severity: critical` → scan verdict `BLOCKED`, and the
     `review-decision.json` verdict is also `BLOCKED`.
   - only `info` violations → `PASS_WITH_RISK` (surface them as Suggestions).
   - no violations → `PASS`.

## Gate interaction

`rule-scan.json` is **not** a required gate artifact (it is never in any stage's `requires:`). But when it is present, the stage gate (`artifact_check._rule_scan_consistency`) validates it (severity + verdict enums, fail-closed on an off-enum value) and refuses a contradiction: if any violation is `critical`, the rule-scan's own `verdict` must be `BLOCKED` AND a present `review-decision` must
not be `PASS`/`PASS_WITH_RISK`. So a critical finding must be carried through to both verdicts — you cannot record it and still pass.

## Layer-b: per-repo architecture / standards invariants

Beyond the shipped operational tree, a repo's OWN architecture and code-standards invariants live as layer-b rules under `docs/standards/` (the `user_rules_dir`). `load_rules_dual` already merges them, so the rule-scan above checks them too — this is how a repo enforces its `docs/system-architecture.md` / `docs/code-standards.md` directives without shipping them onto every installer.
Doc-freshness (an architecture/standards change landing with the auto-loaded prose docs untouched) is carried here as a review rule, dual to the advisory `standards_drift` nudge.

Distinct from these rules, the **architecture_review stamp** (see review-dimensions.md §6a) is a separate **presence gate**, not a layer-b rule: on a structural diff the review must record `architecture_review.checked==true`, which `artifact_check` presence-gates at a hard stage.

## Managing rules

The operational rules live in the std tree (`harness/standards/areas/*.std.yaml`, `zone: operational`); per-rule `enabled: false` is the off-switch. Add or tune a per-repo rule with the rule-author skill, which writes `standards.user.yaml` (override by id, or a new id — a floor rule cannot be overridden or shadowed).
