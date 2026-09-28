# Debug report: Test 1/Test 2 table continuity

## Symptom

Test 2 showed five fragments from pages 1–5 as separate tables. Test 1 also
showed continuation fragments separately after OCR.

## Reproduction

Database inspection of `dos_01M39XXAHPTZGW1X5RCTEWT52F` found five `doc_table`
rows on pages 1–5. Their STT ranges were `01–04`, `05–13`, `14–21`, `22–29`,
and `30`, but every row had `is_multi_page=false` and `continued_from=null`.

Database inspection of `dos_01M39XPA10F5B70J7VAHQXH0PG` found page 1/page 2
fragments with STT `01–02` then `03…`, and page 9/page 10 fragments. The
backend repository returned no continuation links before the fix.

## Confirmed root cause

AI1 already emitted document-level `table_continuity[]`, but
`backend/src/contract_intelligence/shared/ai/ai1_adapter.py` only copied each
page table and discarded those links. The persistence/API therefore returned
independent fragments. Older snapshots had no links at all, so the repository
also needed a conservative legacy recovery rule.

## Fix boundary

1. Map AI1 `MERGE` links into `continued_from_source_id` during snapshot
   adaptation.
2. Persist and expose the link through `doc_table.continued_from` and
   `doc_table.is_multi_page`.
3. For pre-v10 snapshots, infer only when the next-page fragment has the same
   populated column shape and its first STT equals the previous fragment's last
   STT plus one. A total row or a reset sequence prevents inference.
4. Frontend merges linked fragments, removes repeated headers, normalizes
   synthetic numeric headers as data rows, and keeps page-level cell citations.

## Live verification

After rebuilding backend, the repository returned Test 2 as one chain:
pages 1→2→3→4→5. Test 1 returned a page 1→2 chain and preserved the
unrelated signature/section tables separately; page 9→10 was also linked.
