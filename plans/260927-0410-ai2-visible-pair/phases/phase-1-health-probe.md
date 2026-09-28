# Phase 1 — Health Probe: `/health` nói thật trạng thái LLM

## Overview
`/health` phân biệt `llm = off | ready | unreachable` thay vì chỉ `off/ready`
theo key-presence. `status` giữ `"ok"`. TDD.

## Requirements
Functional:
- `llm=off` khi không có API key (chưa `configured()`).
- `llm=ready` khi có key VÀ model gọi được.
- `llm=unreachable` khi có key nhưng gọi model fail: connection error hoặc
  404 (model không tồn tại).
- `status` luôn `"ok"`; trường `model` giữ nguyên hành vi hiện tại
  (`llm.model` khi configured, `""` khi không).

Non-functional:
- Probe KHÔNG in/trả secret (api_key, message chứa key).
- Timeout ngắn cho probe (không dùng 45s mặc định của client).
- Unit test KHÔNG chạm mạng — inject fake client (theo pattern
  `monkeypatch.setattr(main, "NineRouterClient", Fake)` đã dùng ở
  `ai-service/tests/unit/test_production_query.py:115`).

## Related Code Files
Modify:
- `ai-service/app/llm/client.py` — thêm method probe (VD `probe_status() -> str`)
  trả `"off" | "ready" | "unreachable"`.
  - `configured()` hiện tại: `ai-service/app/llm/client.py:31-32` (key presence).
  - `complete_json()` bọc call trong try/except và re-raise ở
    `ai-service/app/llm/client.py:49-72` — probe dùng lối gọi rẻ hơn (VD
    `self._client.models.retrieve(self.model)` hoặc một `chat.completions`
    tối thiểu) với timeout ngắn; bắt Exception → phân loại unreachable.
- `ai-service/app/api/main.py` — `health()` (`:682-700`) dùng kết quả probe cho
  trường `llm` thay cho biểu thức `"ready" if llm.configured() else "off"`
  (`:696`). Giữ `status: "ok"` (`:695`) và `model` (`:697`).

Create:
- `ai-service/tests/unit/test_health_llm_probe.py`.

## Implementation Steps
1. **RED** — viết `test_health_llm_probe.py`:
   - Import `app.api.main as main`, `from fastapi.testclient import TestClient`.
   - Test A `llm=off`: fake client `configured()->False`; `GET /health` →
     `body["status"]=="ok"` và `body["llm"]=="off"`.
   - Test B `llm=unreachable` (connection): fake client `configured()->True`,
     probe/complete ném `ConnectionError` (hoặc `APIConnectionError`) → `llm`
     KHÔNG `"ready"` (khẳng định `== "unreachable"`), `status=="ok"`.
   - Test C `llm=unreachable` (404 model): fake ném lỗi 404 model-not-found →
     `llm=="unreachable"`, `status=="ok"`.
   - Test D `llm=ready`: fake trả về thành công → `llm=="ready"`.
   - Test E secret không rò: đặt api_key giả nhận-dạng-được (VD
     `"sk-SECRET-CANARY"`) vào fake, gọi `/health`, khẳng định chuỗi canary
     KHÔNG xuất hiện trong `json.dumps(body)`.
   - Inject qua `monkeypatch.setattr(main, "NineRouterClient", FakeClient)`.
2. Chạy `uv run pytest tests/unit/test_health_llm_probe.py -q` → đỏ.
3. **GREEN** — thêm `probe_status()` vào `NineRouterClient`:
   - Nếu `not self.configured()` → `"off"`.
   - Ngược lại: gọi tối thiểu với timeout ngắn (đọc từ env riêng, VD
     `AI2_LLM_HEALTH_TIMEOUT_SECONDS`, default ~3s; KHÔNG tái dùng 45s ở
     `client.py:27`); thành công → `"ready"`; bắt `Exception` → `"unreachable"`.
     Không log/kèm nội dung exception có thể chứa key.
4. Sửa `health()` (`main.py:696`) dùng `llm.probe_status()`.
5. Chạy lại pytest → xanh; `uv run ruff check .` sạch.

## Success Criteria
- [ ] `test_health_llm_probe.py` có ≥5 test (off / unreachable-conn /
      unreachable-404 / ready / no-secret) và tất cả xanh.
- [ ] `GET /health` trả `status=="ok"` trong mọi trạng thái LLM ở test.
- [ ] Không có chuỗi canary secret trong response body.
- [ ] `uv run pytest -q` toàn suite xanh; `ruff check .` sạch.

## Risk Assessment
| Rủi ro | K×I | Mitigation |
|---|---|---|
| Probe gọi mạng mỗi `/health` → chậm khi LLM treo | M×M | Timeout ngắn riêng; chỉ probe khi `configured()` |
| Rò secret qua exception | L×H | Chỉ map sang nhãn; không đưa message/api_key vào body/log (test E canary) |
| Đổi nhầm `status` → Docker đánh unhealthy | L×H | Test khẳng định `status=="ok"` ở mọi nhánh (`docker-compose.yml:469-476` chỉ mở `/health`) |
| openai client ném loại lỗi khác kỳ vọng | M×M | Bắt `Exception` gốc, không bắt hẹp một class |

## Post
- `verification-P1.json`
