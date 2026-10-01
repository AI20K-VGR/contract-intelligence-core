# AI2-06 — Implementation gap (FR / EC / case nghiên cứu)

**Phiên bản:** v0.3
**Ngày:** 20/09/2026  
**Phạm vi:** Bản đồ đã có code, mock/mỏng, ngoài AI2. Không claim accuracy/SLA. Không `LEGAL_WINNER`.

Lớp 20/09: gold HD hai nguồn (`fixtures/gold/hd_tong_hop_findings.json`); finding = thân↔phụ lục cùng `item_key`; review overlay session; SQLite lát mỏng `data/ai2` (không thay BE ACL). Coverage ≠ độ chính xác. OCR/RLS vẫn Ngoài AI2; vector recall hiện là capability tuỳ chọn, có discovery NineRouter và SQLite demo, chưa phải pgvector production. NineRouter dùng catalog riêng `/v1/models/embedding` (không chỉ `/v1/models`); runtime đã xác nhận `openrouter/openai/text-embedding-3-small` hoạt động với 1536 chiều. Vector vẫn mặc định tắt, cần bật feature flag khi benchmark/demo. Fixture catalog có đủ EC-001..EC-056 nhưng không phải tất cả đã chạy end-to-end.

Nguồn: [AI2-01](AI2-01-business-policy-perspective.vi.md) … [AI2-05](AI2-05-architecture.vi.md), [AI2-04](AI2-04-edge-case-test-matrix.vi.md).

## Cập nhật mục tiêu AI2 [2026-09-23]

Outcome Contract mới yêu cầu AI2 tổng quát hóa sáu profile wave đầu: `SALES`,
`SUPPLY_SERVICE`, `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA`; hỗ trợ profile
extension cho phụ lục; dựng cây body/annex/clause/table; hiểu relation; comparison
trong dossier; và free-form Q&A có grounding. Đây là mục tiêu cần hoàn thiện, không
phải claim đã xong.

95 case là candidate corpus `UNVERIFIED`. Repo hiện có manifest 65 case records;
chưa có golden set được người duyệt xác nhận. Vì vậy coverage/regression hiện có
không được diễn giải thành accuracy nghiệp vụ.

## 1. Quy ước cột

| Cột | Nghĩa |
|---|---|
| Done | Có đường chạy deterministic trên snapshot (HD-TONG-HOP / EC fixture) |
| Mock | Có hướng + fixture, pipeline demo chưa đủ hoặc lexical thay semantic |
| Ngoài AI2 | Persist/publish/ACL BE đầy đủ, OCR engine, pgvector production, cost ledger, encrypted intake. Lát SQLite local trong AI-service không phải cổng BE. |

## 2. FR / hành vi sản phẩm (rút từ AI2-01/03)

| ID | Hành vi | Trạng thái | Ghi chú |
|---|---|---|---|
| FR-HANDOFF | Không nhận `pdf_bytes`; pin/lifecycle; chất lượng snapshot; v1/legacy boundary | Partial | v1 schema + semantic gate; `ai1.result.v0.1` và legacy OCR vẫn có compatibility path riêng; AI1 producer/Backend handoff end-to-end còn ngoài AI2 |
| FR-ROUTER | FIELD/TABLE/CLAUSE | Done | `ObjectRouter` |
| FR-FACT | Fact + citation; không chọn MST | Done | Gold MST A 0312345678 ↔ 0399999999 |
| FR-TABLE | Meta 2+2 + sandbox; missing≠0; table coverage | Partial (fixture 300) | `NOT_PRESENT` không cảnh báo; `UNKNOWN/UNAVAILABLE` tạo EvidenceIssue; continuation/assembler nhiều trang còn gap |
| FR-CANDIDATE | Pair hai nguồn, cấm winner | Done | Gold HD; Cartesian tắt; phạt khác phạm vi không gộp |
| FR-INDEX | Chỉ `propose` | Done | Nút publish demo không đổi contribution |
| FR-REVIEW | Confirm/correct/reject overlay | Demo mỏng | Candidate lạ bị từ chối; session + SQLite; stale khi extract lại; không sửa raw; chưa thay BE audit |
| FR-L0 | MST, gap, PL7, UNNUMBERED, jailbreak, FX, table codegen | Done | |
| FR-L1 | Exact → structured key → lexical k≤8 → vector recall (tuỳ chọn) | Partial (gói này) | NineRouter discovery + SQLite demo; vector không tự kết luận, phải metadata/citation validate |
| FR-L2 | Plan-then-act khi LLM; không LLM = REVIEW + citation | Done (gói này) | |
| FR-L3 | Extractive; drop node giả | Done (gói này) | |
| FR-ACL | Tool envelope | Mock tại AI2 | EC-053..056 Ngoài |
| FR-OCR | Paddle/Tesseract | Ngoài AI2 | Legacy text-only được nhận degraded; geometry/table đầy đủ phụ thuộc AI1 |
| FR-EVAL-N | Candidate/golden denominator và accuracy claim policy | Partial | Candidate corpus có; golden promotion/human review và reconcile claim 95 còn gap |
| FR-PROFILE | Field/fact profile theo loại hợp đồng | Partial | Core `Fact` có; registry sáu profile wave đầu chưa khóa trong code |
| FR-STRUCTURE | Cây body/annex/clause/table và relation graph | Partial | Outline/context/relation có; coverage đa loại và relation confidence còn gap |
| FR-FREEFORM | Câu hỏi tự do trong dossier có citation | Partial | Query router/L0–L3 có; `unscoped` hiện safe-state, chưa đạt free-form coverage tổng quát |

