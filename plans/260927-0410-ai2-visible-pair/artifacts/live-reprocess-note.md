# Live reprocess note — 2026-09-27

Replay `job_e5a15a15bc` of dossier `dos_01M3BPQFSXW68FGZJ1RPFMYXTY` against the rebuilt AI2 image. Status `SUCCEEDED`, review `NEEDS_REVIEW`.

- One fact, `item_key=contract_value`, raw `1286400000`. No second contract total on the annex, so no `COMPARABLE_DIFFERENCE`.
- Four `CONTEXT_GAP` findings for phụ lục 01–04. `metadata.relation` is absent. That matches the rule: `UNCONFIRMED` is attached only when a value pair already exists.
- `GET /health` on the running container returned `status=ok`, `llm=ready`, `model=gh/gpt-4o-mini`. The probe reached the configured model. `status` stayed `ok`.

The replay writes AI2's own job result. The analysis screen reads the backend projection, which this direct replay does not update. The screen shows `CHƯA XÁC NHẬN` when a stored context finding has `metadata.relation=UNCONFIRMED` (`frontend/tests/context-finding-note.test.ts`).
