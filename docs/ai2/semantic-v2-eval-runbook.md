# Semantic v2 E2E and evaluation runbook

This runbook separates deterministic conflict discovery from optional retrieval
and LLM enrichment. A provider mode may add evidence or review reasons; it
cannot remove a deterministic pair or choose a legal winner.

## Hermetic metamorphic probe

Run the five-case suite from the worktree root:

```powershell
uv run --project ai-service python -m pytest evals/tests/test_semantic_v2_eval.py -q
```

The suite covers opposite polarity, same-milestone value deltas, distinct
milestones, generic entire-agreement text, and provider-disabled determinism.
The real comparator is used; the probe does not call a provider or vector
database.

To emit a mode-pinned receipt:

```powershell
$out = 'tmp/semantic-v2-p6'
foreach ($mode in 'local-only','vector-only','llm-only','full') {
  uv run --project ai-service python scripts/run_semantic_v2_e2e.py `
    --mode $mode --output "$out/$mode.json"
}
```

`vector-only`, `llm-only`, and `full` record requested flags but report
`REQUESTED_BUT_NOT_USED` when this hermetic runner has no provider adapter.
Use a separate live receipt for a real provider run; never label this probe as
an accuracy result.

## Live service smoke and sanitized logs

The canonical Compose project is `contract-intelligence-stack`. The collector
reads Docker stdout for Backend, AI2, and Frontend, redacts bearer/API-key
patterns, and writes the receipt outside Git:

```powershell
python scripts/collect_e2e_service_logs.py `
  --project contract-intelligence-stack `
  --compose-file docker-compose.yml `
  --since 15m --frontend-url http://localhost:5173/ `
  --output tmp/semantic-v2-p6/service-logs.json
```

Check `counts`, `error_count`, and the secret scan before accepting the
receipt. A zero log error count is an observability result, not an AI2 quality
claim. Citation validity still comes from the persisted semantic extension and
the PostgreSQL read model.

## Plan A release measurement

Before any holdout replay, an independent reviewer must freeze the gold label
manifest, matched baseline, metric policy, runtime/model/profile pins, and
holdout ACL receipt. Use the release runner only after those files exist in the
private evaluator directory:

```powershell
uv run --project ai-service python evals/clause_frame_release.py measure `
  --manifest <private-gold.json> --thresholds <private-policy.json> `
  --baseline <private-matched-baseline.json> --freeze <private-freeze.json> `
  --split heldout --mode local-only --private-out <private-result.json> `
  --out <shared-diagnostics.json>
```

The runner keeps `release_status=BLOCKED` until the three human receipts are
real: approved independent gold, holdout isolation, and frozen metric policy.
It reports per-disposition precision/recall, false duplicates, amendment and
citation checks, coverage, workload, cost, and latency only for eligible
units. Missing receipts, source drift, or ACL drift are blocking reasons; do
not replace them with synthetic approvals.

## Required interpretation

`CONFLICT_CANDIDATE` and `COMPARABLE_DIFFERENCE` are review items. `0` pairs
with incomplete coverage means `NEEDS_REVIEW`, never “consistent”. A timeline
proposal is review-only and never establishes a legal winner. Keep debug
dossiers out of the heldout package and split a later evaluation by dossier or
contract package to prevent leakage.
