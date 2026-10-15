# P4 classifier v9 post-fix dev diagnostic

Date: 2026-10-11

## Preregistration

- Run ID: `P4-classifier-v9-dev20-r1`
- Scope: the exact 20 approved dev pairs from `P4-baseline-r1`, same order and source documents.
- Treatment: current production `pairs-v9` classifier prompt and validator.
- Model: `cx/gpt-5.5` using local `ai-service/.env`; do not emit credential values.
- Budget: at most 3 HTTP requests, 100,000 total tokens, and 550 seconds; one attempt per request. Stop at the first failed request; no retry.
- Output: aggregate exact-label/direction scores, pair IDs, outcomes/rejection codes and served model only. Do not persist contract text or raw responses.
- Use: diagnostic only. This is a post-fix re-evaluation of an already exposed dev sample, not an independent confirmation, gate evidence, candidate-recall measurement, or authorization to access held-out.
- Held-out: not accessed.

If a request fails or a limit is exceeded, record invalid/unscored and do not retry.

## Outcome

Invalid/unscored. The diagnostic runner read `gpt-4o-mini` from the local labeler config instead of the preregistered `cx/gpt-5.5`; the first request returned no response, with 1 HTTP request, 0 recorded tokens, and 2.58 seconds. No predictions were scored. Do not retry this sample under this registration. A separately preregistered fresh dev sample is used for the next attempt.
