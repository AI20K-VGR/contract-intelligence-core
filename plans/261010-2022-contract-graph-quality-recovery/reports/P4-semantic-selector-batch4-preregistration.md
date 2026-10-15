# P4 semantic selector, four-request dev diagnostic

Date: 2026-10-11

The user requested remediation of the candidate-recall and classifier-recall failures. After the earlier selector attempt produced no valid artifact, this separate bounded diagnostic is registered before retrying.

- Run ID: `P4-semantic-selector-dev32-batch4-v1`
- Data: the 32 document IDs in the locked dev recall frame only; no held-out documents
- Input: eligible node IDs, headings, and clause text capped at 1,200 characters per node
- Requests: four balanced batches, one request per batch
- Model: requested `cx/gpt-5.5`; record and validate served model for every request
- Output: at most 40 ranked unordered node-ID pairs per document; no relation labels or spans
- Limits: 550 seconds and 500,000 total tokens across the diagnostic
- Validation: discard unknown IDs, self-pairs, ineligible nodes, Luong-1 pairs, and ancestor pairs; score exact candidate coverage on the locked dev gold only
- Use: diagnostic only; no runtime integration or held-out access is authorized by this experiment

The prior failed attempt is separately recorded as invalid/unscored. If any request, time, or token ceiling is exceeded, stop and record a failed run; do not retry under this registration.

## Outcome

Completed all four requests. The provider served `gpt-5.5` for all batches; aggregate usage was 206,907 tokens and 199.02 seconds. Validation retained 816 candidate pairs and rejected 76 Luong-1/ancestor pairs. Candidate coverage was **11/37** (CONFLICT 1/1, DUPLICATE 1/2, GENERAL_SPECIFIC 8/27, REFERENCE 1/7), equal to deterministic C/40. The full selector list adds complementary positives: offline union with C/40 was 17/37, while the preregistered fixed-cap blend sweep peaked at 15/37. Diagnostic only; no runtime change and no held-out access. Artifact SHA-256: `acd6322502ebc26f660b1e89f517c1514d5550f44817218b59a27618efeea40b`.
