"""Derived-output SSOT — tập glob của artifact SINH (build output), không phải nguồn.

Một nguồn sự thật cho "cái gì là output dẫn xuất" để:
  - gitignore convention (showcase migration) bỏ commit chúng;
  - docs-standardize gate báo lỗi khi chúng bị commit vào cây nguồn;
  - build ghi chúng ra out-dir, KHÔNG ghi ngược vào `docs/`.

Nguyên tắc: commit nguồn (md + `_index/*.yaml` + `_present/*` + `_diagram/puml` + hand-authored
`showcase/assets/*` + `showcase/partials/*.html` prose), gitignore output.

CỐ Ý LOẠI `showcase/partials/*.html`: hiện TRỘN hand-authored prose + md-sourced render
(build_showcase Bước A2 chỉ regen page có `source`). Blanket-ignore = mất content tay → quyết
định người dùng (đợi prose chuyển hết sang md, showcase redesign). Xem BACKLOG.
"""
from __future__ import annotations

from pathlib import PurePosixPath

# Glob (rel docs-root) của output dẫn xuất AN TOÀN để gitignore + chặn-commit.
DERIVED_OUTPUT_GLOBS = (
    "public/**",                       # toàn site HTML build (assembler → docs/public, sync → root public)
    "showcase/assets/js/*-data.js",    # 4 data-JS sinh bởi generate_showcase_data (module-m4/ptnt-*/part-modref)
    "_diagram/png/**",                 # png sinh từ puml (giữ puml/ nguồn)
)


def is_derived_output(rel_path: str) -> bool:
    """True nếu `rel_path` (POSIX, rel docs-root) là output dẫn xuất → phải gitignore, cấm commit.

    `**` = đệ quy (khớp tiền tố thư mục); `*` (PurePath.match) KHÔNG băng qua `/` — tránh false-pos
    cho JS hand-authored lồng thư mục con (vd `assets/js/vendor/chart-data.js` KHÔNG phải derived).
    """
    rel = str(rel_path).lstrip("/").lower()   # case-fold: `.JS`/`SHOWCASE/` cũng là output dẫn xuất
    p = PurePosixPath(rel)
    for pat in DERIVED_OUTPUT_GLOBS:
        pat = pat.lower()
        if pat.endswith("/**"):
            base = pat[:-3]
            if rel == base or rel.startswith(base + "/"):
                return True
        elif p.match(pat):
            return True
    return False
