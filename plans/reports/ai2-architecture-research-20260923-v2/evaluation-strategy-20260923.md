# AI2 evaluation strategy và eval-bootstrap assessment

Ngày: 2026-09-23  
Mục tiêu: xác định bộ đánh giá đủ để kiểm soát extraction/grounding hiện tại và long-running HITL architecture tương lai.

## 1. Current-state assessment

Repository đã có evaluation framework đáng kể, gồm:

- strategy/config: `evals/eval_config.json`, `evals/cards/ai2_contract_package.json`, `evals/cards/ai2_grounded_query.json`;
- corpus manifests: `evals/corpus/candidate_manifest.json`, `evals/corpus/golden_manifest.json`;
- sample corpus cho contract package và grounded query, bao gồm bilingual, boundary, conflict, table, long document, low-quality scan, prompt injection và scope;
- deterministic scorer/runner/mirror: `evals/eval_types/...`;
- release/CI: `evals/release_verification.py`, `evals/scripts/run_production_evals.py`, `evals/ci/production-evals.yml`;
- production fixtures và quality report template.

**Kết luận:** framework đủ làm nền cho schema/evidence/query regression. Chưa đủ để chứng minh durable HITL, event replay/order, reconnect, concurrent approval, crash recovery, cancellation, timeout hoặc SSE/WebSocket behavior vì các capability đó chưa tồn tại trong runtime hiện tại.

Không tạo thêm code/eval fixture trong phase research này.

## 2. Ground-truth tiers

| Tier | Nội dung | Người xác nhận | Dùng để |
|---|---|---|---|
| T0 | Schema/provenance invariants deterministic | AI2/BE engineer | contract gate |
| T1 | Evidence-labeled facts/citations/relations | reviewer nghiệp vụ | extraction/grounding |
| T2 | Document segmentation + contract/annex relation | reviewer nghiệp vụ + adjudicator | boundary/relation |
| T3 | Cross-document comparison and contradiction | legal/domain reviewer | comparison correctness |
| T4 | HITL decision/state/event trace | system owner + security reviewer | workflow/recovery |
| T5 | Operational failure/recovery trace | BE/infra owner | resilience/load |

T1–T3 chưa thể gọi là ground truth production nếu chưa có adjudication protocol. Các case hiện có là candidate/golden artifacts trong repository, nhưng cần kiểm tra provenance và người duyệt trước khi dùng làm legal accuracy claim.

## 3. Golden case format đề xuất

Mỗi case phải có:

- `case_id`, `input_snapshot_id`, schema/version và tenant classification;
- logical documents/boundaries với evidence refs;
- expected document type/role/parent relation;
- expected facts: value, normalized value, unit, status, confidence band và citation set;
- expected relations/comparisons/conflicts;
- expected abstentions: `INSUFFICIENT_EVIDENCE`, `UNVERIFIABLE`, `AMBIGUOUS`, `STALE`;
- expected HITL checkpoint, allowed commands, actor policy và terminal state;
- expected event sequence/digest cho workflow cases;
- adjudicator, timestamp, disagreement/resolution và evidence basis.

Raw AI1 JSON không tự động là ground truth; nó là input/evidence candidate.

## 4. Metrics

### 4.1 Extraction và evidence

| Metric | Unit/denominator | Gate proposal |
|---|---|---|
| Schema validity | output fields hợp lệ / output fields bắt buộc | 100% cho contract gate |
| Citation validity | facts có citation trỏ đúng input evidence / facts cần citation | 100% cho publishable facts |
| Citation entailment | citations thực sự support claim / sampled claims | domain threshold, chưa chốt |
| Fact precision | facts đúng / facts được output | theo field/case, không dùng aggregate một mình |
| Fact recall/completeness | facts đúng output / facts trong ground truth | theo field/category |
| Boundary exactness | page/block spans overlap expected boundary | report precision/recall, ambiguity riêng |
| Relation accuracy | relation type+direction đúng / expected relations | phải tính false positive |
| Conflict detection recall | conflict cases được flag / conflict cases trong GT | không được đổi conflict thành value im lặng |
| Abstention correctness | abstain đúng khi evidence thiếu / cases cần abstain | đo false-assertion và false-abstention riêng |

### 4.2 HITL correctness

