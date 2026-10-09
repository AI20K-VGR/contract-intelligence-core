# AI2-20 — Quan hệ ngầm giữa các khoản hợp đồng

## Mục tiêu và trạng thái

Luồng 2 đề xuất quan hệ giữa các khoản không có câu thao tác sửa đổi tường minh.
Luồng 1 vẫn đọc thao tác trước; cặp đã được luồng 1 nối bị loại khỏi luồng 2.
Mọi quan hệ đều `NEEDS_REVIEW`; AI2 không chọn khoản thắng hoặc kết luận hiệu lực pháp lý.
Cờ mặc định tắt. Code và test tích hợp không thay cổng đo chất lượng P5 hoặc quyết định bật cờ.

## Cấu hình và consent

| Biến | Ý nghĩa |
|---|---|
| `AI2_CONTRACT_GRAPH_ENABLED` | Bật luồng 1; phải bật trước khi luồng 2 chạy |
| `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` | Bật luồng 2; mặc định tắt, đọc một lần mỗi lượt |
| `AI2_CONTRACT_GRAPH_PAIRS_MODEL` | Model phân loại; model thực phục vụ phải mang tên Claude |
| `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL` | Endpoint dành riêng cho phân loại |
| `AI2_CONTRACT_GRAPH_PAIRS_API_KEY` | Khóa tại môi trường chạy; không ghi giá trị vào git |

Adapter HTTP và Kafka gán `record.content_sharing_consent` từ
`request.policy_flags.egress_allowed`. Field record mặc định `False`, không serialize
vào snapshot hoặc wire. Không thêm field vào `ProcessingPolicyFlags` hay JSON Schema.
Consent request phải đồng thời đáp ứng egress server và runtime; request không tự mở egress.
Backend hiện gửi `False`, nên job thật dùng rule-only cho tới khi Backend gửi consent.
Đây là D4/Q1 của plan `261008-1500-ai2-contract-graph-implicit`, đã ghi tại
`DEC-dungskbg2004-1` trong `docs/decisions.md` theo quyết định người dùng.
Bật cờ còn cần verdict P5 và quyết định của người dùng.

Cổng D5 được kiểm theo thứ tự: consent, egress runtime, client đã cấu hình,
model được chọn, ngân sách gọi còn lại và đủ thời gian.

| Lý do rule-only | Điều kiện |
|---|---|
| `NO_CONSENT` | Không có consent chia sẻ nội dung |
| `EGRESS_DENIED` | Runtime không cho phép gửi ra provider |
| `LLM_UNAVAILABLE` | Không có client khả dụng |
| `MODEL_UNSET` | Chưa đặt model pairs |
| `BUDGET_EXHAUSTED` | Hết số HTTP request cho LLM |
| `DEADLINE` | Không đủ thời gian cho một lô và phần dự phòng |

Rule-only vẫn đếm ứng viên; không gọi LLM. Một issue cuối danh sách
`CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` báo lý do, số cặp chưa phân tích và yêu cầu review.
Không có phát hiện không có nghĩa là không có rủi ro. Lỗi builder sinh issue
`CONTRACT_GRAPH_PAIRS_FAILED`; lỗi luồng 1 cho pairs `SKIPPED_GRAPH_FAILED`.
Cả hai trường hợp giữ job enrichment ở `SUCCEEDED` nếu pipeline cơ sở thành công.

## Nhãn, grounding và đường ra Backend

| Nhãn nội bộ | Hướng | Đường ra |
|---|---|---|
| `GENERAL_SPECIFIC` | Khoản chung → khoản riêng | Bảng quan hệ + coverage |
| `CONFLICT` | Không có hướng | Candidate cần đối chiếu + bảng quan hệ + coverage |
| `DUPLICATE` | Không có hướng | Bảng quan hệ + coverage |
| `REFERENCE` | Khoản dẫn chiếu → khoản được dẫn | Bảng quan hệ + coverage |