## 3. EC-001 … EC-056

| EC | Thành phần | Trạng thái |
|---|---|---|
| 001 Scout, không dump PDF | L0/L1/L2 cap | Done (refuse tóm tắt toàn bộ) |
| 002 Chunk điều dài | ClauseChunker | Done mỏng |
| 003 UNNUMBERED | L0 | Done |
| 004 Trùng số điều | Node riêng | Done fixture |
| 005 Nhảy số | L0 gap | Done Điều 3 |
| 006 Numbering hỗn hợp | Structure | Mock |
| 007 Header/footer | Handoff | Mock |
| 008 Definition | L1 lexical + synonym | Done mỏng |
| 009 Thiếu target | INSUFFICIENT | Done PL7 |
| 010 Bảng 300 | Codegen | Done |
| 011–019 Table assembler | Catalog EC | Mock trên demo PDF |
| 020 MST lệch | L0 | Done |
| 021 Số chữ/số | Candidate | Done mỏng |
| 022 Ngày tương đối | Fact | Mock |
| 023 Bậc thang | Fact | Mock |
| 024 FX | NOT_COMPARABLE | Done |
| 025 Alias profile | Pin | Mock |
| 026 Tên giống MST khác | Candidate | Mock |
| 027 Body/table/annex | T-GIA | Done mỏng |
| 028 Implicit amendment | Candidate | Mock |
| 029 Nhiều annex | T-DIEU5 | Done: REVIEW, không precedence |
| 030 Khác scope | T-SCOPE | Done |
| 031 Song ngữ | Nodes EN/VI | Mock so sánh |
| 032 Cosmetic vs substantive | — | Mock |
| 033 Cascade định nghĩa | T-CASCADE | Done: REVIEW |
| 034 Aggregation thiếu nguồn | L1/L3 | Done hướng |
| 035 Injection | L0 | Done |
| 036 Index processing | Store flag | Mock |
| 037 Query EN / HĐ VI | Synonym map | Done mỏng |
| 038 Duplicate chunk | Dedupe L1 | Done mỏng |
| 039 Confidence ≠ PASS | L3 | Done hướng |
| 040–044 Scan/OCR | — | Mock / một phần PARTIAL |
| 045 Encrypted PDF | Intake | Ngoài AI2 |
| 046 Trang trắng | Inventory | Mock |
| 047 Budget | — | Ngoài AI2 |
| 048 Nhiều annex queue | — | Mock |
| 049 Lease concurrent | — | Ngoài AI2 |
| 050 Embedding cost | — | Ngoài AI2 |
| 051 Profile đổi | Version pin | Mock |
| 052 Re-OCR revision | Citation | Mock |
| 053–056 ACL/cache/egress/hold | BE | Ngoài AI2 |

## 4. Input dài / hallucination (bắt buộc)

1. Scout outline ID; không concatenate pages vào một prompt.
2. `get_node` ≤2k; bảng chỉ meta 2+2; cấm `get_table_rows` vào LLM.
3. Query quá rộng → `INSUFFICIENT_EVIDENCE` hoặc `NEEDS_REVIEW`, không executive summary.
4. L3 extractive: mệnh đề neo substring/MST trên node đã lấy; `node_id` không có trên outline → loại.
5. Thiếu PL/điều → INSUFFICIENT, không bịa.
6. `legal_winner` strip; conflict → sufficient=false.

## 5. Semantic/vector recall có kiểm soát

