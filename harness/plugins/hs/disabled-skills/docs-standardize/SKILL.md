---
name: hs:docs-standardize
injectable: false
description: Validate structural docs (frontmatter + graph invariant) → artifact JSON → gate. Tìm gap vs template. KHÔNG sửa nội dung, KHÔNG phán chất lượng.
argument-hint: "[--fresh] | [--docs docs] [--artifact <path>] [--quiet]"
allowed-tools: [Bash, Read, Glob]
metadata:
  compliance-tier: gate
---

# hs:docs-standardize — validate structural + tìm gap

Kiểm tra **cấu trúc** docs (không phải nội dung): frontmatter hợp lệ, id unique,
parent/provenance resolve, graph invariant (parts/links/config/safety/foundation),
required-set capability-driven. **Không sửa file.**

**Ranh giới CỨNG** (lặp ở cả 3 skill docs-*): skill **không sáng tạo nội dung thiết kế**,
**không debate chất lượng/nội dung**; chỉ chuẩn hoá cấu trúc + tìm gap vs template. Cái
cần-người-quyết → ghi `FIX.md`, **không tự fix**.

## Kiến trúc 3-lớp (giống sdlc-harness)

```
analyzer (check_docs.py, exit 0)  →  artifact JSON (nguồn sự thật)  →  gate (docs_gate.py, exit 2 nếu error)
```

- **Analyzer** chỉ đếm/đi-graph → `Findings` (error|warn|info) → ghi `harness/state/docs-check.json`.
  Exit 0 LUÔN (kể cả có error) — analyzer không quyết.
- **Artifact** (JSON, sinh bởi `_docslib/docslib/findings.py :: artifact()`) là **nguồn sự thật** duy nhất. Mọi
  phán xét (gate, báo cáo, LLM-advisory) phải neo theo số/finding trong artifact.
- **Gate** đọc artifact, exit 2 nếu có `severity=error`; warn/info không chặn.

## When to use

- Sau khi viết/sửa frontmatter hoặc thêm doc → kiểm cấu trúc.
- Sau `hs:docs-scaffold` → xác nhận skeleton hợp khế ước.
- Trước `hs:docs-build` / ship → gate CI (`--fresh` để chắc artifact mới).

## Step-by-step

1. **Analyze** — `check_docs.py` → in summary + ghi artifact. Đọc các finding `error` trước.
2. **Phân loại**:
   - `error` (structural, objective) → SỬA CẤU TRÚC được (id sai grammar, type lạ, dangling
     parent…). Sửa frontmatter/_index, KHÔNG sửa prose.
   - `warn` (gap) → required-doc-missing/undeclared-doc/dangling-provenance/missing-canonical-link.
     Gap doc thiếu → `hs:docs-scaffold`. Gap cần-người-quyết → `FIX.md`.
3. **Gate** — `docs_gate.py --fresh` → PASS khi 0 error.
4. **Advisory (tùy chọn)** — LLM-check prose chỉ khi được yêu cầu, MẶC ĐỊNH KHÔNG flag, luôn
   neo theo artifact, KHÔNG bao giờ phán "thiết kế dở". Xem `references/validation-split.md`.

## Scripts (I/O thật)

**`scripts/check_docs.py`** — analyzer, exit 0. `load_model(docs)` → `graph.validate(model, f)`
→ `f.write_artifact(...)`. Cờ: `--docs docs --artifact harness/state/docs-check.json --quiet`.
Artifact thêm `extra`: `{modules, docs, parts, links}` (đếm).

**`scripts/docs_gate.py`** — gate, exit 2 nếu có error. Đọc artifact; KHÔNG validate lại logic.
Cờ: `--artifact <path> --docs docs --fresh`. `--fresh` chạy `check_docs.py` trước (artifact mới).
Thiếu artifact + không `--fresh` → exit lỗi (nhắc chạy analyzer trước).

**`scripts/migrate_module_map.py`** — ONE-SHOT: `docs/modules/module-map.yaml` →
`docs/_index/{modules,foundations,safety,showcase}.yaml` + sidecar `_migration/module-attrs.json`
(intrinsic per-module data để bơm frontmatter). Idempotent (ghi đè `_index/*`); KHÔNG đụng map gốc.
Không phải bước thường nhật — chỉ chạy 1 lần khi tách map.

**`scripts/migrate_facts_to_frontmatter.py`** — ONE-SHOT, legacy: đẩy graph fact (layer/note/
universal_spine, reuse edge) từ `_index/modules.yaml` sang frontmatter (part doc / module README)
theo mô hình frontmatter-as-SSOT. Idempotent (`--check` để verify parity trước khi xoá fact tay).
Không phải bước thường nhật — đã chạy khi migrate sang frontmatter-as-SSOT.

**`scripts/retrofit_frontmatter.py`** — ONE-SHOT, legacy: tiêm frontmatter còn thiếu vào doc cũ
(top-docs hand-map + module README `_migration/module-attrs.json` + parts từ `_index/modules.yaml`).
Idempotent (đã có frontmatter → bỏ qua), KHÔNG tạo nội dung. Không phải bước thường nhật.

## Ví dụ lệnh

```
python3 scripts/check_docs.py                    # analyze + summary + artifact
python3 scripts/check_docs.py --quiet            # chỉ ghi artifact (CI)
python3 scripts/docs_gate.py --fresh             # re-analyze rồi gate (exit 2 nếu error)
python3 scripts/docs_gate.py                     # gate trên artifact có sẵn
python3 scripts/migrate_module_map.py            # one-shot P1
```

## Tham chiếu

- `references/frontmatter-spec.md` — khế ước frontmatter: field bắt buộc/optional, grammar id,
  enum (type/status/tier/version), block ví dụ.
- `references/graph-invariants.md` — mọi invariant graph.validate liệt kê + severity + cách fix.
- `references/validation-split.md` — ranh giới Script-check (exit 0/2, objective) vs
  LLM-check (advisory prose, mặc định KHÔNG flag).

## Ranh giới (không làm)

- KHÔNG sửa nội dung prose; chỉ sửa cấu trúc (frontmatter/_index) khi cần dập error.
- KHÔNG phán chất lượng thiết kế (kể cả LLM-advisory) — chỉ structural/objective.
- KHÔNG sinh doc (việc của `hs:docs-scaffold`); KHÔNG build (việc của `hs:docs-build`).
- Quyết định nội dung-cần-người → `FIX.md`, không tự fix.

## Cơ chế ngoại lệ: `.docsignore`

Khi docs chứa file thuộc dự án ngoài (vd `docs/product/` từ `product-spec`), tạo
`docs/.docsignore` với pattern đơn giản (mỗi dòng một pattern):

- `thư-mục/` → exclude cả cây
- `file.md` → exclude một file
- `# comment` → bỏ qua

`check_docs.py` và `docs_gate.py` tự động đọc và áp dụng `.docsignore` khi quét docs.
Không cần flag riêng.
