---
id: 261013-2153-ai2-develop-autodeploy
title: "AI2 develop autodeploy and cross-machine setup"
description: "Bật đầy đủ AI2 theo consent từng hồ sơ, sửa CI/deploy, và chuẩn hoá hướng dẫn chạy trên máy mới."
status: in_progress
priority: P1
effort: "L: 6 phase tuần tự; cần CI, backend/AI service, GitHub settings và provider thật"
tags: [ai2, ci, autodeploy, consent, developer-setup]
mode: hard
tdd: true
branch: feature/ai2-contract-graph
created: 2026-10-13
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-1-ci-green.md
  - phases/phase-2-ai2-runtime-defaults.md
  - phases/phase-3-consent-rollout.md
  - phases/phase-4-consent-enforcement.md
  - phases/phase-5-develop-autodeploy.md
  - phases/phase-6-local-runbook.md
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Plan: AI2 develop autodeploy and cross-machine setup

## Tổng quan

Hoàn tất đường đi từ PR vào `develop` đến deploy có thể xác minh; bật các khả năng AI2 trong đường chạy sản phẩm và khi nhà phát triển chạy đầy đủ stack cục bộ. Mỗi hồ sơ có consent chia sẻ nội dung rõ ràng, mặc định bật theo chỉ thị trước đó của chủ sản phẩm, có thao tác tắt dễ tìm và có hiệu lực cho lần xử lý/truy vấn tiếp theo. Khi consent tắt, AI2 vẫn chạy xử lý xác định cục bộ; LLM, embedding/vector và pair classifier không được nhận nội dung hồ sơ.

Luồng dữ liệu: Backend lấy snapshot OCR hiện hành, metadata/consent của hồ sơ và giới hạn xử lý; ký envelope theo dossier rồi gửi `be.ai2.processing.request.v1` → AI2 xác minh chữ ký, chuyển snapshot thành record chuẩn, chạy graph xác định; egress chỉ xảy ra nếu feature được bật, giới hạn server cho phép, consent hồ sơ bật và budget còn. AI2 trả graph/trạng thái/chứng cứ; Backend lưu theo job + snapshot hiện hành; UI đọc graph và citation. Truy vấn đi qua ACL Backend → payload ký có consent theo hồ sơ → AI2 AND consent với giới hạn server trước LLM/vector → trả câu trả lời/chứng cứ. Nguồn hiện có thể lần theo ở `backend/src/contract_intelligence/shared/ai/canonical_processing.py:376-384`, `ai-service/app/pipeline/ai1_snapshot_adapter.py:188-193`, `ai-service/app/api/main.py:959-983`, `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:1615-1667` và `frontend/src/pages/DossierStructurePage.tsx:496-563,1166-1190`.

Deploy chỉ chạy sau push/merge vào `develop` hoặc gọi thủ công (`.github/workflows/deploy.yml:22-25`). PR không tự deploy. Không tuyên bố deploy thành công nếu thiếu host, SSH, health/readiness, Keycloak hoặc kiểm tra public URL.

## Quyết định đã khoá

