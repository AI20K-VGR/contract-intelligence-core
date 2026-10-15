# NghiÃªn cá»©u: AI2 báº­t Ä‘áº§y Ä‘á»§ trÃªn autodeploy `develop`

**Mode**: depth
**Date**: 2026-10-13
**Sources reviewed**: 8 repo/GitHub records, 4 GitHub Docs pages

## Summary

- Compose hiá»‡n Ä‘Ã£ báº­t graph Ä‘iá»u khoáº£n, pair relations, LLM query, vector query, vector recall vÃ  egress theo máº·c Ä‘á»‹nh `true`; deploy production ghÃ©p cÃ¹ng file Compose nÃ y. Runtime source tá»± fallback `false`, nÃªn chá»‰ cháº¡y trá»±c tiáº¿p service mÃ  thiáº¿u Compose/env sáº½ táº¯t cÃ¡c tÃ­nh nÄƒng Ä‘Ã³ (`docker-compose.yml:489-503`; `ai-service/app/pipeline/idp.py:514-518`; `ai-service/app/api/main.py:209-217`).
- `AI2_EMBEDDING_DISCOVERY_ENABLED` chá»‰ báº­t phÃ©p dÃ² embedding trong `/health`; nÃ³ khÃ´ng pháº£i cÃ´ng táº¯c vector recall. Vector runtime cÃ³ cá» riÃªng (`ai-service/app/api/main.py:798-816`; `ai-service/app/reasoning/vector_recall.py:229-265`).
- Consent chia sáº» ná»™i dung lÃ  quyáº¿t Ä‘á»‹nh theo dossier. `false` tÆ°á»ng minh trong metadata tháº¯ng biáº¿n mÃ´i trÆ°á»ng máº·c Ä‘á»‹nh; Ä‘á»•i global default khÃ´ng báº­t láº¡i dossier Ä‘Ã£ tá»« chá»‘i (`backend/src/contract_intelligence/worker.py:1112-1129`).
- Autodeploy Ä‘Æ°á»£c kÃ­ch hoáº¡t khi cÃ³ push vÃ o `develop`, nhÆ°ng hiá»‡n cáº¥u hÃ¬nh GitHub Environment `production` khÃ´ng cÃ³ protection rule hoáº·c branch policy; deployment hiá»‡n khÃ´ng chá» duyá»‡t. Thiáº¿u `DEPLOY_HOST` sáº½ khiáº¿n workflow xanh dáº¡ng bá» qua, khÃ´ng deploy (`.github/workflows/deploy.yml:22-25,47-53`; GitHub API snapshot ngÃ y 2026-10-13).
- Máº¯t xÃ­ch chÆ°a Ä‘áº¡t yÃªu cáº§u CI: workflow `ai-service` chá»‰ `echo` TODO; ruleset `develop` hiá»‡n chá»‰ yÃªu cáº§u check `pr-guard`. GitHub Actions run má»›i nháº¥t cá»§a nhÃ¡nh hiá»‡n táº¡i Ä‘ang Ä‘á» á»Ÿ Ruff, MyPy vÃ  architecture test; xem [run 38416741068](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/38416741068).
- Äá» xuáº¥t Æ°u tiÃªn: táº¡o config matrix cho product Compose, thÃªm CI tháº­t cho AI service, kiá»ƒm tra deploy fail-closed/readiness vÃ  cáº­p nháº­t má»™t hÆ°á»›ng dáº«n cháº¡y local Ä‘a ná»n táº£ng. KhÃ´ng biáº¿n consent hoáº·c auto-pass thÃ nh cá» â€œbáº­t háº¿tâ€.

## Báº±ng chá»©ng hiá»‡n tráº¡ng

### 1. NhÃ³m cá» runtime vÃ  cháº©n Ä‘oÃ¡n

