"""Playbook orchestration — content ⟂ ui ⟂ output trong 1 config (tinh thần Antora playbook).

`docs/playbook.yaml` khai NGUỒN nội dung, BUNDLE trình bày, và OUT-DIR build — đổi theme hoặc
thêm content source = 1 dòng config, không sửa code. Build/gate đọc đây thay vì hardcode path.

Fail-closed: thiếu file / thiếu `content` / `content` không phải list → PlaybookError actionable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml_io

DEFAULT_OUTPUT = "build/"


class PlaybookError(ValueError):
    """Playbook thiếu/sai shape — fail-closed với message hành-động-được."""


@dataclass
class Playbook:
    content: list           # nguồn nội dung (dir/glob rel docs-root)
    output: str = DEFAULT_OUTPUT
    ui: dict = field(default_factory=dict)   # {bundle, theme, ...}


def load_playbook(docs_root: str | Path) -> Playbook:
    docs_root = Path(docs_root)
    path = docs_root / "playbook.yaml"
    if not path.is_file():
        raise PlaybookError(
            f"thiếu playbook: {path} — tạo `docs/playbook.yaml` khai content/ui/output")
    raw = yaml_io.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise PlaybookError(f"playbook.yaml phải là mapping, gặp {type(raw).__name__}")
    if raw.get("content") is None:
        raise PlaybookError("playbook.yaml thiếu `content:` — khai ≥1 nguồn nội dung (vd `- modules/`)")
    content = raw["content"]
    if not isinstance(content, list):
        raise PlaybookError("playbook.yaml `content:` phải là list nguồn (vd `- modules/`)")
    if not content:
        raise PlaybookError("playbook.yaml `content:` rỗng — khai ≥1 nguồn nội dung (vd `- modules/`)")
    ui = raw.get("ui") or {}
    if not isinstance(ui, dict):
        raise PlaybookError("playbook.yaml `ui:` phải là mapping {bundle, theme}")
    output = raw.get("output") or DEFAULT_OUTPUT
    return Playbook(content=content, output=str(output), ui=ui)
