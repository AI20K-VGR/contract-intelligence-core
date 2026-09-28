---
name: hs:docs-scaffold
injectable: false
description: Sinh skeleton doc từ template (frontmatter + heading + > TBD) theo required-set capability-driven. No-clobber. Không sáng tạo nội dung.
argument-hint: "[--module mod-07 --auto] | [--type <t> --out <path> --set k=v]"
allowed-tools: [Bash, Read, Glob]
metadata:
  compliance-tier: workflow
---

# hs:docs-scaffold — sinh skeleton doc

Stub doc còn thiếu từ `templates/<type>.md` → `{{token}}` thay bằng giá trị/`TBD`.
**No-clobber**: file đã có nội dung (`size > 0`) không bị ghi đè (trừ `--force`).

**Ranh giới CỨNG** (lặp ở cả 3 skill docs-*): **không sáng tạo nội dung thiết kế**, **không debate chất lượng**. Chỉ sinh khung (frontmatter hợp lệ + heading + `> TBD`). Người viết điền nội dung; gap nội dung-cần-quyết → `FIX.md`, không tự fill.

## When to use

- Module mới / module thêm capability (`exposes_api`, `owns_agents`, …) → cần stub doc mới.
- Trước `hs:docs-standardize`: dập tắt `mandatory-doc-missing` / `required-doc-missing` bằng skeleton, rồi để người viết nội dung.
- KHÔNG dùng để viết lại doc đã có nội dung (no-clobber bảo vệ; đừng `--force` bừa).

## Required-set (capability-driven, lai)

Nguồn: `README.md` frontmatter `capabilities` của module (xem `_docslib/.../capabilities.py`).

| Điều kiện | Doc bắt buộc (relative module dir) |
|---|---|
| LUÔN | `README.md`, `design.md` |
| `exposes_api: true` | `api.md` |
| `has_workers: true` | `workers.md` |
| `tenant_config: true` | `config.md` |
| `has_features: [f, …]` | `features/<f>/spec.md` mỗi `f` |
| `owns_agents: [a, …]` | `agents/<a>/{agent,model-card,eval}.md` + `agents/<a>/prompt/SYSTEM.md` mỗi `a` |

README+design thiếu = `mandatory-doc-missing` (error). Còn lại thiếu = `required-doc-missing` (warn).

## Step-by-step

1. **Soi gap** — `capability_required.py` đọc README → liệt kê required còn thiếu mỗi module.
2. **Sinh** — `scaffold_doc.py --module <id> --auto` stub mọi required còn thiếu (no-clobber).
3. **Xác minh** — chạy lại `capability_required.py`; mong đợi `✓ đủ required-set`.
4. **Bàn giao** — báo người viết: file `WROTE` là skeleton `> TBD`, cần điền nội dung. Không tự điền; chuyển `hs:docs-standardize` để validate cấu trúc sau khi viết.

## Scripts (I/O thật)

**`scripts/capability_required.py`** — analyzer gap, exit 0. Đọc `load_model(docs)` → với mỗi module so `required_docs(capabilities)` vs file thực tế → in/JSON `{dir, capabilities, required, missing}`. KHÔNG sinh file.
```
python3 scripts/capability_required.py [--docs docs] [--module mod-07] [--json]
```

**`scripts/scaffold_doc.py`** — sinh skeleton. Token `{{id}} {{type}} {{status}} {{owner}} {{version}} {{parent}} {{title}} {{date}}` → giá trị/`TBD`. Default: `status=draft`, `version=0.1.0`, `owner=PTNT` (config → `PTSP`), `date=hôm nay`. Kết quả mỗi file: `WROTE` | `KEEP` (no-clobber) | `SKIP` (thiếu template / không map type).

- Đơn lẻ: `--type <t> --out <path> --set k=v [--set …] [--force]`
- Module: `--module mod-07 --auto` — sinh MỌI required còn thiếu; tự suy `id` (dot-path dưới module: README→`mid`, `features/<f>/…`→`mid.feature.<f>.<…>`, `agents/<a>/…`→`mid.agent.<a>.<…>`, `prompt/SYSTEM`→`…prompt`), `parent=mid`, `owner` theo type.

```
python3 scripts/scaffold_doc.py --module mod-07 --auto
python3 scripts/scaffold_doc.py --type adr --out docs/decisions/adr/adr-0007-x.md --set id=adr-0007 --set title="Chọn X"
```

**`templates/<type>.md`** — 22 template (1/loại type; loại `index` không có template). Mỗi template = frontmatter token hoá + heading + `> TBD`. Sửa template ⇒ đổi khung sinh ra (không thuộc skill này).

## Ví dụ lệnh

```
# 1) gap toàn repo
python3 scripts/capability_required.py
# 2) chỉ một module, JSON
python3 scripts/capability_required.py --module mod-09 --json
# 3) stub mọi required còn thiếu của mod-09 (no-clobber)
python3 scripts/scaffold_doc.py --module mod-09 --auto
# 4) ép ghi đè một file (hiếm khi cần — phá no-clobber)
python3 scripts/scaffold_doc.py --type api --out docs/modules/.../mod-09/api.md --set id=mod-09.api --force
```

## Ranh giới (không làm)

- KHÔNG viết nội dung thiết kế/API/prompt — chỉ `> TBD`.
- KHÔNG ghi đè file có nội dung (no-clobber); `--force` chỉ khi người dùng yêu cầu rõ.
- KHÔNG sửa `capabilities` (quyết định của chủ module) — chỉ đọc.
- KHÔNG validate graph (việc của `hs:docs-standardize`).