| NhÃ³m | Quan sÃ¡t trong repo | Káº¿t luáº­n cho plan |
|---|---|---|
| Graph Ä‘iá»u khoáº£n | Builder fallback `false`; Compose Ä‘áº·t `AI2_CONTRACT_GRAPH_ENABLED` máº·c Ä‘á»‹nh `true` (`ai-service/app/pipeline/idp.py:514-515`; `docker-compose.yml:489`). | Product Compose báº­t; CI kiá»ƒm tra config Ä‘Ã£ render, khÃ´ng chá»‰ Ä‘á»c default trong Python. |
| Pair graph/classifier | Cá» riÃªng fallback `false`, Compose Ä‘áº·t `true` (`ai-service/app/pipeline/idp.py:518-519`; `docker-compose.yml:490-491`). Thá»±c thi váº«n cáº§n consent dossier, egress, credentials/model vÃ  budget. | Feature flag ON khÃ´ng chá»©ng minh classifier Ä‘Ã£ cháº¡y. Cáº§n smoke/E2E vá»›i dossier cÃ³ consent vÃ  provider kháº£ dá»¥ng. |
| Query LLM/vector | Backend cá»§a AI2 Ä‘á»c `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_LLM`, `AI2_QUERY_USE_VECTOR`, cáº£ ba fallback `false` (`ai-service/app/api/main.py:209-217`). Compose Ä‘áº·t `true` (`docker-compose.yml:497-500`). | Kiá»ƒm tra ba cá» thá»±c trong container sau deploy; khÃ´ng suy ra tá»« UI hoáº·c `/health`. |
| Vector recall | `AI2_VECTOR_RECALL_ENABLED` fallback `false`; Compose Ä‘áº·t `true` (`ai-service/app/reasoning/vector_recall.py:229-265`; `docker-compose.yml:501`). | Cáº§n test retrieval riÃªng, xÃ¡c nháº­n embedding credentials/egress vÃ  vector DB/pgvector sáºµn sÃ ng. |
| Embedding discovery | `/health` tráº£ `NOT_RUN` khi `AI2_EMBEDDING_DISCOVERY_ENABLED` váº¯ng/táº¯t; chá»‰ báº­t `EMBEDDING_CLIENT.discover()` cho cháº©n Ä‘oÃ¡n (`ai-service/app/api/main.py:798-816`). Vector recall tá»± gá»i discovery á»Ÿ runtime theo egress consent (`ai-service/app/reasoning/vector_recall.py:260-265`). | KhÃ´ng nÃªn báº­t cá» health discovery Ä‘á»ƒ tuyÃªn bá»‘ Ä‘Ã£ báº­t vector; `/health` `NOT_RUN` lÃ  cháº©n Ä‘oÃ¡n chÆ°a cháº¡y, khÃ´ng pháº£i tÃ­nh nÄƒng vector táº¯t. |
| Consent chia sáº» ná»™i dung | Náº¿u metadata cÃ³ bool `ai2_content_sharing_consent`, hÃ m tráº£ Ä‘Ãºng giÃ¡ trá»‹ Ä‘Ã³; env chá»‰ fallback khi khÃ´ng cÃ³ bool (`backend/src/contract_intelligence/worker.py:1112-1129`). Compose Ä‘áº·t default `true` (`docker-compose.yml:431`). | Dossier `false` tÆ°á»ng minh váº«n bá»‹ cháº·n pair LLM. Giá»¯ nguyÃªn; khÃ´ng migration hÃ ng loáº¡t hoáº·c ghi Ä‘Ã¨ consent dÆ°á»›i danh nghÄ©a báº­t feature. Dossier chÆ°a cÃ³ lá»±a chá»n thÃ¬ cáº§n quyáº¿t Ä‘á»‹nh product/compliance vá» default. |
| Auto-pass | `AI2_CONTRACT_GRAPH_AUTO_PASS` fallback `false`; calibration hiá»‡n ghi `n=0` cho má»i operation theo comment trong code, yÃªu cáº§u tá»‘i thiá»ƒu `nâ‰¥60` vÃ  Wilson lower bound `â‰¥0.85` (`ai-service/app/pipeline/contract_graph/review_policy.py:1-7,21-32`). | Giá»¯ táº¯t. ÄÃ¢y lÃ  kiá»ƒm soÃ¡t má»©c tá»± Ä‘á»™ng hÃ³a/cháº¥t lÆ°á»£ng, khÃ´ng pháº£i thiáº¿u runtime graph. |
| Graph UI | Háº±ng `AI2_GRAPH_UI_ENABLED` lÃ  `true` (`frontend/src/components/ai2-graph/contractGraphRuntime.ts:92`). | UI switch hiá»‡n khÃ´ng pháº£i chá»— cáº§n sá»­a; cáº§n E2E xÃ¡c nháº­n API, snapshot, graph vÃ  citation trÃªn product. |

