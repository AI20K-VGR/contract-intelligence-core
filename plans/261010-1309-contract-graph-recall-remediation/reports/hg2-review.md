# HG-2 review receipt

- Schema: `contract-graph-hg2/1`
- Status: `PASS`
- `human_approved`: `true`
- `manifest_locked`: `true`

The locked HG-1 positive counts are CONFLICT 30, DUPLICATE 29, GENERAL_SPECIFIC 34, and REFERENCE 8. The sizing report records the lower bounds needed to reach 60 positives per scored label and proposes Wilson lower recall >= 0.85. No expanded rows or recall-floor approval are asserted in this receipt. P5 must remain blocked until a human records the floor, scope consent, and decisions for any added rows.

## Review packet ready

- Selection: `.harness/state/contract-graph-pairs/review/hg2_selection.jsonl`
- Spreadsheet: `.harness/state/contract-graph-pairs/review/hg2_review.csv`
- Selection SHA-256: `7488c8422f53f326042672bba81366d377a0a93027991cb610598ff5d94be896`
- Rows: `474` (`S1=66`, `S2=10`, `S3=384`, `S4=14`)
- Scope: previously unselected held-out pairs only; all 474 GPT suggestions are `UNRELATED`; the human-confirmed decisions are recorded below.

The reviewer must fill `decision` for every row (`approve|relabel|reject`). For `relabel`, fill `label_fixed` and `direction_fixed` where the label is directed. This packet does not modify the locked HG-1 selection or assert `human_approved`.

## Human decision recorded

- Status: `PASS`
- `human_approved`: `true`
- `scope_consent`: `true`
- Recall floor: Wilson lower `>=0.85` for GENERAL_SPECIFIC, CONFLICT, DUPLICATE, REFERENCE.
- Reviewed rows: `474`; approve `474`, relabel `0`, reject `0`.
- HG-1 rows remain unchanged; P5 is permitted only after this manifest is committed.