Mỗi quan hệ phải có span nguyên văn 8–240 ký tự ở cả hai khoản và citation `VALID`.
Output lạ, id tự tạo, span không có trong source hoặc hướng thiếu bị loại.
Span do LLM chọn được giữ trong bảng; evidence của candidate được tạo lại từ **cả node**
và kiểm bằng `CitationResolver`, không dùng span LLM để chiếu finding.
Projection yêu cầu text đầy đủ, kể cả khoản dài hơn 240 ký tự. Khi toàn bộ khoản trải
nhiều trang không có trong một citation kiểm được, candidate bị loại và đếm
`conflict_citation_invalid`; không dùng đoạn đầu ngắn thay cho cả khoản.

`CONFLICT` thành `Candidate(finding_type=COMPARABLE_DIFFERENCE,
disposition=COMPARABLE_DIFFERENCE, model_disposition=UNCLEAR, review_state=NEEDS_REVIEW)`.
Chỉ giữ tối đa 5 candidate pairs/hồ sơ theo thứ tự ứng viên; cặp đã có candidate bị dedupe.
`item_key` dùng địa chỉ canonical hai khoản. Scope body/body là `WITHIN_DOCUMENT`,
annex/annex là `ANNEX_ANNEX`, body/annex là `CONTRACT_ANNEX`.

Backend ánh xạ sang finding `semantic`, `disposition=comparable_difference`, severity
`high` cho `NEEDS_REVIEW` tại `backend/src/contract_intelligence/shared/ai/persistence.py:1095`.
`key_or_topic` nhận `item_key`, fallback finding id tại `persistence.py:1087`.
Hai citation có `source_file_id`, span và evidence riêng từng phía.
Tên nhãn nội bộ không xuất hiện trong lý do finding/issue hoặc field wire mới;
thống kê nhãn chỉ ở `index_contribution.coverage.contract_graph.pairs`.

Pairs được chèn sau `build_contract_context`, `context_issues` và issue luồng 1,
trước khi tạo coverage/index contribution. Chúng không mở khóa so sánh fact,
không sinh thêm `CONTEXT_CONFLICT`, không thay vị trí issue/review ID cũ.

## Coverage thực từ fixture

Các JSON sau lấy từ `pair_record()` + `run_idp`, seed fixture và `FakePairLLM`;
đây là kiểm tra tích hợp deterministic, không phải số đo chất lượng provider thật.

Trước khi bật pairs:

```json
{
  "graph_mode": "operation_first",
  "status": "OK",
  "edges_total": 1,
  "edges_by_op": {"INSERTION": 0, "SUBSTITUTION": 1, "REPEAL": 0, "REJECTION": 0, "SCOPE_LIMIT": 0},
  "unresolved_targets": 0,
  "ambiguous_targets": 0,
  "implicit_edges": 0,
  "auto_pass_enabled": false,
  "truncated": 0,
  "foreign_document_targets": 0,
  "deduped_with_legacy": 0
}
```

Sau khi bật pairs (phần `pairs` đầy đủ; các số luồng 1 giữ nguyên):

```json
{
  "graph_mode": "operation_first+pairs_llm",
  "pairs": {
    "status": "OK", "mode": "llm", "rule_only_reason": null,
    "classifier_model": "claude-fixture", "prompt_version": "pairs-v1",
    "candidates_total": 10, "candidates_kept": 10, "candidates_capped": 0,
    "excluded_luong1": 1, "excluded_external_ref": 1,
    "pairs_sent": 10, "pairs_unclassified": 0, "llm_calls": 2,
    "prompt_tokens": 22, "completion_tokens": 14, "injection_signals": 3,
    "candidates_by_source": {"REFERENCE_CUE": 2, "SAME_ARTICLE": 3, "SAME_KEY": 7},
    "relations_total": 2,
    "relations_by_label": {"GENERAL_SPECIFIC": 1, "CONFLICT": 1, "DUPLICATE": 0, "REFERENCE": 0},
    "rejected": {
      "malformed": 0, "unknown_pair": 0, "duplicate_id": 0, "invalid_label": 0,
      "unrelated": 8, "bad_span": 0, "ungrounded_span": 0, "missing_direction": 0,
      "no_answer": 0, "duplicate_value_mismatch": 0, "conflict_same_span": 0,
      "reference_explicit": 0, "citation_invalid": 0
    },
    "stopped_reason": null, "batches_completed": 2, "conflict_findings": 1,
    "conflict_capped": 0, "conflict_deduped_with_candidates": 0, "conflict_citation_invalid": 0
  }
}
```