- Checkpoint correctness: checkpoint có xuất hiện đúng tại ambiguity/risk case.
- Command authorization correctness: allowed/denied đúng theo actor/role.
- Approval correctness: decision áp dụng đúng generation/checkpoint/version.
- Stale propagation: số artifact stale đúng dependency graph.
- Impact preview completeness: mọi downstream artifact bị ảnh hưởng đều được liệt kê.
- Audit completeness: actor, timestamp, reason, correlation, causation, before/after có đủ.

### 4.3 Event/recovery

- Event ordering pass rate.
- Duplicate apply rate (mục tiêu 0 semantic duplicate).
- Replay convergence: state sau replay = state canonical.
- Snapshot fallback success rate.
- Recovery success after process kill/restart.
- Exactly-one applied command under retry/concurrent delivery.
- Lost pending checkpoint rate (mục tiêu 0).
- Side-effect duplication rate (mục tiêu 0 cho tool có gate).

### 4.4 Performance/operations

- submit-to-first-safe-event latency;
- checkpoint creation latency;
- resume-to-completion latency;
- p95/p99 command latency;
- timeout/expiration rate phân biệt với user no-response;
- active stream count, reconnect rate, replay-gap rate;
- queue wait, worker lease expiry, retry count;
- memory/event backlog dưới long-running load.

Không đặt ngưỡng SLO cụ thể khi chưa có production workload; ngưỡng phải là human-approved configuration.

## 5. Test layers

| Layer | Mục tiêu | Ví dụ |
|---|---|---|
| Unit | reducer, schema, normalizer, dependency graph | stale propagation, CAS transition |
| Contract | AI1→AI2, command/event, AG-UI adapter | missing citation, version mismatch |
| Integration | DB/outbox/worker/tool | commit + event failure, retry |
| Workflow | multi-step durable run | wait/resume/expire/cancel/restart |
| Transport | SSE, reconnect, replay | Last-Event-ID gap/snapshot |
| Security | tenant/role/redaction/tool | forbidden stream/command, injection |
| Load/soak | long-running concurrency | many waiting runs, lease recovery |
| Regression | fixed golden corpus | existing `evals` cards/manifests |
| Manual/adjudication | domain correctness | bilingual precedence, boundary ambiguity |

## 6. Required golden suites

1. Clean contract facts/citations.
2. One JSON containing body + annex with no AI1 segmentation.
3. Multiple JSONs in same dossier with explicit/ambiguous relation.
4. Boundary split/merge and impact preview.
5. Low OCR confidence, scan, truncated clause and multipage table.
6. Numeric/date/currency conflicts.
7. Bilingual governing-language conflict.
8. Multi-party names and defined terms.
9. Missing evidence and correct abstention.
10. Prompt injection/untrusted OCR.
11. Human context conflict.
12. Approval/reject/edit/context request.
13. Concurrent approval and stale command.
14. Duplicate/out-of-order/gap/replay.
15. Crash/restart/worker lease recovery.
16. Timeout/expiration/cancellation.
17. Downstream unavailable/partial result/retry side effect.
18. Tenant isolation and audit redaction.

## 7. Regression policy

- Mỗi bug production trở thành immutable regression case, có expected behavior và source evidence.
- Không overwrite golden case khi output thay đổi; tạo versioned expectation và ghi migration rationale.
- Tách score regression hiện tại khỏi architecture-readiness score.
- Không cho phép LLM judge là sole gate; dùng deterministic checks trước, human adjudication cho legal semantics.
- Fail closed khi citation/schema/security gate fail; không “pass” nhờ aggregate score.

## 8. Evaluation gaps cần human approval

- Ai là adjudicator cho disagreement về legal meaning?
- Field nào bắt buộc 100% citation/precision trước publish?
- Bao nhiêu ambiguity được phép auto-complete?
- TTL, latency, concurrent runs và stream limits là bao nhiêu?
- Có được dùng synthetic/mutated data để bổ sung case hay chỉ real reviewed documents?
- Retention của evaluation inputs/outputs có được phép giữ raw contract không?

## 9. Acceptance của evaluation phase

Phase evaluation chỉ đạt khi:

1. Ground-truth schema được version hóa và có adjudication metadata.
2. Deterministic scorer phân biệt đúng fact/citation/abstention/stale/event errors.
3. Workflow tests chứng minh replay/recovery/idempotency, không chỉ output cuối.
4. Security tests chứng minh tenant/role/redaction.
5. Load test có dữ liệu và SLO được phê duyệt.
6. CI regression không làm mất các contract hiện tại của `ocr.json`/AI1 snapshot.