- Dùng sáu phase tuần tự theo yêu cầu của Tech Lead. Đã chờ câu trả lời về gộp phase nhưng không nhận được phản hồi; giả định chủ sản phẩm chấp nhận sáu phase và ghi nhận giả định này trong Validation Log.
- Theo phê duyệt trước đó “Bật cho tất cả hồ sơ”, backfill một lần consent `true` cho mọi dossier hiện hữu đang hoạt động, kể cả giá trị `false` trước rollout. Ghi audit đầy đủ giá trị cũ và rollout ID; sau rollout, lựa chọn opt-out mới của người dùng được ưu tiên và không bị rollback ghi đè.
- Dossier mới được tạo với consent `true` lưu tường minh theo phê duyệt đã có; consent field thiếu/null/sai kiểu luôn fail closed. Chủ sở hữu có thể opt-out qua điều khiển rõ ràng trong UI/API. Consent là chính sách truyền dữ liệu theo hồ sơ, không phải cờ tính năng. Consent không-true chặn pair classifier, LLM xử lý, embedding/vector và LLM/vector truy vấn; các đường xác định cục bộ vẫn hoạt động.
- Mọi quyết định egress phải là AND giữa consent hồ sơ và giới hạn phía server/runtime. Payload chỉ được quyền thu hẹp egress; request không thể bật vượt cấu hình server. Giữ chữ ký/envelope bắt buộc và kiểm tra toàn vẹn.
- Đặt ON mặc định sản phẩm cho graph, pair, LLM truy vấn, vector truy vấn/recall và egress ở mọi runtime fallback/sample được hỗ trợ. Vẫn cho phép operator đặt `false` làm công tắc ngắt. Không xem cờ ON là bằng chứng provider đã cấu hình hoặc suy luận thật đã chạy.
- Giữ `AI2_EMBEDDING_DISCOVERY_ENABLED=false` vì đây chỉ là dò model trong `/health`, không phải vector runtime (`ai-service/app/api/main.py:798-816`). Giữ `AI2_CONTRACT_GRAPH_AUTO_PASS=false` vì đây là chính sách duyệt của người (`ai-service/app/pipeline/contract_graph/review_policy.py:1-7,21-32`). Giữ yêu cầu chữ ký (`ai-service/app/api/main.py:878-885`; `ai-service/.env.example:135`).
- `AI2_REQUIRE_DATABASE` là bảo vệ độ bền dữ liệu: bật trong full local/product profile và template, giữ khả năng tắt riêng cho unit tests cô lập. Không được báo graph “đã lưu” khi thực tế chạy kho tạm.
- Không nới quyền ACL, không tự phê duyệt quan hệ, không thay đổi chữ ký/schema envelope thiếu kiểm thử tương thích.

## Ràng buộc và bằng chứng hiện trạng

- `docs/code-standards.md` và `docs/system-architecture.md` đã đọc; cook phải đọc lại trước khi sửa vì hai tài liệu có thể đổi. Kiến trúc yêu cầu không tạo quyết định pháp lý tự động và egress phải tuân thủ consent + runtime policy.
- CI nhánh gần nhất thất bại ở run [38416741068](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/38416741068), SHA `9b9f27bb659b0cebbd17a13da9e1505610694c93`: Ruff E501 tại `backend/src/contract_intelligence/infrastructure/ai_adapters.py:720,729`; MyPy `backend/src/contract_intelligence/worker.py:1123`; architecture test lỗi theo Ruff. Unit và PostgreSQL integration đã qua trong run này, nhưng phải chạy lại trên SHA cuối.
- `.github/workflows/ai-service.yml:3-24` hiện chỉ in TODO; `.github/workflows/backend-ci.yml:4-169` có lint/format/type/unit/architecture/PostgreSQL integration; `.github/workflows/frontend.yml:5-32` có npm/lint/build.
- Compose bật các cờ AI2 nhưng nhiều fallback code và `ai-service/.env.example` vẫn false (`docker-compose.yml:483-503`; `ai-service/app/pipeline/idp.py:514-519`; `ai-service/app/api/main.py:209-217`; `ai-service/app/reasoning/vector_recall.py:229-238`; `.env.example:129-139`). Backend query settings cũng false (`backend/src/contract_intelligence/config/settings.py:234-244`) và Compose chưa truyền đủ cờ query cho Backend. Decision matrix bên dưới phân loại toàn bộ cờ liên quan.
- Dossier metadata lưu JSON và có soft-delete (`backend/src/contract_intelligence/contract/infrastructure/persistence/orm.py:33-63`). Hàm consent hiện trả giá trị bool đã lưu, nếu chưa có mới đọc env; source fallback hiện là false (`backend/src/contract_intelligence/worker.py:1112-1129`). Consent hiện được truyền vào field riêng, trong khi adapter lấy egress runtime riêng (`ai-service/app/pipeline/ai1_snapshot_adapter.py:188-193`), nên service phải thực hiện AND.
- Hai đường query Backend hiện truyền policy global, không gắn consent dossier: `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:1615-1667` và `backend/src/contract_intelligence/api/v1/dossiers.py:107-135`. AI2 đang bỏ qua policy request tại `/query` và chỉ dùng server env (`ai-service/app/api/main.py:209-217,959-983`); phải thay bằng chính sách thu hẹp được ký và AND với cap của AI2.
- Deploy gần nhất trên develop run `38200338190` failed sau khi AI2 báo capability ready; `deploy/keycloak_configure.py:66-93` xin admin token rồi gặp timeout. Compose chỉ đợi Keycloak `service_started`/healthcheck tắt (`docker-compose.yml:174-178,269-271`). Workflow thiếu `DEPLOY_HOST` hiện ghi notice rồi skip mà job xanh (`.github/workflows/deploy.yml:47-53,58-60,97`).
- Bốn tên secret `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` có trong GitHub, nhưng giá trị không được đọc. GitHub Environment `production` snapshot không có protection rule/branch policy; ruleset develop mới yêu cầu `pr-guard`. Không khẳng định secret, host, environment policy hay outbound provider đang hợp lệ.
- Theo `hs-run plan next --fact-subjects ...`, caller codemap không khả dụng vì repo không có `codemap.yaml`; vì vậy đã dùng grep có phạm vi các module/route cụ thể và đọc trực tiếp call path. Caller chính được liệt kê tường minh ở trên; không suy ra từ số kết quả grep.

