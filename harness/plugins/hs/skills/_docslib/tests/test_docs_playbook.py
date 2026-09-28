"""C4 — playbook orchestration: content ⟂ ui ⟂ output trong 1 config.

`docs/playbook.yaml` khai `content:[sources]`, `ui:{bundle,theme}`, `output:`. Đổi UI bundle =
re-theme không đụng content; thêm content source = include không sửa code; playbook thiếu
content = fail-closed message actionable.
"""
from pathlib import Path

import pytest
import yaml_io

from docslib.playbook import load_playbook, PlaybookError


def _write_playbook(docs: Path, payload) -> None:
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "playbook.yaml").write_text(yaml_io.safe_dump(payload, allow_unicode=True), encoding="utf-8")


def test_load_playbook_fields(tmp_path):
    _write_playbook(tmp_path, {
        "content": ["modules/", "architecture/", "guides/"],
        "ui": {"bundle": "_present", "theme": "showcase"},
        "output": "build/",
    })
    pb = load_playbook(tmp_path)
    assert pb.content == ["modules/", "architecture/", "guides/"]
    assert pb.ui == {"bundle": "_present", "theme": "showcase"}
    assert pb.output == "build/"


def test_theme_swap_does_not_touch_content(tmp_path):
    base = {"content": ["modules/"], "ui": {"bundle": "_present", "theme": "showcase"}, "output": "build/"}
    _write_playbook(tmp_path, base)
    pb1 = load_playbook(tmp_path)
    base["ui"]["theme"] = "dark"
    _write_playbook(tmp_path, base)
    pb2 = load_playbook(tmp_path)
    assert pb2.ui["theme"] == "dark"
    assert pb1.content == pb2.content            # content không đổi khi re-theme


def test_add_content_source_included(tmp_path):
    _write_playbook(tmp_path, {"content": ["modules/"], "output": "build/"})
    assert load_playbook(tmp_path).content == ["modules/"]
    _write_playbook(tmp_path, {"content": ["modules/", "decisions/"], "output": "build/"})
    assert load_playbook(tmp_path).content == ["modules/", "decisions/"]


def test_output_defaults_when_absent(tmp_path):
    _write_playbook(tmp_path, {"content": ["modules/"]})
    assert load_playbook(tmp_path).output == "build/"


def test_missing_content_fails_closed(tmp_path):
    _write_playbook(tmp_path, {"ui": {"theme": "x"}, "output": "build/"})
    with pytest.raises(PlaybookError) as e:
        load_playbook(tmp_path)
    assert "content" in str(e.value).lower()


def test_empty_content_message_says_empty(tmp_path):
    """content present-nhưng-rỗng → message phân biệt 'rỗng', không nói 'thiếu'."""
    _write_playbook(tmp_path, {"content": [], "output": "build/"})
    with pytest.raises(PlaybookError) as e:
        load_playbook(tmp_path)
    assert "rỗng" in str(e.value).lower()


def test_missing_playbook_file_fails_closed(tmp_path):
    with pytest.raises(PlaybookError) as e:
        load_playbook(tmp_path)
    assert "playbook" in str(e.value).lower()


def test_content_not_list_fails_closed(tmp_path):
    _write_playbook(tmp_path, {"content": "modules/", "output": "build/"})
    with pytest.raises(PlaybookError):
        load_playbook(tmp_path)
