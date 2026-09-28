# Ranh giới Script-check vs LLM-check

Hai loại kiểm tra. **Chỉ Script-check chặn.** LLM-check là advisory, mặc định im lặng.

## Script-check (objective — đếm / đi-graph)

- Thực thi bởi `check_docs.py` → `graph.validate` → artifact JSON. Gate `docs_gate.py` đọc số → exit 0/2.
- Phán **structural/objective**: frontmatter shape, id grammar/unique, parent/provenance resolve,
  parts/links/config/safety/foundation graph, required-set capability-driven, README-DRY guard.
- Đặc tính: **xác định** (cùng input → cùng output), không cần model, không suy diễn nội dung.
- `error` → BLOCKED (exit 2). `warn`/`info` → không chặn.
- Danh mục đầy đủ: `references/graph-invariants.md`.

## LLM-check (advisory — phán prose)

- KHÔNG có trong analyzer/gate. Là pass tùy chọn của người/agent đọc prose, **chỉ khi được yêu cầu rõ**.
- Phạm vi hẹp, ví dụ: vagueness (`> TBD` còn sót sau khi đáng-lẽ-đã-viết), contradiction
  (hai doc nói ngược nhau về cùng một part), duplicate (đoạn copy nguyên-văn giữa doc — bổ trợ
  cho `readme-copies-boundary` ở mức mềm).
- **Quy tắc cứng**:
  1. **MẶC ĐỊNH KHÔNG flag.** Im lặng là trạng thái đúng; chỉ nói khi có bằng chứng cụ thể.
  2. **Luôn neo theo số trong artifact.** Mọi nhận xét tham chiếu finding/đếm thật
     (`harness/state/docs-check.json`), không phán chung chung.
  3. **KHÔNG bao giờ phán "thiết kế dở" / "nội dung kém".** Skill không debate chất lượng.
     Tối đa: chỉ ra *vị trí* prose cần người xem (vd "doc A và B mô tả khác nhau về part X").
  4. **KHÔNG tự sửa.** Quan sát cần-người-quyết → ghi `FIX.md`, để người quyết.
- Advisory **không** thay đổi verdict gate. Một repo PASS gate vẫn PASS dù LLM-check có ghi chú.

## Bảng phân vai

| | Script-check | LLM-check |
|---|---|---|
| Chạy bởi | `check_docs.py` / `docs_gate.py` | người/agent, on-demand |
| Đối tượng | cấu trúc (frontmatter/graph/required-set) | prose |
| Xác định? | có | không |
| Chặn CI? | có (`error`→exit 2) | KHÔNG |
| Mặc định | luôn chạy | KHÔNG flag |
| Phán chất lượng? | KHÔNG | KHÔNG |
| Đầu ra | artifact JSON | ghi chú neo-artifact / `FIX.md` |

## Quy trình khi muốn dùng LLM-check

1. Đảm bảo artifact mới (`check_docs.py --quiet`).
2. Đọc prose; chỉ nêu quan sát **có bằng chứng** + neo finding/số liên quan.
3. Không kết luận "tốt/dở"; chỉ "vị trí X cần người xem vì lý do objective Y".
4. Quan sát → `FIX.md` (mỗi mục: vị trí + lý do + để-người-quyết). Không tự sửa, không chặn.