## Ma trận quyết định cờ AI2

| Cờ / hiện trạng | Phân loại | Đích mặc định và ranh giới |
|---|---|---|
| `AI2_CONTRACT_GRAPH_ENABLED` false ở source | Tính năng graph xác định | ON trong source, sample và product; operator có thể đặt false. |
| `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` false ở source/builder | Pair classifier | ON mặc định; classifier chỉ gọi khi dossier consent và global egress cho phép, model/key/budget sẵn sàng. |
| `AI2_PROCESSING_EGRESS_ALLOWED` false ở source/sample | Cap egress xử lý | ON theo profile sản phẩm; server operator có thể tắt, luôn AND với dossier consent. |
| `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_LLM`, `AI2_QUERY_USE_VECTOR` false ở AI2 source/sample | Tính năng hỏi đáp ngoài egress | ON mặc định cho full profile; từng request chỉ thu hẹp quyền, global service cap vẫn thắng. |
| `AI2_VECTOR_RECALL_ENABLED` false ở source/sample | Retrieval runtime | ON mặc định; cần embedding provider và DB/vector backend hoạt động; consent false tắt embedding và recall. |
| Backend `ai2_query_egress_allowed`, `ai2_query_use_vector` false | Caller policy | ON mặc định ở Backend sản phẩm và truyền rõ sang AI2, nhưng không thể nới service cap. |
| `AI2_CONTENT_SHARING_CONSENT_DEFAULT` false ở worker | Chính sách truyền dữ liệu theo hồ sơ | ON cho dossier mới và backfill một lần do chủ sản phẩm đã duyệt; opt-out từng dossier luôn thắng. |
| `AI2_REQUIRE_DATABASE` false ở source/sample, true trong Compose | Bảo vệ tính bền vững | ON trong template/full stack; chỉ cho phép OFF ở test cô lập. Không tính đây là tính năng AI. |
| `AI2_EMBEDDING_DISCOVERY_ENABLED` false | Chẩn đoán `/health` | Giữ OFF; không ảnh hưởng vector runtime. |
| `AI2_CONTRACT_GRAPH_AUTO_PASS` false | Chính sách review/chất lượng | Giữ OFF; chỉ mở sau calibration/gate riêng, không thuộc phạm vi này. |
| `AI2_QUERY_REQUIRE_SIGNATURE` true | Bảo vệ xác thực request | Giữ true; không có unsigned fallback trong product. |

## Phases

| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | CI xanh và baseline consent | — | M |
| 2 | Default-on runtime AI2 | P1 | M |
| 3 | Consent rollout + điều khiển hồ sơ | P2 | L |
| 4 | Enforce consent trên mọi egress | P3 | M |
| 5 | Deploy develop fail-closed | P4 | M |
| 6 | Hướng dẫn máy mới + full-stack evidence | P5 | M |