`ai-service/.env.example:129-134` Ä‘áº·t nhiá»u cá» false, cÃ²n Compose override cÃ¡c cá» runtime báº±ng env cá»§a service. `deploy/compose.prod.yml:124-131` chá»‰ náº¡p cáº¥u hÃ¬nh provider/API key, trong khi cÃ¡c cá» runtime cÃ²n láº¡i káº¿ thá»«a tá»« Compose ná»n. VÃ¬ váº­y plan nÃªn ghi rÃµ profile nÃ o lÃ  nguá»“n chuáº©n, vÃ  test Compose sau merge hai file; ngÆ°á»i cháº¡y AI2 ngoÃ i Compose váº«n nháº­n fallback táº¯t.

### 2. Autodeploy, GitHub settings vÃ  CI

- `.github/workflows/deploy.yml:22-25` deploy khi push `develop` hoáº·c khi `workflow_dispatch`; `:30-32` tuáº§n tá»± hoÃ¡ deploy báº±ng concurrency, khÃ´ng há»§y lÆ°á»£t Ä‘ang cháº¡y. Job tham chiáº¿u environment `production` á»Ÿ `:38-43`.
- Náº¿u `DEPLOY_HOST` trá»‘ng, bÆ°á»›c `Is a server configured?` ghi notice vÃ  `configured=false`; cÃ¡c bÆ°á»›c deploy vÃ  kiá»ƒm tra ngoÃ i server Ä‘á»u bá»‹ skip, job khÃ´ng fail (`.github/workflows/deploy.yml:47-53,58-60,97`). Cáº§n Ä‘á»•i hÃ nh vi hoáº·c thÃªm tráº¡ng thÃ¡i kiá»ƒm tra riÃªng Ä‘á»ƒ khÃ´ng nháº§m â€œsuccessâ€ vá»›i â€œÄ‘Ã£ autodeployâ€.
- GitHub Actions secret names hiá»‡n cÃ³ Ä‘á»§ bá»‘n tÃªn cáº§n theo workflow: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` (`gh secret list`, 2026-10-13; chá»‰ tÃªn Ä‘Æ°á»£c Ä‘á»c, khÃ´ng Ä‘á»c giÃ¡ trá»‹). ÄÃ¢y khÃ´ng chá»©ng minh host, SSH, env file hay app Ä‘Ã£ hoáº¡t Ä‘á»™ng.
- GitHub Environment `production` hiá»‡n tráº£ `protection_rules: []`, `deployment_branch_policy: null` (GitHub API `GET /repos/AI20K-VGR/contract-intelligence-core/environments/production`, 2026-10-13). VÃ¬ váº­y chÃº thÃ­ch â€œcÃ³ thá»ƒ Ä‘á»£i reviewerâ€ trong workflow chá»‰ thÃ nh sá»± tháº­t khi admin thiáº¿t láº­p environment ngoÃ i repo.
- Deploy gáº§n nháº¥t trÃªn `develop`: run 38200338190, commit `c74cd1441debd8c1e1507164256aa3aa05409480`, **failure**. Log cho tháº¥y backend healthy vÃ  `[deploy] AI2 full capability: ready`; lá»—i phÃ¡t sinh khi `keycloak_configure.py` xin admin token vÃ  socket timeout, bÆ°á»›c kiá»ƒm tra ngoÃ i bá»‹ skip. Cleanup cÃ²n cáº£nh bÃ¡o `.worktrees/backend-ocr-integration-preview` Ä‘Æ°á»£c khai bÃ¡o lÃ  submodule nhÆ°ng thiáº¿u URL trong `.gitmodules`. ÄÃ¢y lÃ  lá»—i mÃ´i trÆ°á»ng/deploy Ä‘Ã£ quan sÃ¡t, khÃ´ng pháº£i báº±ng chá»©ng AI2 thiáº¿u model config.
- Workflow `ai-service` chá»‰ cháº¡y `echo "no CI defined for ai-service yet"` (`.github/workflows/ai-service.yml:1-23`). Frontend cháº¡y `npm ci`, lint, build (`frontend.yml:5-31`). Backend cÃ³ import-linter, Ruff/format, MyPy, unit/architecture vÃ  integration PostgreSQL (`backend-ci.yml:4-169`).
- API GitHub ruleset hiá»‡n táº¡i: ruleset `develop` yÃªu cáº§u 2 review, resolve review threads, code-owner review vÃ  chá»‰ status `pr-guard`; stale approvals bá»‹ dismiss vÃ  yÃªu cáº§u ngÆ°á»i khÃ¡c approve láº§n push cuá»‘i. Ruleset `branch-naming` báº¯t regex cho tÃªn nhÃ¡nh. ÄÃ¢y lÃ  cáº¥u hÃ¬nh live quan sÃ¡t qua `gh api repos/AI20K-VGR/contract-intelligence-core/rulesets/23406229` vÃ  `/23406227` (2026-10-13), khÃ´ng chá»‰ suy ra tá»« workflow. CI cÃ²n láº¡i hiá»‡n khÃ´ng pháº£i required status check.
- GitHub Actions run má»›i nháº¥t cá»§a nhÃ¡nh `feature/ai2-contract-graph`, SHA `9b9f27bb659b0cebbd17a13da9e1505610694c93`, failure: Ruff hai lá»—i E501; MyPy `worker.py:1123` tráº£ `object` thay vÃ¬ `bool`; architecture test lá»—i cÃ¹ng Ruff. Integration tests vÃ  unit tests pass trong run 38416741068. ÄÃ¢y lÃ  tráº¡ng thÃ¡i trÆ°á»›c sá»­a tiáº¿p theo; cook pháº£i rerun CI trÃªn SHA cuá»‘i cÃ¹ng.

### 3. HÆ°á»›ng dáº«n mÃ¡y má»›i

- `README.md:73-110` Ä‘Ã£ cÃ³ quick start Docker Compose, yÃªu cáº§u Docker Desktop/Node.js 20+, táº¡o `backend/.env`, `ai-service/.env`, cháº¡y Compose vÃ  `npm ci && npm run dev`.
- `HUONG-DAN-CHAY.md:5-64` cÃ²n ghi Ä‘Æ°á»ng dáº«n hai repo riÃªng `ci-backend` / `contract-intelligence-core` vÃ  `npm install`. Máº«u `frontend/.env.local` Ä‘Æ°á»£c nÃªu á»Ÿ Ä‘Ã¢y nhÆ°ng README quick start khÃ´ng táº¡o file nÃ y.
- `frontend/src/api/client.ts:8` fallback API lÃ  `http://127.0.0.1:8080`, trong khi Compose map Backend host `8000` (`docker-compose.yml:367`) vÃ  README/HUONG-DAN Ä‘áº·t `VITE_API_BASE_URL=http://127.0.0.1:8000` (`README.md:92`; `HUONG-DAN-CHAY.md:47-53`). MÃ¡y má»›i bá» qua bÆ°á»›c `.env.local` cÃ³ thá»ƒ gá»i sai cá»•ng; hÆ°á»›ng dáº«n cáº§n yÃªu cáº§u táº¡o file frontend config rÃµ rÃ ng.
- `deploy/README.md:54-105,156-203` mÃ´ táº£ server Linux, host credentials, bootstrap, `deploy/.env.prod`, `ai-service/.env`, secrets Actions vÃ  environment approval. ÄÃ¢y lÃ  production setup riÃªng; khÃ´ng nÃªn trá»™n secrets server vÃ o local guide hoáº·c commit env files.

