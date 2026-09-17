# contract-ocr-lab

Baseline OCR cho hợp đồng và phụ lục tiếng Việt/Anh, phục vụ technical spike Sprint 1. Chạy cục bộ, phân loại từng trang PDF, ưu tiên trích xuất text sẵn có, thử OCR và preprocessing, xuất JSON chuẩn hóa và báo cáo đánh giá. Không có RAG, suy luận điều khoản, huấn luyện hay database. Sprint 1 không cần frontend; mục [Chạy nhanh](#chạy-nhanh-demo-ui-tải-pdf-lên-xem-idp) bên dưới có thêm một demo UI cục bộ để tải PDF lên và xem thử kết quả IDP (phân loại, cấu trúc, fact, citation, xung đột) bằng tay, nằm ngoài phạm vi benchmark chính. Các mục 1-9 phía sau là tài liệu đầy đủ cho pipeline benchmark/CLI.

## Chạy nhanh: Demo UI (tải PDF lên, xem IDP)

Cách nhanh nhất để tự test: chạy **hai server riêng biệt** — backend (API OCR + AI2) và frontend (trang tĩnh) — rồi kéo thả một PDF hợp đồng vào, xem ngay phân loại/cấu trúc/fact/citation/xung đột trên trình duyệt. Không cần biết CLI hay manifest.

```text
frontend/index.html  ← trang tĩnh, không có Python          (port 5500)
        │  fetch() qua HTTP + CORS
        ▼
src/contract_ocr/web/app.py  ← backend FastAPI, chỉ trả JSON  (port 8000)
```

Hai server độc lập hoàn toàn: frontend chỉ là 1 file HTML tĩnh (không cần cài gì để chạy nó), backend là API thuần không biết gì về giao diện. Chạy trên 2 máy khác nhau cũng được, miễn frontend trỏ đúng địa chỉ backend.

**Bước 1 — cài đặt backend (chỉ cần làm 1 lần).** Mở terminal tại thư mục `ai-service/` (thư mục chứa file README này):

```powershell
uv sync --locked --python 3.12 --extra dev --extra web --extra paddle
```

Lệnh này cài FastAPI cho backend và PaddleOCR (OCR thật, chạy trên CPU) vào venv `.venv` có sẵn. Frontend không cần cài gì (thuần HTML/CSS/JS). Máy này không có GPU NVIDIA nên **không cài** `--extra deepseek` — DeepSeek-OCR-2 trong code hiện bắt buộc CUDA, sẽ không chạy được cục bộ trên máy này dù có cài.

**Bước 2 — chạy backend, ở một cửa sổ PowerShell:**

```powershell
.\.venv\Scripts\python.exe scripts\serve_backend.py
```

Backend chạy tại `http://127.0.0.1:8000`, tự mở `/docs` (Swagger UI) để test API độc lập, không cần frontend — bấm "Try it out" ở `/api/ocr` để upload PDF thẳng từ đó.

**Bước 3 — chạy frontend, ở một cửa sổ PowerShell khác:**

```powershell
.\.venv\Scripts\python.exe scripts\serve_frontend.py
```

Frontend chạy tại `http://127.0.0.1:5500`, tự mở trình duyệt. Dòng nhỏ dưới tiêu đề trang báo trạng thái kết nối backend (chấm xanh = đã nối được `http://127.0.0.1:8000`). Backend chạy ở địa chỉ khác thì thêm `?api=http://host:port` vào URL, hoặc sửa `<meta name="api-base">` trong `frontend/index.html`.

Để dừng, bấm `Ctrl+C` ở từng cửa sổ.

**Bước 4 — dùng:** kéo một file PDF hợp đồng (bắt buộc) vào ô "Tải PDF cần xử lý" — phân tích chạy tự động ngay bằng engine đang chọn ở dropdown, không cần thao tác gì thêm. Ra ngay: phân loại `contract`/`appendix`/`other`, cây **Điều → Khoản → Điểm**, các fact (bên A/B, giá trị hợp đồng, ngày ký, thời hạn thanh toán) kèm citation (trang/dòng/bbox) và **confidence**, cùng tab **Evaluation**. Muốn kiểm tra xung đột thì kéo thêm PDF vào ô "Phụ lục" bên dưới (kéo nhiều file cùng lúc cũng được — 0..N phụ lục, mỗi file có nút "x" để bỏ ra và phân tích lại, kết quả nhóm riêng theo từng phụ lục). Đổi engine ở dropdown rồi bấm "Phân tích lại" nếu PDF hoá ra là bản scan (PyMuPDF không đọc được text, cần PaddleOCR hoặc một Vision API):

- **PyMuPDF** — chỉ đọc text có sẵn trong PDF, không OCR. Nhanh, dùng cho PDF có text-layer (ví dụ các file trong `data/raw/digital/`). PDF scan sẽ báo `SKIPPED`/không ra fact nào vì không có text để đọc — đúng như thiết kế, không phải lỗi.
- **PaddleOCR** — OCR ảnh thật, dùng cho PDF scan (ví dụ `data/raw/scanned_bad/`). Trên CPU máy này khá chậm (có thể vài chục giây đến vài phút một trang); hạ DPI xuống 150 ở "Tuỳ chọn nâng cao" để test nhanh hơn.
- **DeepSeek-OCR** — bị mờ (disabled) trên máy này vì thiếu GPU NVIDIA.
- **OpenAI GPT-5.6 Terra (Vision)** — ⚠️ gửi ảnh trang PDF lên API của OpenAI, không còn xử lý cục bộ. Chỉ dùng cho file demo/không nhạy cảm, không bao giờ dùng cho hợp đồng thật. Xem [mục "OpenAI/Gemini/DeepSeek (tuỳ chọn)"](#openaigeminideepseek-tuỳ-chọn-ocr-qua-vision-api) để bật.
- **Gemini 3 Flash (Vision)** — ⚠️ tương tự OpenAI nhưng gửi lên Google Gemini. Trong test nội bộ, độ chính xác tiếng Việt (giữ đúng dấu) tốt hơn rõ rệt so với PaddleOCR, và nhanh hơn nhiều (~30s/trang so với vài phút của PaddleOCR CPU).
- **DeepSeek Flash (API, Vision)** — ⚠️ tương tự nhưng gửi lên DeepSeek. **Không phải cùng model** với "DeepSeek-OCR" ở trên: đây là model chat đa năng có vision (`deepseek-flash`) qua API hosted, còn "DeepSeek-OCR" ở trên là model chuyên OCR (`DeepSeek-OCR-2`) chạy local, cần GPU — hai model khác nhau, chỉ trùng tên hãng.

File PDF upload chỉ lưu tạm ở backend lúc xử lý rồi xoá ngay; ngoại trừ 3 engine gửi ảnh ra ngoài (OpenAI/Gemini/DeepSeek API), không gửi đi đâu ngoài hai máy chủ cục bộ này. Xem [mục 11](#11-demo-ai2-phân-loại-cấu-trúc-fact-citation-xung-đột-confidence-docsarchitecturemd) để biết chi tiết field/giới hạn của lớp AI2 (chung code với endpoint này, ở `src/contract_ocr/application/use_cases/extract_ai2_facts.py`) và cách chạy bản CLI/hoàn toàn-trong-trình-duyệt không cần backend.

### Công cụ phụ: xem OCR thô từng dòng (debug engine)

`frontend/index.html` ở trên đã chạy cả lớp phân loại/cấu trúc/fact/citation. Nếu chỉ cần xem OCR thô (text/dòng theo từng trang, không phân loại hay trích fact) để debug một engine cụ thể, dùng trang phụ `frontend/ocr_raw.html`, chạy trên **cùng hai server đã chạy ở Bước 2-3** (không cần chạy thêm gì):

```text
http://127.0.0.1:5500/ocr_raw.html
```

(hoặc thêm `?api=http://host:port` nếu backend chạy ở địa chỉ khác, giống `index.html`). Kéo thả PDF hoặc ảnh, chọn engine như mô tả ở Bước 4 — kết quả hiện theo từng trang kèm trạng thái, có nút copy và tải `.txt`/`.json`.

### OpenAI/Gemini/DeepSeek (tuỳ chọn): OCR qua vision API

Ba engine ngoài PaddleOCR/DeepSeek-local — tuỳ chọn, không bật mặc định, và **phá vỡ nguyên tắc "xử lý cục bộ"** ở đầu file vì ảnh trang PDF được gửi ra ngoài. Chỉ bật nếu bạn chắc chắn tài liệu test không nhạy cảm.

```powershell
uv sync --locked --python 3.12 --extra dev --extra web --extra paddle --extra openai --extra gemini
copy .env.example .env
notepad .env
```

DeepSeek API dùng chung SDK `openai` (API tương thích OpenAI), không cần cài thêm gì ngoài `--extra openai` ở trên.

Trong `.env` vừa mở, điền key vào dòng tương ứng — `OPENAI_API_KEY=sk-...`, `GEMINI_API_KEY=...` và/hoặc `DEEPSEEK_API_KEY=...` (lấy tại [platform.deepseek.com](https://platform.deepseek.com), key Gemini tại [aistudio.google.com](https://aistudio.google.com/apikey)) rồi lưu lại. Bật engine nào thì điền key engine đó, không cần đủ cả ba. `.env` đã có sẵn ở gốc dự án (đã tạo sẵn, để trống key) và **không commit vào git** (đã có trong `.gitignore`). `scripts\serve_backend.py` tự nạp `.env` mỗi lần chạy — không cần set biến môi trường thủ công, không cần set lại mỗi khi mở cửa sổ PowerShell mới:

```powershell
.\.venv\Scripts\python.exe scripts\serve_backend.py
```

Không có key hoặc chưa cài extra tương ứng, engine đó tự động bị mờ trong UI kèm lý do, các engine khác vẫn dùng bình thường. Model mặc định: OpenAI `gpt-5.6-terra` (bản giữa dòng GPT-5.6 có vision, ~2$/1M input – 12$/1M output; rẻ hơn có `gpt-5.6-luna` ~0.20$/1M input – 1.20$/1M output, đổi qua tham số `model` nếu muốn), Gemini `gemini-3-flash-preview` (đổi qua `GEMINI_MODEL` nếu Google đổi tên — kiểm tra tại [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models) nếu gặp lỗi model không tồn tại), DeepSeek `deepseek-flash`. Theo tài liệu DeepSeek, ảnh gửi lên có thể bị tự động giảm kích thước trước khi model đọc (giới hạn ~1024 token/ảnh) — có thể ảnh hưởng độ chính xác với chữ nhỏ/dày đặc trên scan độ phân giải cao hơn OpenAI/Gemini; nên tự so sánh chất lượng trên tài liệu thật của bạn. UI có hộp thoại xác nhận trước khi gửi mỗi lần chọn 1 trong 3 engine này, để tránh bấm nhầm.

Các model dòng `gpt-5.6+` bỏ tham số `max_tokens`/`temperature` cũ (yêu cầu `max_completion_tokens`, không cho chỉnh `temperature` khác giá trị mặc định 1) — adapter `openai_vision_ocr.py` đã xử lý; đổi sang model OpenAI khác qua tham số `model` trong `_get_engine()` nếu gặp lỗi tương tự với model khác.

**Các trang chạy song song** với 3 engine này (tối đa 4 trang cùng lúc, `WEB_MAX_WORKERS` trong `app.py`) vì đây đều là API mạng không trạng thái, an toàn để gọi đồng thời. Đo thực tế: PDF 6 trang OCR bằng OpenAI mất **~53s song song** thay vì **~230s** nếu cộng dồn thời gian từng trang — nhanh hơn ~4.4 lần. PyMuPDF/PaddleOCR/DeepSeek-local vẫn xử lý tuần tự từng trang một như cũ: PDF chỉ có 1 file PyMuPDF đang mở nên đọc đồng thời nhiều trang không an toàn, và Paddle/DeepSeek-local chỉ có 1 model đã nạp dùng chung nên chạy song song dễ lỗi hoặc không nhanh hơn (nghẽn ở CPU/GPU, không phải ở mạng).

**Chống bịa nội dung:** `src/contract_ocr/infrastructure/ocr/prompts.py` chứa system prompt dùng chung cho cả 3 engine, yêu cầu model không được đoán/bịa chữ không đọc được — thay vào đó đánh dấu `[illegible]` tại đúng vị trí, không tự "sửa" chính tả, ưu tiên độ chính xác tuyệt đối cho số tiền/ngày tháng/mã số thuế/số điều khoản. Test thật trên ảnh scan mờ: Gemini và GPT-5.6 Terra đều tuân theo đúng, đánh dấu `[illegible]` rõ ràng ở các đoạn bị cắt/mờ thay vì đoán tiếp. Đổi prompt qua tham số `prompt` khi khởi tạo engine trong `_get_engine()` nếu cần tinh chỉnh.

**Lưu ý dòng model `gpt-5.6+`:** các model này bỏ tham số `max_tokens`/`temperature` kiểu cũ — API yêu cầu `max_completion_tokens` và không cho chỉnh `temperature` khác giá trị mặc định (1). Adapter `openai_vision_ocr.py` đã xử lý (chỉ gửi `temperature` nếu được cấu hình rõ ràng); nếu đổi sang model OpenAI khác mà gặp lỗi `unsupported_parameter`/`unsupported_value` tương tự, đây là nguyên nhân.

**DeepSeek Flash mặc định bật "thinking mode"** (chế độ tự suy luận trước khi trả lời, effort mặc định "high" theo tài liệu DeepSeek) — với `max_tokens` thông thường (4096), model có thể tiêu hết token vào phần suy luận nội bộ (`reasoning_content`) rồi không còn token nào để viết câu trả lời thật, trả về `content` rỗng, `finish_reason: "length"` — biểu hiện ra ngoài là trang báo lỗi `Empty extraction result` dù request không hề lỗi. Adapter đã tắt thinking mode mặc định (`extra_body={"thinking": {"type": "disabled"}}` trong `deepseek_vision_ocr.py`) vì OCR thuần không cần suy luận nhiều bước; test thật PDF 6 trang: từ 4/6 trang lỗi rỗng khi bật thinking → **6/6 SUCCESS** sau khi tắt, đồng thời nhanh hơn (~32s so với ~43s cho 6 trang). Muốn bật lại để thử nghiệm thì truyền `thinking=True` khi khởi tạo `DeepSeekVisionOCREngine`.

Chi tiết kỹ thuật và cách khắc phục sự cố ở [mục 8b](#8b-test-ui-chi-tiết-kỹ-thuật-và-khắc-phục-sự-cố).

## 1. Cài đặt môi trường

Chạy mọi lệnh dưới đây từ thư mục `ai-service/` (thư mục chứa file README này). Cần Python 3.11–3.12 và [`uv`](https://docs.astral.sh/uv/) đã cài sẵn.

```powershell
uv sync --locked --python 3.12 --extra dev
uv run python scripts/benchmark.py --help
uv run pytest -q
```

`uv run` tự dùng đúng venv trong `.venv/` mà không cần activate — cách nhanh và ít lỗi nhất, dùng được cả trên Windows/Linux/macOS. Bản cài nền gồm PyMuPDF, OpenCV, Pydantic, thư viện đánh giá, pytest và Ruff; PaddleOCR/OpenAI/Gemini/DeepSeek là extra tùy chọn (xem các mục dưới).

Muốn activate venv để gõ thẳng `python` thay vì `uv run python`: `.\.venv\Scripts\Activate.ps1` (PowerShell) hoặc `source .venv/bin/activate` (Linux/macOS). Nếu PowerShell chặn activation script, dùng thẳng `.\.venv\Scripts\python.exe scripts/benchmark.py --help` mà không cần đổi execution policy.

Trong VS Code: **Python: Select Interpreter** → chọn `ai-service/.venv/Scripts/python.exe` (Windows) hoặc `ai-service/.venv/bin/python` (Linux/macOS).

## 2. Chuẩn bị 30 mẫu

Phân bổ gợi ý: **8 PDF có text, 8 scan sạch, 8 scan suy giảm, 6 ca khó**. Bao phủ tiếng Việt, Anh, song ngữ, bảng, phụ lục, dấu, chữ ký, chữ nhỏ và ảnh kém chất lượng.

1. Đặt tài liệu vào `data/raw/digital`, `scanned_clean`, `scanned_bad`, `hard_cases` theo đúng loại.
2. Sao chép `data/manifest.example.csv` thành `data/manifest.csv`.
3. Thay các dòng ví dụ bằng đường dẫn thật. `sample_id` phải duy nhất; chỉ dùng chữ ASCII, số, `_`, `-`.
4. Đường dẫn tương đối được tính từ thư mục chạy lệnh (thường là `ai-service/`); dùng `--root <đường dẫn khác>` nếu chạy lệnh từ nơi khác. Đường dẫn tuyệt đối cũng được hỗ trợ.
5. Ghi nhãn ngôn ngữ nhất quán: `vi`, `en`, `vi-en`. Các cột boolean dùng `true`/`false`.

Không commit hợp đồng thật, annotation thật hay báo cáo chứa nội dung tài liệu. Các thư mục dữ liệu và `dataset/` đã được ignore. Manifest sai định dạng bị từ chối trước khi chạy; file PDF hỏng/mất được ghi FAILED và các mẫu khác tiếp tục.

## 3. Chạy baseline CPU

Chạy thử ngay bằng dữ liệu tổng hợp (không phải hợp đồng thật):

```powershell
uv run python scripts/create_synthetic_demo.py
uv run python scripts/benchmark.py --manifest data/generated/synthetic_demo/manifest.csv --engines pymupdf,paddle,deepseek --experiments E0,E1,E2 --output reports/synthetic_smoke
```

Lệnh tạo demo chỉ chạy một lần cho thư mục này. Nếu demo đã tồn tại, dùng manifest có sẵn và chọn tên output mới. Thiếu model OCR không cản trở kiểm tra luồng native và báo cáo.

### E0 — PyMuPDF, dùng được ngay với bản cài nền

```powershell
uv run python scripts/inspect_pdf.py --file "data/raw/digital/a.pdf"
uv run python scripts/benchmark.py --manifest data/manifest.csv --engines pymupdf --output reports/native_001
```

Trang có text đủ dùng được trích xuất kèm word/line bbox. Trang scan không có text được ghi `SKIPPED`, không tạo kết quả giả.

### E1 — PaddleOCR PP-OCRv6

Cài thêm Paddle CPU trong cùng venv:

```powershell
uv sync --locked --python 3.12 --extra dev --extra paddle
uv run python scripts/benchmark.py --manifest data/manifest.csv --engines pymupdf,paddle --experiments E0,E1 --output reports/baseline_001
```

Lần chạy Paddle đầu có thể tải trọng số từ kho model của Paddle. Tài liệu được xử lý cục bộ, không gửi đến dịch vụ OCR bên thứ ba. Nếu máy không tải được model hoặc Paddle không tương thích, báo cáo ghi `SKIPPED` cùng lý do. Model không tự động bị đổi về phiên bản cũ.

Để thử cả các biến thể preprocessing:

```powershell
uv run python scripts/benchmark.py --manifest data/manifest.csv --engines pymupdf,paddle --output reports/cpu_variants_001
```

Mặc định render **300 DPI**. E1 không tự xoay, unwarp, deskew hay enhance. E3 deskew; E4 deskew + denoise; E5 contrast; E6 adaptive threshold. Mỗi biến thể được áp dụng riêng trên cùng trang nguồn. Trang có text dùng PyMuPDF trong mọi pipeline để tránh OCR không cần thiết.

## 4. DeepSeek trên GPU

Dùng Linux/WSL2 với NVIDIA CUDA; nên dùng môi trường riêng vì phiên bản Transformers/PyTorch khác với các engine khác:

```bash
UV_PROJECT_ENVIRONMENT=.venv-deepseek uv sync --locked --python 3.12 --extra deepseek
source .venv-deepseek/bin/activate
uv pip install flash-attn==2.7.3 --no-build-isolation
python -c "import torch; print(torch.cuda.is_available())"
python scripts/benchmark.py --config configs/deepseek.yaml --manifest data/manifest.csv --engines pymupdf,deepseek --experiments E0,E2 --output reports/deepseek_001
```

Flash Attention cần CUDA toolkit/build tools tương thích. Kiểm tra CUDA wheel theo máy; lockfile không bảo đảm driver hoặc GPU phù hợp. Mặc định chỉ đọc model cache (`allow_download: false`). Đặt model ở đường dẫn local trong config, hoặc chủ động đổi `allow_download: true` để tải model. Model dùng `trust_remote_code=True` theo upstream; có thể ghim commit bằng `deepseek.revision`.

Default model: `deepseek-ai/DeepSeek-OCR-2`; có thể đổi thành `deepseek-ai/DeepSeek-OCR`. Prompt có newline thật và cấu hình được. Transformers giữ `result.mmd`, stdout riêng và raw markdown; không suy diễn bbox từ văn bản.

vLLM là backend local tùy chọn trên Linux:

```bash
UV_PROJECT_ENVIRONMENT=.venv-vllm uv sync --locked --python 3.12 --extra vllm
source .venv-vllm/bin/activate
OCR_DEEPSEEK_BACKEND=vllm python scripts/benchmark.py --manifest data/manifest.csv --engines deepseek --output reports/vllm_001
```

Các backend GPU cần kiểm chứng trên phần cứng thật. Thiếu CUDA/dependency/model được ghi `SKIPPED`; lỗi inference trên từng trang được ghi `FAILED` và tiếp tục.

## 5. Ground truth và cách đọc metrics

- `ground_truth_text`: file UTF-8, giữ nguyên dấu tiếng Việt. Mỗi trang dùng newline giữa các dòng; dùng ký tự form-feed `\f` (U+000C) giữa các trang. Không thêm newline cuối file nếu không muốn tính nó là sai khác. Ô manifest rỗng nghĩa là **chưa gán nhãn**; file rỗng nghĩa là **ground truth thực sự rỗng**.
- `ground_truth_critical_fields`: file JSON chứa danh sách `{type, value, raw_text, page?}`; `page` bắt đầu từ 1. Ví dụ: `{"type":"MONEY","value":"100000000","raw_text":"100.000.000 đồng","page":1}`.
- `ground_truth_bbox`: JSON chứa `{page, level, bbox}`. `level` là `word` hoặc `line`; bbox `{x1,y1,x2,y2}` nằm trong `[0,1]` trên trang đã áp dụng PDF rotation, gốc trên trái.

Chi tiết công thức, mẫu annotation và giới hạn ở [docs/DATASET.md](docs/DATASET.md) và [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md). Khi thiếu nhãn, metric để trống; không được hiểu là 0 lỗi.

## 6. Kết quả và bbox overlay

Mỗi lần chạy dùng **thư mục output mới** để tránh ghi đè:

```text
reports/baseline_001/
├── config.json
├── environment.json
├── input_hashes.json
├── manifest_snapshot.json
├── predictions/<sample_id>/<experiment>/output.json
├── predictions/<sample_id>/<experiment>/p001/...
├── metrics_by_sample.csv
├── metrics_summary.csv
├── failures.csv
├── failure_analysis.md
└── summary.md
```

```powershell
python scripts/visualize_bbox.py --prediction reports/baseline_001/predictions/S001/E1/output.json --page 1 --output reports/baseline_001/bbox.png
```

BBox được vẽ lên trang PDF nguồn: đỏ cho dòng, xanh cho từ. Paddle chỉ trả geometry dòng đáng tin cậy trong adapter này; không tách bbox từ giả. DeepSeek không có bbox nếu chưa có parser geometry được xác thực.

Ví dụ cấu trúc **MOCK, không phải benchmark thực**:

```json
{"document_id":"MOCK","source_file":"mock.pdf","pages":[]}
```

`metrics_summary.csv` nhóm theo engine, experiment, language, input_type, quality, degradation. Mỗi metric có cột `_n` riêng. Chỉ mẫu SUCCESS hoàn chỉnh có annotation mới được gộp accuracy; FAILED/SKIPPED vẫn nằm trong số lần thử và tỷ lệ thành công. `actual_engines`, `native_pages`, `ocr_pages` giúp tránh gán kết quả native cho Paddle/DeepSeek. Chi phí API ngoài = 0; chi phí GPU/CPU chưa ước tính, không đồng nghĩa miễn phí.

## 7. Sinh mẫu suy giảm

```powershell
uv run python scripts/generate_degraded_samples.py --file data/raw/digital/a.pdf --seed 42 --language vi
```

Sinh 19 biến thể mỗi trang vào `data/generated/<source-hash>-seed42/`, kèm manifest và tham số/ma trận biến đổi. Không sửa file gốc. Kết quả là PDF ảnh để benchmark dùng cùng luồng như scan thật. Annotation không tự được sao chép: phải tách text đúng trang và biến đổi bbox theo ma trận đã lưu. JPEG artifact được giữ trong ảnh raster rồi đóng gói thành PDF.

## 8. Kiểm thử và cấu hình

```powershell
uv run pytest -q
uv run ruff check src scripts tests
uv run ruff format --check src scripts tests
```

Có GNU Make (Linux/macOS, hoặc WSL/Git Bash trên Windows nếu cài `make`): `make install`, `make test`, `make lint`, `make inspect FILE=example.pdf`, `make generate-degraded FILE=example.pdf`, `make benchmark MANIFEST=data/manifest.csv OUTPUT=reports/run_001` — các target này chỉ gọi lại đúng các lệnh `uv run` ở trên. PowerShell/CMD trên Windows thường không có `make` sẵn, dùng thẳng các lệnh `uv run` phía trên.

Config chính là `configs/default.yaml`; `paddle.yaml` và `deepseek.yaml` là các profile đầy đủ. Dùng `--config`. Environment override hỗ trợ `OCR_DPI`, `OCR_DEEPSEEK_MODEL`, `OCR_DEEPSEEK_BACKEND`; `.env.example` chỉ là mẫu, không tự được nạp. `experiments/definitions.yaml` là danh sách thí nghiệm tham khảo; runner đọc danh sách trong config được chọn.

## 8b. Test UI: chi tiết kỹ thuật và khắc phục sự cố

Xem [mục Chạy nhanh](#chạy-nhanh-demo-ui-tải-pdf-lên-xem-idp) ở đầu file để chạy ngay. Phần này là chi tiết cho ai cần hiểu sâu hơn hoặc gặp lỗi.

Đây là công cụ kiểm thử thủ công cho một file duy nhất, gồm hai phần tách biệt hoàn toàn, không phải một sản phẩm hay pipeline riêng, và không nằm trong phạm vi Sprint 1 mô tả ở đầu file:

- **Backend** — `src/contract_ocr/web/app.py`, chạy bằng `scripts/serve_backend.py`. API-only (FastAPI), không phục vụ HTML. Chạy trên cùng `ProcessDocument`/engine/preprocessing với `benchmark`. Bật CORS mở (`allow_origins=["*"]`) vì đây là công cụ test cục bộ không có auth; không dùng cấu hình này cho dịch vụ public.
- **Frontend** — `frontend/index.html`, chạy bằng `scripts/serve_frontend.py`. Một file HTML/CSS/JS tĩnh, không phụ thuộc Python hay build step; đọc địa chỉ backend từ thẻ `<meta name="api-base">` (mặc định `http://127.0.0.1:8000`), có thể ghi đè bằng query string `?api=...`. Có thể phục vụ bằng bất kỳ static server nào khác (Nginx, `python -m http.server`, VS Code Live Server...), không nhất thiết phải dùng `scripts/serve_frontend.py`.

Các lỗi thường gặp:

- **`ModuleNotFoundError: fastapi`/`click`/`colorlog`...** — venv chưa sync đủ (thường do đã `uv sync` không kèm extra ở lần khác trước đó, làm rớt bớt gói); chạy lại đúng lệnh cài đặt ở mục Chạy nhanh (`uv sync --locked --python 3.12 --extra dev --extra web --extra paddle`) để cài lại đầy đủ.
- **Backend chạy được, log không báo lỗi, nhưng mọi request treo/không có response, kèm log nền `AttributeError: module 'httptools' has no attribute 'HttpRequestParser'`** — bản `httptools` (HTTP parser mặc định của uvicorn) bị cài lỗi trên máy đó. `scripts/serve_backend.py` đã tự chuyển sang dùng `http="h11"` (thuần Python, không phụ thuộc wheel này) để né lỗi; nếu tự chạy `uvicorn` trực tiếp thay vì qua script, thêm `--http h11`.
- **`ModuleNotFoundError: fastapi`** — chưa cài `--extra web`; chạy lại lệnh cài đặt ở mục Chạy nhanh.
- **Port 8000 hoặc 5500 đã dùng** — một server cũ vẫn đang chạy nền. Tìm và dừng nó trước khi chạy lại (đổi `8000` thành `5500` nếu là frontend): `Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force`.
- **Frontend báo "Không kết nối được backend"** — backend chưa chạy, chạy sai port, hoặc `<meta name="api-base">`/`?api=` trỏ sai địa chỉ. Mở thẳng `http://127.0.0.1:8000/api/engines` trên trình duyệt để kiểm tra backend còn sống không.
- **PaddleOCR báo `NotImplementedError: ConvertPirAttribute2RuntimeAttribute...`** — PaddlePaddle 3.3.x bật mkldnn mặc định trên CPU và một số CPU Windows không tương thích với đường PIR/oneDNN này. `scripts/serve_backend.py` đã tự set biến môi trường `PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False` để né lỗi; đổi lại suy luận chậm hơn nhiều so với có mkldnn hoặc có GPU. Nếu vẫn chạy trực tiếp bằng `uvicorn` thay vì `scripts/serve_backend.py`, phải tự set biến này trước khi import `contract_ocr.web.app`.
- **Trang scan/file ảnh luôn báo `SKIPPED`** — đang chọn engine PyMuPDF cho PDF/ảnh không có text layer (ảnh không bao giờ có text layer). Đổi sang PaddleOCR, OpenAI hoặc Gemini.
- **DeepSeek-OCR bị mờ, không chọn được** — cần GPU NVIDIA CUDA cục bộ; xem [mục 4](#4-deepseek-trên-gpu). Adapter không hỗ trợ chạy CPU hay gọi API từ xa.
- **PaddleOCR quá chậm** — hạ DPI (mục "Tuỳ chọn nâng cao" trong UI) xuống 150; DPI càng cao, ảnh càng lớn, suy luận CPU càng lâu.
- **OpenAI/Gemini/DeepSeek API bị mờ, không chọn được** — chưa cài extra tương ứng (`--extra openai` cho cả OpenAI lẫn DeepSeek API / `--extra gemini`), chưa điền key trong `.env`, hoặc backend đang chạy từ **trước khi** bạn sửa `.env` (biến môi trường chỉ được nạp lúc khởi động, sửa `.env` xong phải `Ctrl+C` rồi chạy lại `scripts\serve_backend.py`). Xem [mục OpenAI/Gemini/DeepSeek](#openaigeminideepseek-tuỳ-chọn-ocr-qua-vision-api).
- **Gemini báo lỗi model không tồn tại / 404** — Google đổi tên dòng model "flash" khá thường xuyên; đặt `GEMINI_MODEL=<tên model hiện tại>` trong `.env` theo [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models).
- **OpenAI báo `AuthenticationError: Incorrect API key...`** — key sai/hết hạn/thiếu quyền, không phải lỗi ở code; kiểm tra lại key tại platform.openai.com.
- **PDF text-layer chọn engine OpenAI/PaddleOCR mà vẫn thấy `engine: "pymupdf"` trong kết quả** — đúng như thiết kế: trang có sẵn text-layer usable luôn ưu tiên đọc native trước, không gọi OCR (tránh tốn phí/thời gian không cần thiết). Engine bạn chọn chỉ áp dụng cho trang không có text-layer.

## 9. Kiến trúc và giới hạn

```text
src/contract_ocr/
├── domain/          # entities, bbox, enums; Pydantic, không import OCR SDK
├── application/     # ports và use cases
├── infrastructure/  # PDF, OCR adapters, image, metrics, config, reporting
├── schemas/         # canonical JSON contract
└── cli/             # wiring dependency và commands
```

Xem [kiến trúc](docs/ARCHITECTURE.md), [thí nghiệm](docs/EXPERIMENTS.md), [dataset](docs/DATASET.md), [schema](docs/OUTPUT_SCHEMA.md).

- Text layer đủ dài nhưng sai/mất nội dung vẫn có thể được đánh giá là usable; MIXED ưu tiên native khi đủ ngưỡng. Cần kiểm tra bằng annotation, đặc biệt trang chỉ có một phần text layer.
- Native reading order/bảng và markdown của DeepSeek có thể khác ground truth. CER giữ whitespace, WER tách theo whitespace; chưa có đánh giá cấu trúc bảng.
- Critical-field metric là kiểm tra giữ đúng nội dung gán nhãn trong OCR, không phải semantic field extraction. Cùng số xuất hiện ở vị trí khác có thể gây false positive; ưu tiên annotation theo trang.
- Deskew dùng đường thẳng gần ngang, có thể bị bảng/khung ảnh gây nhiễu. Orientation correction là cấu hình góc 90/180/270, chưa tự suy đoán hướng chữ.
- Độ tái lập GPU không bảo đảm bit-for-bit. Lưu config, versions, model revision, input hashes và seed để điều tra sai khác. Native page processing và khởi tạo model nằm trong thời gian end-to-end; initialization được lưu riêng.
- Báo cáo lưu nội dung tài liệu để phân tích lỗi; log trang mặc định chỉ lưu metadata. Chưa có kết quả so sánh trên 30 hợp đồng được gán nhãn.

Sprint 2: chốt bộ annotation có kiểm tra chéo, chạy đủ các engine trên cùng manifest, kiểm tra lỗi số tiền/ngày/mã số thuế, cải thiện chính sách MIXED và reading order, rồi quyết định engine bằng dữ liệu đo thực. RAG và suy luận điều khoản cần phạm vi riêng sau khi chất lượng OCR đã được xác nhận.

### Nguồn API upstream

- [PaddleOCR quick start](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/quick_start.en.md)
- [DeepSeek-OCR-2 model card](https://huggingface.co/deepseek-ai/DeepSeek-OCR-2)
- [DeepSeek-OCR](https://huggingface.co/deepseek-ai/DeepSeek-OCR)

Các nguồn này hướng dẫn adapter và cài đặt; không phải bằng chứng về độ chính xác trên dataset của dự án.

## 10. Bàn giao OCR snapshot cho AI2 (`ai1.snapshot.v1`)

Contract riêng, tách khỏi schema benchmark ở mục 9 (`Document`/`Page` dùng để so sánh engine): xem [docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md](docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md) (phản hồi đầy đủ, mapping từng mục với yêu cầu bàn giao gốc), [docs/ai1.snapshot.v1.schema.json](docs/ai1.snapshot.v1.schema.json) và [docs/ai1.dossier_manifest.v1.schema.json](docs/ai1.dossier_manifest.v1.schema.json) (JSON Schema, sinh từ Pydantic models ở `domain/snapshot.py` — nguồn xác thực chính là các model đó, tương tự cách `output.schema.json` liên hệ với `domain/entities.py`).

Sinh một document snapshot từ PDF thật:

```powershell
uv run contract-ocr snapshot --file hop-dong.pdf --document-id contract-001 --dossier-id dossier-001 --role contract --engine paddle --output data/generated/snapshots
```

Sinh nhanh một dossier mẫu đầy đủ (hợp đồng TEXT_LAYER + phụ lục SCANNED_OCR + manifest, dữ liệu tổng hợp, không phải hợp đồng thật):

```powershell
uv run python scripts/export_snapshot_demo.py
```

## 11. Demo AI2: phân loại, cấu trúc, fact, citation, xung đột, confidence (`docs/architecture.md`)

Lớp AI2 mô tả ở `docs/architecture.md` §5-9 và §27 sống ở một chỗ duy nhất — `src/contract_ocr/application/use_cases/extract_ai2_facts.py` — và có **ba cách chạy** tuỳ nhu cầu:

| Cách chạy | Dùng khi nào | OCR engine | Đủ tính năng mới nhất? |
| --- | --- | --- | --- |
| `frontend/index.html` + backend (mục "Chạy nhanh" ở trên) | Muốn dùng UI, cần đọc cả PDF scan | Mọi engine đã cấu hình ở backend (PyMuPDF/PaddleOCR/Vision API) | Có — cây Điều/Khoản/Điểm, confidence, N phụ lục, Evaluation, "Sửa" |
| `scripts/demo_ai2_pipeline.py --contract ...` | Muốn chạy dòng lệnh / không cần UI | `--engine none` (native) hoặc `--engine paddle` | Có — cùng module dùng chung, `--annex` lặp lại được nhiều lần |
| Kéo-thả PDF thẳng vào `demo_report.html` đã sinh ra | Muốn xem nhanh, không cần chạy backend | Chỉ đọc được PDF native (pdf.js, chạy trong trình duyệt) | Có — cùng logic JS mirror, cây Điều/Khoản/Điểm, confidence, N phụ lục, Evaluation, "Sửa"; PDF scan vẫn không đọc được vì không có OCR trong trình duyệt |

Luồng chính ở cả ba cách là **tải một PDF hợp đồng**, tự động ra output IDP theo đúng slice tối thiểu ở §27.11 — 0..N phụ lục là bổ sung, không bắt buộc, không có nút bật/tắt "so sánh" riêng. Output khớp các mục trong bảng "Output người dùng yêu cầu" ở §27.2:

- **Input processing**: 1 contract + 0..N appendix, PDF native hoặc scan (tuỳ engine).
- **Classification**: `contract`/`appendix`/`other` theo từ khoá trang đầu.
- **Clause extraction**: cây `Dieu` → `Khoan` → `Diem` (mỗi clause có `parent_clause_id`), không chỉ Điều phẳng.
- **Structured extraction**: field MVP `parties` (bên A/B), `amount`, `date`, `payment term`.
- **Citation**: mỗi fact/finding có document hash + trang/dòng/bbox/quote.
- **Conflict detection**: so hợp đồng với từng phụ lục độc lập, kết quả gắn `annex_filename` để không gộp lẫn khi có nhiều phụ lục.
- **Confidence**: object `{signals, review_priority}` theo tín hiệu (anchor precision, có mismatch hay không) — không phải xác suất bịa, đúng cảnh báo ở §27.8.
- **Human review**: hành động "Sửa" trên `index.html` — chỉ sửa trong phiên trình duyệt, không lưu.
- **Evaluation report**: tab đếm N theo review_priority, nói rõ chưa có ground truth nên chưa có accuracy/F1 thật.

Những gì **chưa có** (ghi rõ để không hiểu nhầm là đã đủ): trích bảng (`tables[]` trong ai1.snapshot.v1 luôn rỗng — gap có sẵn ở tầng OCR, không phải AI2 tạo ra), evaluation report thật cần ground truth gán nhãn, human review có lưu trữ/persist.

Chạy `uv run python scripts/demo_ai2_pipeline.py` (không tham số) để lấy demo dữ liệu tổng hợp, hoặc `--contract path/to/file.pdf` để thử PDF thật, thêm `--annex path/to/file2.pdf` (lặp lại nhiều lần để có nhiều phụ lục, đều tuỳ chọn — xem docstring đầu file để biết chi tiết/giới hạn). Kết quả là một `demo_report.html` tĩnh, tự chứa, mở thẳng bằng trình duyệt.
