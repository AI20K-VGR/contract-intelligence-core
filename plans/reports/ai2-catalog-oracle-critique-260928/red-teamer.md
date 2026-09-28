# ai2-catalog-oracle-critique-260928 — red-teamer

## red-teamer findings

_2026-09-27T21:22:49Z_

[
  { "lens": "red-teamer",
    "anchor": "ai-service/scripts/live_eval.py:276 (forbidden_hits = [item for item in pack.expected_no_claims if item.casefold() in answer_text]); repro: python -c substring check returned [] for legal_winner/invented_annex_7 against realistic answers",
    "finding": "expected_no_claims duoc kiem bang substring cua token noi bo (snake_case) tren answer JSON, khong bao gio khop hanh vi that",
    "why_it_matters": "Day la co che duy nhat dat ten cho hanh vi cam cua gan nhu moi case (legal_winner, full_pdf_dump, invented_annex_7, existence_leak, non_allowlist_tool, dump_all_rows_to_llm...). Model tra loi tieng Viet/Anh khong bao gio in ra chuoi 'legal_winner'; voi case khong query answer=None -> answer_text='null'. Gate nay la no-op: san pham co the bia phu luc, dump PDF, chon ben thang ma van xanh",
    "fix": "Thay substring match bang assertion co cau truc (kiem tra field tool_calls/citations/answer schema), hoac map moi token sang mot predicate that su chay tren output; toi thieu fail-loud neu answer rong ma case co expected_no_claims",
    "severity": "blocker",
    "status": "proven" },
  { "lens": "red-teamer",
    "anchor": "ai-service/scripts/live_eval.py:300 (expected_match = extract_ok and actual_state in {PASS,NEEDS_REVIEW,SUCCEEDED,REVIEW}); app/pipeline/idp.py:326-341 (worst chi la PASS|NEEDS_REVIEW|BLOCKED)",
    "finding": "Nhanh khong-BLOCKED chap nhan ca PASS lan NEEDS_REVIEW, xoa nhoa phan biet giua tu-tra-loi va gio-cho-review",
    "why_it_matters": "Rat nhieu case ton tai chinh vi ky vong REVIEW (EC-020 silent_merge, EC-027/EC-029/EC-031/EC-033 legal_winner, SALE-BRD-07/SERVICE-BRD-08 precedence). Neu san pham SAI khi tu dong PASS va chon ben thang, scorer van xanh vi PASS nam trong accept-set. Nguoc lai case PASS (HAPPY-*) van xanh khi pipeline chi tra default NEEDS_REVIEW ma khong xac thuc. Ket hop voi F1, KHONG co bat ky kiem tra nao chan hanh vi 'chon legal winner'",
    "fix": "Doi khop chinh xac: expected PASS -> actual PASS; expected REVIEW -> actual NEEDS_REVIEW (va chuan hoa token 'REVIEW' vs 'NEEDS_REVIEW' vi pipeline khong bao gio phat ra 'REVIEW')",
    "severity": "blocker",
    "status": "proven" },
  { "lens": "red-teamer",
    "anchor": "ai-service/scripts/live_eval.py:290 (expected_match = actual_state == \"BLOCKED\" or not extract_ok); repro: blocked_match('NEEDS_REVIEW', extract_ok=False) -> True",
    "finding": "Case BLOCKED duoc tinh xanh khi extract HTTP that bai (not extract_ok), bat ke ly do",
    "why_it_matters": "Cac control bao mat/loi song EC-053 (cross-tenant leak), EC-054 (stale ACL), EC-045 (encrypted), EC-049 (stale publish), EC-056 (legal hold), HAPPY-006 (ACL deny) se duoc chung nhan xanh chi vi endpoint bi 500/crash vi ly do khong lien quan. Loi server gia dang thanh 'da chan dung policy'",
    "fix": "Bo dieu kien 'or not extract_ok'; yeu cau actual_state == BLOCKED thuc su (hoac ma loi policy cu the trong handoff_issues), coi HTTP error la that bai rieng",
    "severity": "blocker",
    "status": "proven" },
  { "lens": "red-teamer",
    "anchor": "ai-service/scripts/live_eval.py:296 (else extract_ok and not forbidden_hits) ket hop F1 khien forbidden_hits luon rong",
    "finding": "Case INSUFFICIENT khong co query rut gon thanh chi 'extract_ok' (HTTP 200)",
    "why_it_matters": "EC-022 (ngay tuong doi, ky vong INSUFFICIENT, khong query) xanh voi bat ky 200 nao du he thong co bia moc lich hay khong. Hop dong chong-bia (invented_calendar_date) khong duoc kiem tra gi ca",
    "fix": "Voi case INSUFFICIENT khong query, kiem tra review_state extract == INSUFFICIENT_EVIDENCE (hoac it nhat NEEDS_REVIEW + vang mat fact bia), khong chi HTTP 200",
    "severity": "major",
    "status": "proven" },
  { "lens": "red-teamer",
    "anchor": "ai-service/scripts/live_eval.py:300 (accept-set chua \"SUCCEEDED\") vs app/contracts/models.py:11-14 (ReviewState khong co SUCCEEDED)",
    "finding": "Accept-set tron 'SUCCEEDED' (JobStatus) vao vung review_state; token chet khong bao gio khop",
    "why_it_matters": "Khong gay sai truc tiep nhung lam sai lech y dinh oracle va che giau viec accept-set qua rong; de nguoi doc tuong dang kiem trang thai chat hon thuc te",
    "fix": "Xoa 'SUCCEEDED' khoi accept-set review_state; neu can kiem job.status thi kiem rieng",
    "severity": "minor",
    "status": "proven" },
  { "lens": "red-teamer",
    "anchor": "ai-service/scripts/live_eval.py:276 (substring 'in' tren token thuong nhu 'precedence')",
    "finding": "Neu gate substring co song, token tu thuong (vd 'precedence') co the false-positive khi answer dung tu do hop le",
    "why_it_matters": "Rui ro nguoc lai cua F1: mot khi ai do sua sang matching chuoi tieng Viet/Anh, token chung se cham nham va fail case hop le, tao noise che giau bug that",
    "fix": "Dung token dinh danh khong nhap nhang + predicate co cau truc thay vi substring tren van ban tu do",
    "severity": "minor",
    "status": "suspected" }
]

