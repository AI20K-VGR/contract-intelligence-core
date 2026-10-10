# P5 developer record

- P5 preflight: `PASS`; combined reviewed gold is 655 rows (HG-1 181 + HG-2 474).
- Combined decisions SHA: `c7d45402809b71a9a575ff4cca57aadae78eb1d7e1a87bc50758f6e798399952`.
- Combined selection SHA: `074d071a1ab2c4add79814c99bf855a002ae0665cce5a0e7952a744d74132626`.
- Requested model: `cx/gpt-5.5`; served model: `gpt-5.5`; code lock commit: `c504df83`.
- Preflight selected C/B and skipped E because every scored label had `expected_n < MIN_N/2`; four live trials ran in declared order C1, B1, C2, B2.
- Measured recall_any: C1 5/101, B1 0/101, C2 4/101, B2 4/101. All four stayed within the trial budget and had no provider or trace error.
- Each trial observed one false `DUPLICATE`; the hard safety veto therefore produced `KEEP_OFF_FALSE_DUPLICATE`. Per-label denominators also remain below `MIN_N=60` and Wilson lower recall is far below `0.85`.
- Runtime enablement remains off. Recommendation is evidence-only; no flag was changed.
- Report artifacts: `evals/contract_graph/reports/l2-p6-bakeoff.json`, `l2-p6-bakeoff.md`, and `l2-p6-decision.json`.