Phase tuần tự; không có file source thuộc hai phase. P3 backfill và điều khiển người dùng theo sau P2 defaults; P4 chỉ hoàn thiện hiệu lực consent trên processing/query; P5 có thể triển khai code sau đó nhưng không được chạy deploy thật trước các điều kiện GitHub/provider; P6 dogfood sau khi các thay đổi code đã hoàn tất.

## Ngoài phạm vi

- Không merge PR, không thay branch ruleset, GitHub Environment, host hay secret trong giai đoạn cook nếu chưa có bước vận hành được ủy quyền riêng.
- Không đổi model/provider hay chạy benchmark hợp đồng; chỉ chạy smoke test inference khi key hợp lệ, egress thật và dữ liệu kiểm thử được cho phép.
- Không thay đổi thuật toán candidate generation/classifier, thresholds, auto-pass, human review outcomes, ACL, hoặc dữ liệu/consent của dossier sau khi người dùng opt-out.
- Không coi `/health` hoặc giá trị env là chứng minh graph, LLM, embedding, vector DB hay egress production hoạt động; cần request smoke có thể quan sát.

## Acceptance toàn plan

- [ ] Trên SHA cuối của nhánh, AI-service có lint/format/type/unit/integration check thật; Backend lint/format/MyPy/import-linter/unit/architecture/PostgreSQL integration; Frontend install/lint/build/test; Compose render assertions; `pr-guard`. Mọi check bắt buộc do GitHub settings xác nhận, và tất cả xanh.
- [ ] Từng capability matrix có test cho default ON, biến `false` operator override, credential thiếu/degraded và cap egress. Không có secret nào trong log, report hoặc artifact.
- [ ] Consent true cho phép eligible external inference; consent false chặn mọi outbound content ở processing LLM/pair/embedding/vector và query LLM/vector, ngay request kế tiếp. Deterministic graph/UI/read evidence tiếp tục chạy. Global service cap false chặn mọi dossier.
- [ ] Backfill có dry-run count, rollout ID, per-dossier audit giá trị trước/sau, bỏ qua dossier đã xóa/purge, chạy lại idempotent. Rollback chỉ khôi phục nếu giá trị hiện tại vẫn đúng giá trị rollout đã đặt; không đảo quyết định opt-out mới.
- [ ] Consent toggle kiểm tra ACL, ghi actor + timestamp + giá trị vào append-only audit cùng transaction, hiển thị trạng thái và hiệu lực. E2E chứng minh tắt rồi chạy lại không gửi nội dung ra ngoài.
- [ ] Deploy chỉ báo success sau cùng SHA, remote Compose health, Keycloak ready, external HTTPS/auth probe và smoke AI2; thiếu bất kỳ deploy secret/host/config nào làm job fail rõ, không được xanh kiểu skip. Runbook phân biệt CI xanh với deploy thật.
- [ ] Người phát triển sạch trên Windows PowerShell và Linux/macOS shell hoàn thành setup từ clone đến login, OCR, graph, citations, query/vector smoke bằng hướng dẫn; provider keys và network egress được xác minh mà không log giá trị.

## Kiểm thử theo lớp

| Lớp | Phạm vi | Gate |
|---|---|---|
| Unit | Consent resolver, env flag parser/override, runtime cap AND consent, vector/LLM call count=0 khi opt-out, audit/idempotent backfill/rollback-safe. | Mỗi thay đổi code dùng red → green; tests không phụ thuộc key thật. |
| Contract/Integration | Signed processing/query payloads, HMAC intact, Backend routes cả hai query API truyền đúng consent, AI2 thực thi cap server, DB PostgreSQL ghi audit+metadata nguyên tử, pair+graph deterministic. | Backend unit/integration; AI-service wire/IDP/query tests; Compose config assertion. |
| E2E/Smoke | Compose full stack, upload sample PDF, OCR, graph pair/operation, citation source/target, query LLM/vector; opt-out re-run không outbound. | Chỉ chạy provider thật khi credentials/egress có sẵn; giữ evidence redacted. |
| CI/Deploy | Workflows thật, `develop` required checks, production environment/branch gate, same SHA deployed, Keycloak and external auth. | GitHub Actions link/SHA và deploy smoke; không dùng run baseline thay bằng chứng mới. |
| Docs | Clean clone PowerShell + Linux/macOS, command/port/provider/key hygiene. | Dogfood checklist, không chỉ spellcheck. |

