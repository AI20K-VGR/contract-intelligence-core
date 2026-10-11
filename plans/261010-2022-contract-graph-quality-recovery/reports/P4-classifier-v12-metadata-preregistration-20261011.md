# P4 classifier v12 contract/metadata diagnostic

Date: 2026-10-11

## Preregistration

- Run ID: `P4-classifier-v12-metadata-dev20-r1`.
- Dev-only, same exposed sample and order as v9/v10: 3 `REFERENCE`, 3 `GENERAL_SPECIFIC`, 14 `UNRELATED`; pair-ID SHA-256 `c4cdac1658e5d0b5408fedbe97b603c4831b4b97e3e2860c1289f376288a37b3`.
- Treatment: prompt v12 aligns resolved citations with the reviewed relation convention, resolves REFERENCE/GENERAL_SPECIFIC step order, and sends candidate provenance as `candidate_sources`; exact span and direction validators remain. Rubric version bumped to `pairs-labeler-v2`.
- Requested model `cx/gpt-5.5`; cap 3 HTTP requests, 100,000 tokens, 550 seconds; one attempt per request.
- Score exact label plus direction for directed labels, per-label counts, abstentions, and false DUPLICATE.
- The pairs have been seen in previous dev trials. Diagnostic only; not independent validation, no gate change, no held-out access.
- On request failure or cap breach, mark invalid/unscored and do not retry this registration.

## Result

Completed 3 requests with served model `gpt-5.5`; 12,599 tokens and 49.12 seconds. Raw exact score against the existing approved gold: `15/20`: `REFERENCE` 2/3, `GENERAL_SPECIFIC` 1/3, `UNRELATED` 12/14; 1 false `DUPLICATE`; 0 span/direction validator rejections; no abstentions. At least one scored `GENERAL_SPECIFIC` item contains a numbered citation that v12 now treats as `REFERENCE` evidence, while gold was approved under the previous rubric. Therefore this raw score is **not comparable** to v10's 16/20 until affected gold rows are adjudicated under the new taxonomy. Diagnostic only; no quality PASS.

Artifact SHA-256: `3e8a26ee8e6ed8c677d51a5ec0edd5025429e487b69d3ddfcc725708f2124240`.