Thứ tự authoritative: exact label → structured key (không dùng raw query làm key) → BM25-lite + synonym EN↔VI. Vector RAG chỉ bổ sung recall ứng viên sau khi NineRouter được discovery thành công; segment batch/cache theo snapshot + model + dimension, filter source metadata, rồi validate `node_id`, offset và substring citation. Lỗi provider, không có model hoặc không đủ evidence chỉ fallback deterministic/`NEEDS_REVIEW`, không làm hỏng L0–L3.

## 6. Backlog nghiên cứu (không bắt buộc code gói này)

Cấu trúc: thứ tự tài liệu mời thầu (chỉ trích nguyên văn); recital vs điều; side letter; tham chiếu vòng.

Tiền/XD: BOQ vs giá HĐ; provisional sum; VAT; không cộng thiếu nguồn.

Thời gian: EOT; phạt vs trần; retention vs bảo lãnh.

So sánh: redline; spec vs bản vẽ; «bao gồm nhưng không giới hạn».

Query: đa hop 3+; overlap duplicate.

## 7. Gold / test

- Fixture [`hd_tong_hop_tasks.json`](../../ai-service/fixtures/reasoning/hd_tong_hop_tasks.json): T-PARA, T-SUMMARY, T-CASCADE + 12 task cũ.
- Upload: map task theo **label** Điều/PL trên outline, không gắn cứng `cl_9`.
- Pytest mặc định: không gọi 9Router. Gold findings HD: `tests/test_hd_gold.py`.
- `pytest -m llm`: chạy bắt buộc trong CI/release khi đã cấu hình `AI2_LLM_API_KEY`; không xem việc thiếu key là bằng chứng pass. Local không có key chỉ được báo là môi trường chưa đủ để kết luận live-model gate.
- `app.pipeline.units`: đã có unit page-window có `unit_id`/`input_digest` ổn định và `UnitCheckpoint` để worker PostgreSQL nối vào; demo hiện vẫn chạy synchronous nhưng không ghép toàn bộ dossier vào một prompt.

## 8. Intent hỏi HĐ / phụ lục

Không BM25 mặc định. Câu không khớp → INSUFFICIENT + gợi ý.

| Intent | Ví dụ | Lớp |
|---|---|---|
| `party_card` | Thông tin bên A? | L0 assemble theo vai (tên, MST cùng dòng, không dump Điều 8) |
| `count_party` / `count_entity` | Bao nhiêu bên / pháp nhân | L0 |
| `lookup_clause` | Điều 5 nói gì | L0 + SAME_CLAUSE thân/PL |
| `annex_card` | Phụ lục 1 gồm gì | L0 children PL; thiếu PL → INSUFFICIENT |
| `field_card` | Giá trị HĐ; MST | L0 nhóm canonical |
| `compare` / `cascade` | Khác PL | L1+L2 |
| `too_broad` | Tóm tắt cả HĐ | L0 refuse |
| `unscoped` | Câu mở | Safe state hiện tại; cần mở rộng bounded free-form + grounding theo Outcome Contract |

Ngoài phạm vi: tư vấn, winner, tóm tắt toàn văn, vector index production/pgvector và cost ledger. Embedding recall demo đã có nhưng mặc định tắt.

## 9. DOC-01 / DOC-02 / DOC-03 — AI2 vs ngoài (LF-2.0)

AI2 làm **đối chiếu có nguồn**, không chatbot. Ask-intent là phụ.

| ID | Nội dung | AI2 | Ngoài AI2 |
|---|---|---|---|
| BR01–BR04 / FR01–FR03 | Intake, OCR, workspace file | Handoff snapshot | OCR/Paddle, seal, PAGE re-OCR |
| BR05 / FR06 | Typed fact + context (item, unit, currency, kỳ) | `Fact.item_key` `period_start` `source_role` | HITL persist |
| BR06 / FR07 | Decision table 5 disposition, 3 scope | `compare.py` | — |
| R01–R05 | Context tiền; sửa tường minh; Decimal; semantic X≠Y | Done fixture SALE-BRD-07 / SERVICE-BRD-08 | — |
| EvidenceIssue | Viện dẫn PL thiếu file | `evidence_issues` + coverage | Queue upload BE |
| FR08–FR11 | HITL confirm, ACL, publish | Index `propose` | BE persist |
| FR12 | Export | JSON findings+issues (demo) | CSV neutralize app |
| FR13–FR14 | Batch 10, cloud consent | — | FE |
| DOC-01 cấm | Chatbot, HĐ hợp nhất, legal winner | Không | — |

Kịch bản DOC-02 §7–§8: **Done** (`SALE-BRD-07`, `SERVICE-BRD-08`).