## Trade-off vÃ  xáº¿p háº¡ng hÆ°á»›ng xá»­ lÃ½

| Háº¡ng | HÆ°á»›ng | Äá»™ phá»©c táº¡p/váº­n hÃ nh | Adoption risk | PhÃ¹ há»£p repo |
|---|---|---|---|---|
| 1 | Khai bÃ¡o config matrix sáº£n pháº©m rÃµ á»Ÿ Compose/profile; dÃ¹ng má»™t profile sáº£n pháº©m lÃ m nguá»“n chuáº©n cho local vÃ  deploy. CI render Compose vÃ  assert cá» runtime, model/key presence dÆ°á»›i dáº¡ng boolean, consent precedence; rollout readiness fail khi host/deploy prereq thiáº¿u. | Vá»«a; cáº§n quáº£n lÃ½ biáº¿n/secret theo profile. | Tháº¥p-vá»«a; Compose Ä‘Ã£ lÃ  Ä‘Æ°á»ng cháº¡y chuáº©n, nhÆ°ng pháº£i test merge vÃ  trÃ¡nh log secret. | Tá»‘t nháº¥t: trÃ¡nh phÃ¢n ká»³ source fallback, local Compose, production overlay. |
| 2 | Chá»‰ sá»­a cÃ¡c default á»Ÿ `ai-service/.env.example`/env files vÃ  giao váº­n hÃ nh Ä‘iá»n thá»§ cÃ´ng. | Ãt code, nhiá»u thao tÃ¡c tay. | Cao; `.env.example` bá»‹ nháº§m lÃ  runtime contract, má»—i mÃ¡y/server cÃ³ thá»ƒ khÃ¡c; secrets khÃ´ng Ä‘Æ°á»£c xÃ¡c minh. | Chá»‰ dÃ¹ng lÃ m template onboarding, khÃ´ng Ä‘á»§ Ä‘á»ƒ báº£o Ä‘áº£m autodeploy. |
| 3 | Äáº·t má»i `false` thÃ nh `true`, gá»“m consent/auto-pass/diagnostic, táº¡i source hoáº·c migration. | Thoáº¡t nhÃ¬n Ä‘Æ¡n giáº£n, rá»§i ro váº­n hÃ nh/chÃ­nh sÃ¡ch cao. | Ráº¥t cao; cÃ³ thá»ƒ bá» qua dossier tá»« chá»‘i, má»Ÿ egress khÃ´ng chá»§ Ã½, cho phÃ©p káº¿t luáº­n tá»± Ä‘á»™ng chÆ°a calibration. | KhÃ´ng phÃ¹ há»£p; Ä‘á»•i end state cá»§a user consent vÃ  quality gate. |