## Rollback

- P1: revert riêng các sửa lint/type/workflow nếu regression; giữ consent default không được hạ im lặng vì đó là quyết định sản phẩm đã duyệt. Nếu cần đảo default, thay đổi có kiểm soát qua explicit config và thông báo người dùng.
- P2: đặt biến runtime false hoặc revert source defaults; giữ signatures/auto-pass unchanged. Tắt riêng từng capability theo env; các graph đã lưu vẫn đọc được.
- P3: stop script trước commit nếu audit/metadata không thống nhất; rollback bù có điều kiện từ audit, chỉ đụng record mà rollout event vẫn là consent event mới nhất và giá trị còn true. API toggle có thể revert độc lập, nhưng không xoá audit.
- P4: rollback adapter/policy wiring về fail-closed consent; giữ cap global false khi điều tra. Không revert sang hành vi request tin client.
- P5: revert workflow/healthcheck/deploy retry trên commit trước đó; ngăn deploy mới bằng workflow dispatch/branch ops, không xoá host/secret. Nếu deploy lỗi sau cập nhật, restore cùng image SHA trước theo deploy runbook và xác minh public health.
- P6: revert docs link/page khi không chính xác; không tác động runtime.

## Rủi ro

| Rủi ro (khả năng × tác động) | Biện pháp |
|---|---|
| Mở egress với toàn bộ hồ sơ do default/backfill (Cao × Rất cao) | Chỉ thực hiện theo phê duyệt trước; backfill có count/dry-run, nhật ký append-only, rollout ID/rollback conditional, toggle opt-out dễ tìm; AND global cap + consent tại AI2 chứ không tin UI. |
| Chi phí/provider unavailable làm timeout hoặc AI2 báo thành công giả (Cao × Cao) | Budget/timeouts giữ nguyên; thiếu key/egress hiện rõ degraded/error, không báo model đã chạy; provider smoke chỉ là gate riêng; graph deterministic không lệ thuộc provider. |
| Dossier opt-out nhưng đường query khác vẫn egress (Trung bình × Rất cao) | Sửa hai caller đã truy dấu; signed field; AI2 AND với server cap; tests cho cả hai routes, payload thiếu consent, cap=false, replay/invalid signature. |
| Keycloak vẫn chưa sẵn sàng khi deploy (Trung bình × Cao) | Compose health condition + retry có deadline, bắt timeout tường minh; fake-timeout regression test; health/external probe chặn deploy. |
| CI job xanh mà không deploy/không chạy AI service (Cao × Cao) | AI-service workflow thật; missing-secret fail-closed; branch required checks/env rule phải được kiểm tra ngoài code; báo deploy success chỉ sau post-deploy probes. |
| Backfill ghi đè giá trị user mới chọn hoặc dữ liệu đã xóa (Thấp × Cao) | Snapshot candidate set, transaction, bỏ deleted/purged, optimistic predicate và audit; rollback bỏ qua record đã đổi. |

## Red-team disposition

