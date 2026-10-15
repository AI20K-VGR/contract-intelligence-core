# P4 semantic selector, top-80 dev diagnostic

Date: 2026-10-11

The prior preregistered top-40 selector completed with 11/37 candidate recall, equal to deterministic C/40. An offline merge sweep found 15/37 when preserving the first 32 deterministic candidates, adding up to 8 model-ranked candidates, then backfilling unused slots. To test whether the selector's own top-40 truncation is the limiting factor, run one new top-80 diagnostic before any runtime integration.

- Run ID: `P4-semantic-selector-dev32-top80-v2`
- Split and documents: the same locked 32-document dev recall frame only
- Model: `cx/gpt-5.5`
- Requests: four, one request per balanced batch
- Output: up to 80 ranked unordered node-ID pairs/document; no labels or spans
- Limits: 550 seconds, 500,000 total tokens, four HTTP requests
- Validation: eligible known nodes only; exclude Luong-1 and ancestor pairs; deduplicate; score against the same locked approved dev gold
- Use: diagnostic only. No runtime integration or held-out access is authorized by this preregistration.

If a request or limit fails, stop and mark the run invalid/unscored. Do not retry this registration.

## Outcome

The preregistered run `P4-semantic-selector-dev32-top80-v2` is `invalid_unscored`: request 2 raised `LabelerCallError` after 2 HTTP requests, 108,416 tokens, and 227.19 seconds. The metric is excluded; the registration was not retried. No held-out data was accessed. Since no valid top-80 ranking was produced, this run does not establish candidate-recall improvement or regression.
