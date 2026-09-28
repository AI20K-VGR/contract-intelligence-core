# ai2-catalog-oracle-critique-260928 — independent-revalidator

## independent-revalidator findings

_2026-09-27T21:26:27Z_

[
  { "lens": "independent-revalidator",
    "anchor": "ai-service/scripts/live_eval.py:299-300",
    "finding": "expected_state khop kieu permissive: nhanh else chap nhan actual_state in {PASS,NEEDS_REVIEW,SUCCEEDED,REVIEW}, nen case expected_state=REVIEW van green khi san pham tra PASS (tu dong chap nhan).",
    "why_it_matters": "Cac case doi hoi REVIEW/khong tu quyet (EC-020, EC-027, SALE-BRD-07) score green ma san pham chua bao gio flag review; green khong chung minh hanh vi title tuyen bo duoc tuan thu.",
    "fix": "Khop expected_state chinh xac (REVIEW chi map NEEDS_REVIEW/REVIEW, khong gom PASS) hoac them assertion theo tung state.",
    "severity": "blocker",
    "status": "proven" },
  { "lens": "independent-revalidator",
    "anchor": "ai-service/scripts/live_eval.py:275-276",
    "finding": "expected_no_claims duoc kiem nhu literal casefold substring cua JSON answer, nhung gia tri la ma hanh vi ngu nghia (legal_winner, full_pdf_dump tai fixtures/catalog.py:251,362) khong xuat hien nguyen van trong cau tra loi tieng Viet.",
    "why_it_matters": "Gate forbidden-claim rong nghia: san pham thuc su pham hanh vi cam van cho forbidden_hits=[] va van green, nen expected_no_claims khong phai oracle that.",
    "fix": "Thay substring-match bang detector hanh vi that theo tung ma, hoac assert tren truong co cau truc cua answer thay vi token search.",
    "severity": "blocker",
    "status": "suspected" }
]