| Finding | Disposition |
|---|---|
| RT-1 — Consent thiếu/malformed có thể bị hiểu thành true, và code có thể được bật trước khi backfill/audit hoàn tất. Bằng chứng: P1 `phase-1-ci-green.md` trước disposition; P4 `phase-4-consent-enforcement.md:36,47`; hiện resolver `backend/src/contract_intelligence/worker.py:1122-1127`; P3 backfill diễn ra riêng. | **Accept — P1/P2/P3/P4.** Missing/null/wrong-type fail closed xuyên processing và hai query routes; hồ sơ mới ghi true tường minh tại create; cap egress giữ OFF cho tới khi backfill/audit/UI xong, rồi operator bật rõ ràng. Thêm tests cho consent absent/malformed và cap OFF. |
| RT-2 — `workflow_dispatch` có thể chạy ref khác `develop`; environment policy không được workflow tự áp đặt. Bằng chứng: `.github/workflows/deploy.yml:21-25` mô tả dispatch deploy branch được chọn; P5 trước cập nhật chưa buộc guard ref trong job. | **Accept — P5.** Tách preflight job không có secrets/environment: `develop` tiếp tục, ref khác fail rõ; deploy job `needs: preflight`, chỉ sau đó gắn production environment. Thêm tests cho cả hai ref; production environment branch restriction/approval là defense-in-depth. |
| RT-3 — workflow mới và CI hiện có có thể xanh nhưng không bắt buộc trên PR vì ruleset chỉ yêu cầu `pr-guard`. Bằng chứng: research `ai2-deploy-features-ci-local-setup-research.md:41,64`; P1 chỉ xác minh workflow xanh, P5 chỉ yêu cầu quan sát settings. | **Accept — P1/P5.** Trong P1 ghi rõ status check names ổn định cho backend, frontend, AI service và `pr-guard`; P5 phải xác minh các check đều required trên ruleset `develop`, và thêm thao tác cấu hình qua GitHub API/admin trong cook khi quyền cho phép. Nếu quyền thiếu, acceptance CI-required BLOCKED và không mở PR/merge; không coi xanh đơn thuần là gate. |
| RT-4 — rollback có thể race với opt-out giữa lần kiểm tra và ghi bù; unit test không chứng minh đồng thời PostgreSQL. Bằng chứng: P3 rollback step trước disposition và `phase-3-consent-rollout.md:45`. | **Accept — P3.** Dùng row lock hoặc CAS, check + write trong cùng transaction; chuyển test rollout sang integration PostgreSQL và điều phối race opt-out/rollback. |
| RT-5 — tài liệu hứa Windows + Linux/macOS nhưng dogfood có thể chỉ chạy một POSIX OS. Bằng chứng: `phase-6-local-runbook.md:5,38`. | **Accept — P6.** Nghiệm thu PowerShell + ít nhất một POSIX; nếu quảng bá hỗ trợ riêng cả Linux và macOS thì phải dogfood cả hai hoặc thu hẹp tuyên bố. |

### Red-team report

Independent adversarial pass covered Failure Mode Analyst, Security Adversary and Bad-day Operator. Five findings (three high, one medium, one platform-coverage risk) were accepted above and propagated to the owning phases. Evidence is anchored in the plan, workflow source, and research report; no external setting or secret value was read for this review.

## Validation Log và câu hỏi còn mở

- Đã đọc `docs/code-standards.md`, `docs/system-architecture.md`, `harness/rules/harness-contract.md`, `harness/rules/verification-mechanism.md`; khi cook cần đọc lại và đối chiếu ownership.
- Sáu phase giữ theo chỉ dẫn của Tech Lead sau khi chờ mà không có phản hồi về khả năng gộp phase; đây là giả định cấu trúc, không phải yêu cầu thêm từ chủ sản phẩm.
- Đã chạy `hs-run plan next --fact-subjects contract_intelligence.shared.query_policy::server_query_policy_flags,contract_intelligence.shared.ai.canonical_processing::build_processing_policy,app.pipeline.ai1_snapshot_adapter::adapt_be_ai2_processing_request,app.api.main::_query_policy_flags`; tool trả `unavailable: no codemap.yaml`. Do đó caller inventory dùng grep có giới hạn và trace trực tiếp; các caller hiện xác nhận được liệt kê trong phần bằng chứng.
- Chưa đọc secret values, không truy cập production, không chạy inference hoặc deploy trong plan step. Workflow/environment repo snapshot, secret names, run failures cần re-check tại cook/ship vì có thể đã thay đổi.
- Câu hỏi cần xác minh trước deploy: (1) GitHub Environment `production` đã khóa branch `develop` và approval theo chính sách chưa? (2) Bốn deploy secrets có giá trị hợp lệ? (3) host/network Keycloak, HTTPS và provider API/egress thực có hoạt động? Nếu bất kỳ điều kiện nào chưa được xác nhận, PR có thể sẵn sàng nhưng không được báo deploy sản phẩm đã xong.
