# Mock cases

- Generator: `fixtures/catalog.py`
- Dump JSON: `python scripts/dump_cases.py` → `fixtures/cases/{EC|HAPPY}-*.json` + `manifest.json`

Coverage: EC-001..EC-056 (AI2-04) and HAPPY-001..HAPPY-006.

Large tables (EC-010, 300 rows) keep full rows in Python; JSON dump stores first/last sample + `n_rows`.
