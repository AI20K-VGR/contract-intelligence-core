# AI2-04 — Edge-case Test Matrix

**Phiên bản:** v0.2
**Mục đích:** Chuyển các edge-case trong [AI2-02](AI2-02-extraction-engine-design.vi.md) thành fixture/test matrix cho AI2.

## Quy ước

- `PASS`: output có thể publish sau grounding gate.
- `REVIEW`: nhãn ma trận cho `ReviewState.NEEDS_REVIEW`, tạo issue và không suy đoán.
- `INSUFFICIENT`: thiếu evidence để trả lời.
- `BLOCKED`: bị chặn bởi ACL, policy, lifecycle hoặc egress.

Mỗi test phải ghi input snapshot/version, actor/tenant context, tool calls, output state, citation resolution, cost/usage và audit event.

## Matrix

| ID | Tình huống thực tế | Component chính | Hành vi mong đợi | State | Acceptance |
|---|---|---|---|---|---|
| EC-001 | Hợp đồng 50+ trang | Router/Reasoning | Scout outline, xử lý unit, checkpoint; không full dump | PASS/REVIEW theo unit | AC-004..007, AC-031 |
| EC-002 | Điều khoản dài | Clause/chunk | Chunk theo node/bullet/level, giữ parent/span | PASS/REVIEW | AC-004/007 |
| EC-003 | Không đánh số | Structure | `UNNUMBERED_BLOCK`, giữ raw label | REVIEW nếu mapping mơ hồ | AC-004/011 |
| EC-004 | Trùng số điều | Structure | Node riêng theo document/parent | REVIEW | BR-RUL-002 |
| EC-005 | Nhảy số | Structure | Ghi gap, không tự tạo clause | REVIEW | BR-RUL-001/002 |
| EC-006 | Numbering hỗn hợp | Structure | Giữ level/parent nguồn | PASS/REVIEW | AC-004 |
| EC-007 | Header/footer xen giữa | Reconstruction handoff | Không nối mù; giữ source blocks | REVIEW nếu boundary mơ hồ | AC-004 |
| EC-008 | Definition được tham chiếu | Retrieval | Lấy definition liên quan làm breadcrumb | PASS/INSUFFICIENT | AC-006/007 |
| EC-009 | Tham chiếu phụ lục/điều | Retrieval + relation graph | Resolve edge có citation/snapshot; thiếu hoặc ambiguous target không bịa | INSUFFICIENT | AC-007 |
| EC-010 | Bảng 300 dòng | Table/codegen | Model chỉ thấy metadata/mẫu; code chạy toàn bảng | PASS/REVIEW | AC-001, AC-006 |
| EC-011 | Bảng hai trang | Table assembler | Dùng continuation/header/row identity | REVIEW nếu thiếu signal | AC-001 |
| EC-012 | Subtotal/footnote | Table validator | Tách boundary, không tự cộng tổng thiếu | REVIEW | AC-001/007 |
| EC-013 | Merged cell | Table assembler | Derived context trỏ cell nguồn | REVIEW nếu thiếu span | AC-001/009 |
| EC-014 | Header hai tầng | Table schema | Giữ raw parent/child header path | PASS/REVIEW | AC-001 |
| EC-015 | Empty/dash/N/A/zero | Table transform | Phân biệt sentinel, không coi missing là zero | REVIEW nếu ambiguity | AC-001/007 |
| EC-016 | `1.234`/`1,234`/ngoặc âm | Codegen | Normalize bằng code, giữ raw value | PASS/REVIEW | AC-001/009 |
| EC-017 | Hai bảng cùng số cột | Table assembler | Không nối nếu thiếu title/header/row evidence | REVIEW | AC-001 |
| EC-018 | Cell OCR tách thành nhiều row | Table assembler | Dùng row boundary; không chắc thì review | REVIEW | AC-001 |
| EC-019 | Bảng landscape/rotation | Citation | Dùng page transform/rotation đúng revision | PASS/REVIEW | AC-009 |
| EC-020 | MST/pháp nhân lặp/lệch | Fact/candidate | Giữ mọi fact, tạo candidate | REVIEW | AC-008/009 |
| EC-021 | Số bằng chữ khác số | Fact grounding | Hai anchor, không tự chọn | REVIEW | AC-009 |
| EC-022 | Ngày tương đối | Fact extractor | Giữ raw/validity, không bịa mốc | INSUFFICIENT | AC-007 |
| EC-023 | Giá trị bậc thang | Fact schema | Giữ condition/scope, không flatten | PASS/REVIEW | AC-006/008 |
| EC-024 | USD và VND | Candidate pairer | Không tự quy đổi, `NOT_COMPARABLE` | REVIEW | AC-008 |
| EC-025 | Alias tenant | Profile resolver | Chỉ dùng profile version đã pin | PASS/REVIEW | AC-011/024 |
| EC-026 | Tên giống, MST khác | Entity resolver | Blocking/scoring; link, không merge | REVIEW | AC-008 |
| EC-027 | Body/table/annex mâu thuẫn | Candidate | Evidence hai phía, không chọn bản đúng | REVIEW | AC-008 |
| EC-028 | Implicit amendment | Comparison | Candidate chỉ khi câu sửa/effective context đủ rõ | REVIEW | AC-008 |
| EC-029 | Nhiều annex cùng sửa | Comparison | Hiện chain/uncertainty, không precedence | REVIEW | AC-008 |
| EC-030 | Khác scope | Candidate pairer | `NOT_COMPARABLE` | PASS as technical finding | AC-008 |
| EC-031 | Song ngữ lệch nghĩa | Semantic comparison | Giữ span hai ngôn ngữ | REVIEW | AC-008/009 |
| EC-032 | Cosmetic/substantive change | Alignment | Deterministic align trước LLM classify | PASS/REVIEW | AC-008 |
| EC-033 | Defined-term cascade | Relation graph | Edge `DEFINES`/`USES_DEFINED_TERM`, surface affected sections, không legal winner | REVIEW | AC-008 |
| EC-034 | Aggregation thiếu một source | Retrieval | Không tổng hợp; trả nguồn hiện có + insufficient | INSUFFICIENT | AC-007 |
| EC-035 | Prompt injection trong PDF | Tool security | Xem PDF là untrusted; chỉ allowlist tools | BLOCKED/REVIEW | AC-025 |
| EC-036 | Index đang processing/failed | Index pointer | Dùng active index cũ | PASS | AC-015/016 |
| EC-037 | Query EN, doc VI | Semantic retrieval | Cross-lingual retrieval nhưng citation bắt buộc | PASS/INSUFFICIENT | AC-007 |
| EC-038 | Overlap tạo duplicate | Dedupe | Dedupe theo source/context key | PASS | AC-005/006 |
| EC-039 | Confidence cao nhưng sai | Grounding/eval | Không auto-accept; grounding/gold check | REVIEW | AC-009/030 |
| EC-040 | Boundary ambiguous | Classifier | Bounded classifier; không resolve thì review | REVIEW | AC-004/011 |
| EC-041 | Skew/watermark/con dấu | Scan quality | Quality/coverage flag, không đoán | REVIEW | AC-009 |
| EC-042 | Chữ ký che số | Scan/citation | Partial evidence + issue | REVIEW | AC-009 |
| EC-043 | Scan quality không đều | Page processor handoff | Per-page state, không bỏ denominator | PARTIAL/REVIEW | AC-030 |
| EC-044 | OCR sai dấu tiếng Việt | Fact/citation | Raw/normalized riêng, audit span | REVIEW | AC-009 |
| EC-045 | Encrypted/corrupt/empty PDF | Intake | Input error rõ, không coi empty là success | BLOCKED | AC-004 |
| EC-046 | Trang trắng/ảnh không chữ | Page inventory | Giữ inventory, không tạo fact | PARTIAL | AC-001/030 |
| EC-047 | File vượt budget | Orchestrator | Dừng có kiểm soát, trả partial/policy error | PARTIAL/REVIEW | AC-031 |
| EC-048 | Nhiều annex làm nổ unit | Queue/checkpoint | Incremental queue, resume | PARTIAL/PASS | AC-031 |
| EC-049 | Rerun đồng thời | Worker fencing | Lease/idempotency; worker cũ không publish | BLOCKED/RETRY | AC-015/016 |
| EC-050 | Embedding cost lớn | Vector recall/cost gate | Discovery trước, batch/cache theo snapshot-model-dimension, quota; vector chỉ recall | RATE_LIMITED/RETRY | AC-017 |
| EC-051 | Profile đổi | Versioning | Run mới, giữ result cũ | PASS | AC-024 |
| EC-052 | Re-OCR một page | Revision lineage | Citation revision mới; review cũ stale | REVIEW | AC-009/024 |
| EC-053 | Vector cross-tenant | ACL/vector index | Metadata tenant/dossier filter + citation recheck ở read/write | BLOCKED | AC-012 |
| EC-054 | Cache sai quyền | Cache/ACL | Key có ACL revision; hit recheck ACL | BLOCKED | AC-012/017 |
| EC-055 | Egress chưa approval | Policy/vector gate | Block vector/LLM + audit; deterministic retrieval vẫn chạy trong policy scope | BLOCKED | AC-025/033 |
| EC-056 | Legal hold/purge | Lifecycle | Hold chặn purge; artifact nằm inventory | BLOCKED | AC-021/022 |

## Test record tối thiểu

```json
{
  "case_id": "EC-011",
  "tenant_id": "tenant_test",
  "dossier_id": "dossier_table_02",
  "input_snapshot_digest": "sha256:...",
  "profile_version": 1,
  "policy_version": 1,
  "expected_state": "REVIEW",
  "expected_citations": ["table_page_1", "table_page_2"],
  "expected_no_claims": ["complete_total"],
  "actual_tool_calls": [],
  "actual_state": null,
  "audit_event_id": null
}
```

## Release gates

Không đạt release nếu:

1. citation resolve sai hoặc source/page revision không pin;
2. request cross-tenant trả content, metadata hoặc resource existence;
3. table thiếu row/cell nhưng hệ thống vẫn khẳng định tổng;
4. index mới fail làm mất active index cũ;
5. `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE` bị coi là answered;
6. purge bỏ sót embedding, index, cache hoặc operational copy;
7. report thiếu `n`, denominator, version hoặc failed/not-run.