## Khuyáº¿n nghá»‹ cÃ³ thá»© tá»±

1. **ÄÃ³ng gÃ³i default-on Ä‘Ãºng chá»—**: duy trÃ¬ code fallback táº¯t; profile product Compose Ä‘áº·t ON cho graph, pair classifier, query LLM/vector, vector recall vÃ  egress khi nhÃ  váº­n hÃ nh Ä‘Ã£ cáº¥p credentials. KhÃ´ng thÃªm `AI2_EMBEDDING_DISCOVERY_ENABLED` vÃ o danh sÃ¡ch feature ON; náº¿u muá»‘n diagnostics chá»§ Ä‘á»™ng cháº¡y thÃ¬ mÃ´ táº£ riÃªng vÃ  giá»›i háº¡n call/cost.
2. **KhÃ´ng cÆ°á»¡ng Ã©p consent**: env consent default chá»‰ tÃ¡c Ä‘á»™ng dossier thiáº¿u trÆ°á»ng; bool `false` hiá»‡n cÃ³ pháº£i tiáº¿p tá»¥c cháº·n egress classifier. E2E cáº§n cáº£ dossier consent true (pair model Ä‘Æ°á»£c phÃ©p gá»i) vÃ  false (khÃ´ng cÃ³ LLM egress), cÃ¹ng dossier má»›i/thiáº¿u cá» Ä‘á»ƒ xÃ¡c nháº­n chÃ­nh sÃ¡ch máº·c Ä‘á»‹nh. User/business pháº£i chá»‘t default cho há»“ sÆ¡ má»›i; khÃ´ng suy ra tá»« cá» Compose.
3. **Giá»¯ auto-pass OFF** Ä‘áº¿n khi calibration artifacts Ä‘á»§ tá»‘i thiá»ƒu vÃ  gate Wilson Ä‘áº¡t ngÆ°á»¡ng; ON graph khÃ´ng Ä‘á»“ng nghÄ©a tá»± Ä‘á»™ng cháº¥p nháº­n quan há»‡.
4. **Thay AI-service placeholder báº±ng CI cÃ³ tháº­t**, thÃªm test compose-config/flag precedence vÃ  API contract; sau Ä‘Ã³ lÃ m cÃ¡c status checks nÃ y required trÃªn ruleset `develop`. Hiá»‡n ruleset chá»‰ yÃªu cáº§u `pr-guard`, nÃªn â€œall CI greenâ€ chÆ°a Ä‘Æ°á»£c GitHub báº£o vá»‡.
5. **Báº£o Ä‘áº£m autodeploy cÃ³ thá»ƒ chá»©ng minh**: thiáº¿u host/secret hoáº·c readiness nÃªn fail cÃ³ Ã½ nghÄ©a; giá»¯ `concurrency`; xÃ¡c nháº­n production environment `develop`-only vÃ  reviewer náº¿u muá»‘n duyá»‡t trÆ°á»›c. Fix/Ä‘iá»u tra timeout Keycloak cá»§a deploy gáº§n nháº¥t vÃ  lá»—i submodule cleanup trÆ°á»›c khi coi deploy pass. GitHub docs xÃ¡c nháº­n environment protection/secrets náº±m á»Ÿ repository settings vÃ  chá»‰ cÃ³ hiá»‡u lá»±c khi Ä‘Æ°á»£c cáº¥u hÃ¬nh [3][4].
6. **Há»£p nháº¥t hÆ°á»›ng dáº«n mÃ¡y má»›i** vÃ o má»™t trang canonical: clone nhÃ¡nh Ä‘Ã£ nÃªu, yÃªu cáº§u Docker Compose v2/Node 20+, copy Ä‘Ãºng `.env.example` nhÆ°ng khÃ´ng commit giÃ¡ trá»‹ bÃ­ máº­t, táº¡o `frontend/.env.local` vá»›i host ports Ä‘ang dÃ¹ng, Ä‘iá»n provider keys cÃ³ quyá»n/egress, cháº¡y stack, smoke-check health + login + upload OCR + AI2 graph/pairs + vector query, rá»“i lá»‡nh stop/log/cleanup. Cáº­p nháº­t hÆ°á»›ng dáº«n cÅ© hoáº·c redirect sang trang canonical.