Rule-only dùng `graph_mode=operation_first+pairs_rule_only`.
`FAILED`/`SKIPPED_GRAPH_FAILED` dùng `operation_first`, giữ cùng bộ khóa thống kê
với số đếm 0. Cờ pairs tắt không thêm coverage key và không import module `pair_*`.
Golden flag-off 67 case và graph-on 69 case khóa output; rule-only khác golden graph-on
ở coverage pairs, issue/review pairs, số issue và review state job cần review.

## PostgreSQL và ngữ nghĩa thay dòng

Migration `0006_ai2_contract_pair_relations` nối sau `0005_ai2_contract_edges`.
Bảng `ai2.contract_pair_relations` trên metadata graph riêng có PK
`(tenant_id,dossier_id,relation_id)` và index `(tenant_id,dossier_id,job_id)`.
Cột giữ digest snapshot, nhãn/hướng, hai node, nguồn ứng viên, hai span/citation,
model, prompt version, trạng thái review, digest quan hệ và thời điểm.
CHECK chỉ chấp nhận bốn nhãn. Mọi text NUL được lọc trước ghi PostgreSQL.
SQLite không có bảng pairs.

Trong transaction `PostgresJobStore.complete_with_snapshot`, chỉ job `SUCCEEDED`
mới nhất được thay read model/quan hệ, dưới khóa transaction theo tenant/dossier.
`pair_relations_ran=True` khi LLM đã hoàn tất ít nhất một lô hoặc khi `NO_CONSENT`.
Lô hoàn tất có thể không tạo quan hệ: list rỗng vẫn xóa các dòng cũ.
`NO_CONSENT` xóa đề xuất LLM cũ khi consent không còn.

Cờ tắt, lỗi graph/pairs, egress/model/ngân sách/thời gian không đủ hoặc provider hỏng
trước lô đầu giữ `pair_relations_ran=False` và giữ dữ liệu cũ.
Ghi pairs dùng savepoint riêng; lỗi CHECK/DB undo DELETE+INSERT pairs,
giữ quan hệ cũ, vẫn commit snapshot/job và các cạnh luồng 1.
Log `ai2.contract_pair_relations_write_failed` gồm job/tenant/dossier và loại exception.
Tắt cờ không tự xóa các dòng pairs đã có: đây là giới hạn vận hành có chủ ý.

## Injection và ngân sách

Text/context hợp đồng là dữ liệu không đáng tin trong prompt. Signals injection được đếm;
provider không thể tạo quan hệ bằng id không có trong batch hoặc quote ngoài source.
Ngân sách chung đếm mỗi HTTP request, kể cả retry; tối đa 8 cặp/lô, 5 lô phân loại,
context tối đa 300 ký tự, text tối đa 1200 ký tự/khoản, giữ top 40 ứng viên/hồ sơ.
Dự phòng thời gian là 30 giây cộng thời gian timeout × số attempts.
Cặp không phân loại và lý do dừng nằm trong coverage, không được coi là quan hệ âm tính.

## Runbook rollback

Rollback nóng: tắt `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`; output quay về luồng 1,
không xóa dòng cũ và không gửi thêm nội dung tới classifier.

Rollback schema/code (RT-11):

1. Dừng/scale về 0 **mọi** process chạy code P4: API, Kafka worker, `ai2_batch`, job định kỳ.
2. Từ `ai-service/`, đặt `AI2_DATABASE_URL` và chạy
   `python -m app.db.migrate downgrade 0005_ai2_contract_edges`.
   Chỉ `ai2.contract_pair_relations` bị drop; revision quay về 0005.
3. `git revert <commit P4>`, deploy code cũ, sau đó mới khởi động lại process.

Không downgrade khi process P4 còn chạy: mỗi process gọi `migrate()` ở lần dùng DB đầu
có thể tự upgrade schema trở lại. Up/down/up đã được test trên PostgreSQL 16 Docker;
extension pgvector cần image hỗ trợ riêng.

## Số đo

P5 điền kết quả bake-off B/C/E, denominator gold đã duyệt, precision bảo thủ/ước lượng,
recall, grounding, call/token budget và verdict sau chạy thật.
P4 chỉ chứng minh boundary tích hợp/storage, chưa quyết định bật cờ hoặc chất lượng nghiệp vụ.
