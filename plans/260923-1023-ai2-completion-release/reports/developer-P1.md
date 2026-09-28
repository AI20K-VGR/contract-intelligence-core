# Developer report — P1 Contract Boundaries

## Implementation

- Added semantic validation for request/result digest, duplicate identity/relation,
  membership, relation scope, citations and unknown payloads.
- Kept canonical snapshot handling separate from OCR-lab and legacy
  `ai1.result.v0.1` adapters.
- Added versioned profiles for `SALES`, `SUPPLY_SERVICE`, `LEASE`,
  `CONSTRUCTION_WORK`, `EMPLOYMENT` and `NDA`, including annex extensions.
- Added `ai2.contract-type-profile.v1` schema.
- Corrected Vietnamese alias handling using UTF-8-safe Unicode escapes; raw keys remain
  unchanged and no mojibake/U+FFFD is allowed.

## TDD evidence

- Intentional RED: collection failed because `validate_processing_result` and
  `contract_profiles.py` were absent.
- GREEN targeted P1: `36 passed`.
- Full offline gate: `209 passed, 6 deselected`.
- Contract registry: `Contract registry OK (5 schemas)`.
- `git diff --check`: clean.
- Byte-level UTF-8/FFFD/mojibake check: PASS.

## Main review

- Re-ran P1 targeted tests independently: `36 passed, 1 warning`.
- Confirmed profile aliases resolve actual Vietnamese `Đơn giá` to `unit_price` while
  preserving the raw key.
- Warning is an existing Starlette deprecation warning; no assertion failure.
- Live/provider accuracy remains outside P1 and is not claimed.

## Files

Changed only within P1 ownership; no commit was created by the developer.