## Äiá»u kiá»‡n nghiá»‡m thu Ä‘á» xuáº¥t cho cook

- Compose config vá»›i profile product resolve **true** cho `AI2_CONTRACT_GRAPH_ENABLED`, `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`, `AI2_PROCESSING_EGRESS_ALLOWED`, `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_LLM`, `AI2_QUERY_USE_VECTOR`, `AI2_VECTOR_RECALL_ENABLED`; secret/API key khÃ´ng Ä‘Æ°á»£c in trong log/artifact.
- Unit/integration tests chá»©ng minh: flag OFF giá»¯ backward-compatible path; ON táº¡o Graph edges + pairs khi input/provider/consent Ä‘á»§; consent `false` tÆ°á»ng minh tháº¯ng global default; vector recall cÃ³ runtime path; thiáº¿u provider credential bÃ¡o degraded/failure rÃµ, khÃ´ng bÃ¡o â€œÄ‘Ã£ so sÃ¡nhâ€.
- CI cuá»‘i cÃ¹ng cÃ³ checks thá»±c: AI-service lint/type/test/build; Backend CI; Frontend lint/build; pr-guard; deploy validation. Ruleset `develop` yÃªu cáº§u má»i status check cáº§n thiáº¿t, khÃ´ng chá»‰ `pr-guard`.
- Deploy thá»­ trÃªn `develop` xÃ¡c nháº­n server tiáº¿n Ä‘Ãºng SHA, service container cháº¡y flags Ä‘Ãºng, backend/AI2 health/readiness, public HTTPS/auth vÃ  full user journey; thiáº¿u DEPLOY_HOST pháº£i bá»‹ bÃ¡o lÃ  â€œnot deployedâ€ vÃ  khÃ´ng bá»‹ tá»•ng há»£p nháº§m thÃ nh release deployed.
- HÆ°á»›ng dáº«n Ä‘Æ°á»£c thá»±c thi trÃªn má»™t checkout/mÃ¡y sáº¡ch khÃ´ng cÃ³ `.env` cÃ¡ nhÃ¢n; kiá»ƒm tra command, ports, auth, upload, OCR, graph evidence, query/vector vÃ  secret hygiene. Má»™t README Ä‘Ãºng chá»¯ nhÆ°ng chÆ°a dogfood khÃ´ng pháº£i báº±ng chá»©ng end-to-end.

## Nguá»“n

