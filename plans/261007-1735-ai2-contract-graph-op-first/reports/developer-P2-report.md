# P2 developer report (tóm tắt, đã kiểm tại main)

- Harness suite: 69 passed (main chạy lại). ai-service focused (address, resolver, import_boundaries): 85 passed (main chạy lại).
- ai-service full suite (subagent): 13 failed môi trường / 1143 passed (= 1061 + 82) / 36 skipped.
- p2-resolver: nd50 UNIQUE đúng 26/26 cả hai hình dạng cây (P1 baseline 13/26); toàn bộ UNIQUE 65 (đúng 63), NOT_FOUND 4, AMBIGUOUS 0; precision 0.969 (CI 0.895–0.992).
- Deviations: plan VL-6.
