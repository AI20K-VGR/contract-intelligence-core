# P3 developer report (tóm tắt, đã kiểm tại main)

- Golden sha256 `091421c523715af741bfaca7cad7125a381d6063e0471a7e58d063bd7f64cac2` (main kiểm lại sau khi sửa `idp.py`).
- Harness suite: 76 passed; 5 file test P3 ai-service: 107 passed (main chạy lại).
- ai-service full suite (subagent): 13 failed môi trường / 1250 passed / 36 skipped.
- p3-operation-parser: target_correct 68/70 (CI95 0.902–0.992), op_lexical_agreement 70/113, op_precision 70/84; không kém P1 ở mọi op (recall + precision).
- Deviations: plan VL-7.