1. [GitHub Docs â€” Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) | GitHub | tÃ i liá»‡u hiá»‡n hÃ nh, truy cáº­p 2026-10-13 | credibility: high | mÃ´ táº£ pull-request target/base, branch/path filters vÃ  merge-result ref.
2. [GitHub Docs â€” Deploying with GitHub Actions](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments) | GitHub | tÃ i liá»‡u hiá»‡n hÃ nh, truy cáº­p 2026-10-13 | credibility: high | environment, protection rules, concurrency vÃ  push/dispatch trigger.
3. [GitHub Docs â€” Managing environments for deployment](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) | GitHub | tÃ i liá»‡u hiá»‡n hÃ nh, truy cáº­p 2026-10-13 | credibility: high | reviewer/branch restriction do settings cáº¥u hÃ¬nh; secret bá»‹ gate bá»Ÿi environment.
4. [GitHub Docs â€” Secrets](https://docs.github.com/en/actions/concepts/security/secrets) | GitHub | tÃ i liá»‡u hiá»‡n hÃ nh, truy cáº­p 2026-10-13 | credibility: high | secret chá»‰ kháº£ dá»¥ng khi workflow tham chiáº¿u; environment secret chá» approval.
5. [GitHub Docs â€” Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) | GitHub | tÃ i liá»‡u hiá»‡n hÃ nh, truy cáº­p 2026-10-13 | credibility: high | `workflow_dispatch` pháº£i tá»“n táº¡i trÃªn default branch, cÃ³ thá»ƒ chá»n `--ref` khÃ¡c.
6. Repo hiá»‡n táº¡i: `.github/workflows/deploy.yml`, `deploy/deploy.sh`, `deploy/compose.prod.yml`, `docker-compose.yml`, `ai-service/app/*`, `backend/src/contract_intelligence/worker.py`, `README.md`, `HUONG-DAN-CHAY.md`, `deploy/README.md` | source of truth cho implementation hiá»‡n commit.
7. Live read-only GitHub API/CLI snapshot (2026-10-13): `gh secret list`; `gh api repos/AI20K-VGR/contract-intelligence-core/environments/production`; rulesets `/23406229`, `/23406227`; Actions runs 38200338190 vÃ  38416741068. KhÃ´ng Ä‘á»c/ghi giÃ¡ trá»‹ secret.

## NgoÃ i pháº¡m vi / giá»›i háº¡n

- ChÆ°a má»Ÿ secrets values, deploy host config, database hoáº·c env cá»§a server; hiá»‡n tráº¡ng credential â€œcÃ³ tÃªn secretâ€ khÃ´ng chá»©ng minh giÃ¡ trá»‹ há»£p lá»‡.
- KhÃ´ng deploy, khÃ´ng sá»­a workflow, khÃ´ng cháº¡y eval model tháº­t, khÃ´ng truy cáº­p há»£p Ä‘á»“ng ngÆ°á»i dÃ¹ng.
- GitHub Docs lÃ  nguá»“n hÃ nh vi ná»n táº£ng; báº±ng chá»©ng config repo láº¥y tá»« source vÃ  read-only API snapshot. KhÃ´ng xÃ¡c minh tá»« browser trÃªn production.

## CÃ¢u há»i cÃ²n má»Ÿ

- Product cÃ³ chá»n consent máº·c Ä‘á»‹nh báº­t cho há»“ sÆ¡ má»›i khÃ´ng? ÄÃ¢y lÃ  chÃ­nh sÃ¡ch chia sáº» ná»™i dung há»£p Ä‘á»“ng cho provider, khÃ´ng thá»ƒ suy ra tá»« mong muá»‘n â€œbáº­t full AI2â€.
- Owner cÃ³ thá»ƒ cáº¥u hÃ¬nh GitHub Environment `production`, deployment branch policy `develop`, vÃ  reviewer rule theo quyá»n/plan cá»§a repository khÃ´ng?
- NgÆ°á»i váº­n hÃ nh cÃ³ thá»ƒ kháº¯c phá»¥c Keycloak admin-token timeout vÃ  lÃ m sáº¡ch `.worktrees/...` submodule metadata trÃªn server/repo khÃ´ng?
- API key OpenAI/provider vÃ  outbound egress trÃªn production cÃ³ há»£p lá»‡ táº¡i thá»i Ä‘iá»ƒm deploy khÃ´ng? Cáº§n kiá»ƒm tra báº±ng readiness/run tháº­t, khÃ´ng ghi secret vÃ o bÃ¡o cÃ¡o.
