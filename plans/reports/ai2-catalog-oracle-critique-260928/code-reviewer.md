# ai2-catalog-oracle-critique-260928 — code-reviewer

## code-reviewer findings

_2026-09-27T21:23:24Z_

[
  { "lens": "code-reviewer",
    "anchor": "ai-service/scripts/live_eval.py:299-300",
    "finding": "Nhanh else chap nhan tap long {PASS,NEEDS_REVIEW,SUCCEEDED,REVIEW} va khong he so expected_state, nen PASS vs REVIEW khong duoc phan biet.",
    "why_it_matters": "Khoang mot nua catalog mat y nghia expected_state: mot case REVIEW tra ve PASS (hoac nguoc lai) van expected_match=true, oracle khong khoa duoc hanh vi ma title tuyen bo.",
    "fix": "So khop truc tiep: map expected 'PASS'->{'PASS'}, 'REVIEW'->{'NEEDS_REVIEW','REVIEW'} va yeu cau actual_state nam dung tap cua expected, bo 'SUCCEEDED' khoi tap review_state.",
    "severity": "blocker",
    "status": "proven" },
  { "lens": "code-reviewer",
    "anchor": "ai-service/scripts/live_eval.py:274-275",
    "finding": "expected_no_claims la nhan ky hieu snake_case khong bao gio xuat hien trong answer JSON; voi case khong query answer_text='null', nen forbidden_hits luon rong.",
    "why_it_matters": "forbidden_claim_violations luon =0: cong chong bia (legal_winner, full_pdf_dump, existence_leak...) duoc bao cao la an toan nhung ve cau truc khong the bat duoc vi pham nao.",
    "fix": "Anh xa moi nhan sang mot assertion cu the tren answer/citations/handoff_issues thay vi substring tren json.dumps(answer).",
    "severity": "blocker",
    "status": "proven" },
  { "lens": "code-reviewer",
    "anchor": "ai-service/scripts/live_eval.py:291-298",
    "finding": "INSUFFICIENT khong query (EC-022, catalog.py:647) sup ve 'extract_ok and not forbidden_hits', va forbidden_hits luon rong.",
    "why_it_matters": "EC-022 'khong bia moc lich' khop chi nho extract HTTP 200; hanh vi giu bat dinh khong bao gio duoc kiem - oracle mark true du behavior unchecked.",
    "fix": "Voi INSUFFICIENT khong query, kiem actual_extract_state la trang thai bat dinh thuc hoac them assertion khong co structured_value bia, dung chi dua extract_ok.",
    "severity": "major",
    "status": "proven" },
  { "lens": "code-reviewer",
    "anchor": "ai-service/scripts/live_eval.py:290",
    "finding": "Nhanh BLOCKED chap nhan 'not extract_ok', nen extract crash HTTP 500 duoc cham la chan dung.",
    "why_it_matters": "EC-045/049/053/054/056: mot loi sap extraction nguy trang thanh BLOCKED hop le, che giau regression thuc trong duong policy.",
    "fix": "Yeu cau actual_state=='BLOCKED' (review_state) tuong minh; coi extract HTTP !=200 la failure rieng chu khong phai bang chung cua block.",
    "severity": "major",
    "status": "proven" },
  { "lens": "code-reviewer",
    "anchor": "ai-service/scripts/live_eval.py:265-274",
    "finding": "Case khong query co ask_payload={} nen citation_errors rong va citation_valid=True vo dieu kien.",
    "why_it_matters": "citation_valid_rate bi thoi phong boi cac case chua tung sinh citation, lam chi so grounding trong bao cao mat y nghia.",
    "fix": "Loai case khong query khoi mau so citation_valid_rate, hoac gan N/A thay vi True khi khong co answer path.",
    "severity": "minor",
    "status": "proven" }
]

