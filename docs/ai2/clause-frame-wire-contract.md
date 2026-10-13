# Contract semantic AI2 v1

P4 bổ sung extension tùy chọn trong job hiện tại. Backend vẫn quản lý ACL, run và publish; AI2 chỉ
đề xuất. Quality gate trên hồ sơ thật và manual approval schema/limits chưa đạt nên producer mặc
định tắt.

`semantic_profile` trên `be.ai2.processing.request.v1` có capability `ai2.semantic.v1`, tenant,
contract type, version, digest, alias version/digest, aliases đã active, trạng thái activation và
bounds. Digest SHA256 tính trên JSON canonical UTF-8 (`sort_keys`, dấu phân cách `,`/`:`,
`ensure_ascii=False`), gồm toàn bộ trường DTO trừ `digest`; default phải explicit trước khi ký.
Service envelope ký toàn bộ payload raw. Retry giữ chính xác payload raw và profile trong
`config_snapshot`; đổi alias cần run mới.

Consumer hỗ trợ extension trước producer. Request cũ không có profile tiếp tục đường cũ; không thêm
`semantic_profile:null` vào raw signed request đã lưu. `AI2_SEMANTIC_ENABLED` mặc định false. AI2
cần `AI2_SEMANTIC_CONTEXT_CAPS` JSON đủ sáu số nguyên hữu hạn: `max_hops`, `max_nodes`,
`max_context_tokens`, `max_output_tokens`, `max_llm_calls`, `max_seconds`. Request vượt cap hoặc
thiếu cap bị reject khi producer được bật. Bounds là trần kỹ thuật, không phải policy accuracy đã
freeze. Backend chỉ tạo profile khi có trusted `AI2_SEMANTIC_PROFILE_CONFIG` gồm version,
contract_type, context_bounds, alias_proposal_minimum_length; thiếu cấu hình không tự bật.

`result.semantic_extension` có version `ai2.semantic.v1`, tenant/dossier/profile digest/alias pins,
frames, rows, pairs, timeline, alias_drafts và coverage. Rows là frame IDs và phải resolve đủ, duy
nhất. Frame chứa family, contract profile, source snapshot/document, evidence, slots và key
provenance. Slot gồm `value_type=DECIMAL|TEXT|NONE`, `value` dạng chuỗi hoặc null,
`state=GROUNDED|UNKNOWN|ABSENT|UNSUPPORTED`, evidence và reason. Decimal là chuỗi chính xác; không
chuyển qua float, không đổi unknown thành zero.

Evidence giữ source_ref/raw và Citation đầy đủ. Ref `#spanN` của extractor resolve về node gốc;
CitationResolver kiểm tra document/snapshot, page revision, raw span, character offsets, line IDs và
source/quote digest. Thiếu hoặc sai evidence giữ record nhưng hạ slot thành UNKNOWN và hiện coverage
reason. Citation chứa dữ liệu nguồn thật; geometry không có thì không tự dựng.

Pair giữ semantic disposition riêng khỏi macro legacy, reason, hai phía evidence, candidate_sources
và method CLOSED_SYMBOL hoặc TENANT_ALIAS. Tất cả pair vẫn NEEDS_REVIEW. Timeline chứa
source/target, REFERENCES hoặc AMENDS, date role/date value, acceptance/value slot/proposed value và
reasons. AMENDS chỉ có proposed value khi target, effective date, acceptance source và quantity đều
đủ; vẫn NEEDS_REVIEW, không LEGAL_WINNER. Thiếu/mơ hồ/cycle/branch được giữ thành review gap.

Macro compatibility: DUPLICATE→comparable_match khi grounded;
COMPARABLE_DIFFERENCE→comparable_difference;
SCOPE_DIFFERS/GENERAL_VS_SPECIFIC/NOT_COMPARABLE→not_comparable; trạng thái còn
lại→insufficient_evidence. Typed frame/pair và pins lưu ở `finding_side.value_snapshot.semantic`;
phương pháp alias giữ ở finding.method. Full extension lưu nguyên trong run.ai2_result_json.
Rows/timeline/coverage đều có review targets. SUCCEEDED không đồng nghĩa COMPLETE/evidence_ready;
negotiated profile thiếu extension là SEMANTIC_NOT_MEASURED.

Runtime duy nhất debit mọi HTTP attempt, retry, JSON-format fallback và alias proposal.
`max_output_tokens` truyền vào cả SDK requests. Absolute operation deadline chặn retry/backoff và
late reservation sau deadline; context deadline không giả thành job deadline. UTF-8 byte count là
upper bound bảo thủ cho input tokens. Node/frame/prompt/call/time caps tạo partial coverage với
reason và giữ provenance. Chỉ slot từ source context được local extractor chứng minh cùng
actor/action/modality mới được nâng certainty; ambiguity/cycle/cross-snapshot/cap gap không được
nâng.

Alias proposal chỉ gửi cụm trừu tượng, dùng minimum length policy đã pin, luôn DRAFT; không đổi
active lexicon. Draft được giữ cùng run để operator và expert duyệt bằng P3 governance. Không tự tạo
approval, nhãn độc lập hay receipt activation.

Rollback: tắt producer và enrichment, giữ consumer dual-read, các run/profile cũ và typed evidence.
Run mới có profile nhưng producer off trả semantic NOT_MEASURED/review; không xóa lịch sử, không
downgrade SQL schema. Không bật rollout cho tới khi BE/AI2 owner duyệt schema/limits và reviewer
cuối duyệt quality evidence.

Kiểm chứng cơ học: `test_frame_job.py`, `test_frame_context_runtime.py`, queued raw signed payload
trong `test_ai2_postgres_store.py`, và `backend/tests/integration/test_clause_frame_roundtrip.py`
dùng network HTTP process thật + PostgreSQL dùng riêng. Test cuối yêu cầu
`AI2_FRAME_TEST_DATABASE_URL`; thiếu URL là fail, không skip. Fixtures đều synthetic; kết quả test
không thay approved gold/eval độc lập trên hồ sơ thật.

Proposed AMENDS is projected as `candidate_amendment`. Its side metadata contains `frame`,
`timeline` and the same profile/alias pins; pair findings contain `frame`, `pair` and pins.
The amendment side order is old target on side A, proposed source on side B. Both remain reviewable.

Coverage `covered` means that a record/slot has a representation or assessed source; it is not
a business accuracy score. Rows, pairs and timeline records remain NEEDS_REVIEW even when covered.
Node/context/call counters apply to the semantic stage as a whole, not as a new budget per frame.
UTF-8 input accounting includes local units plus system/user prompt bytes across calls.

Legacy serializers may send `semantic_profile: null`; the request schema accepts it as OFF.
Omitted legacy profile remains omitted by the Backend builder. Signed raw requests are never
normalized by model defaults before persistence or queued restart.

Finite hard ranges below are schema constraints. Operator-chosen values must still be approved
before enabling the producer; this table does not freeze an accuracy or activation policy.

| Bound | Schema range |
|---|---|
| max_hops | 0..8 |
| max_nodes | 1..256 |
| max_context_tokens | 1..32768 |
| max_output_tokens | 1..8192 |
| max_llm_calls | 0..20 |
| max_seconds | 1..300 |

The HTTP/PG regression uses a synthetic ACTIVE alias snapshot v7 solely to test method/pin
roundtrip. It does not approve or activate a real tenant alias and is not an independent gold label.
Both same-heading and different-heading explicit amendments are tested. Ambiguous or invalid
targets preserve distinct unresolved timeline records and do not receive a proposed value.
