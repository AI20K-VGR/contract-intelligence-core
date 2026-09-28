"""Frontmatter YAML: parse + validate shape. KHÔNG đánh giá nội dung.

Khế ước frontmatter (global default — module override khi khác):
  id        : dot-path, segment kebab, globally-unique   (BẮT BUỘC)
  type      : ∈ DOC_TYPES                                  (BẮT BUỘC)
  status    : draft|review|stable|superseded              (BẮT BUỘC)
  owner     : PTNT|PTSP|<team>                             (BẮT BUỘC)
  version   : semver x.y.z                                 (BẮT BUỘC)
  tier      : ∈ TIERS                                      (optional, validate enum nếu có)
  parent    : id doc cấp trên                              (optional, resolve ở graph)
  provenance: [path,...] nguồn raw                         (optional, resolve ở graph)
  capabilities: {...}  CHỈ module-readme                   (xem capabilities.py)
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml_io

DOC_TYPES = {
    "sad", "overview", "quality", "governance", "module-readme", "module-design",
    "part", "api", "worker", "config", "techstack", "operations", "guide", "feature-spec",
    "agent-spec", "model-card", "eval", "prompt", "mcp-tool", "adr", "glossary",
    "changelog", "index",
}
STATUSES = {"draft", "review", "stable", "superseded"}
TIERS = {"L0", "L1", "L1x", "L2", "L3", "platform", "module"}
PART_LAYERS = {"L2", "L3", "L4"}  # graph layer của part (DA5) — SSOT, graph.py tái dùng
REQUIRED = ("id", "type", "status", "owner", "version")

ID_RE = re.compile(r"^[a-z0-9]+(?:[-.][a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")
# Fence đóng phải nằm ngay sau một dòng mới: `---` giữa dòng KHÔNG phải fence.
# Thiếu neo đó thì `title: 'a --- b'` bị cắt ngay trong dấu nháy và cả tệp hỏng,
# còn một `---` thụt lề trong khối nhiều dòng thì cắt mất phần còn lại của giá
# trị và đẩy nó sang body mà raw_error vẫn None — mất dữ liệu không ai thấy.
# `...` là dấu kết thúc tài liệu hợp lệ của YAML. Khối được giữ nguyên dòng mới
# cuối để YAML đọc đúng dòng cuối của một block scalar.
_FM_RE = re.compile(r"^---\s*\n(.*?\n)(?:---|\.\.\.)\s*\n?(.*)$", re.DOTALL)
# Khối RỖNG (`---\n---`) có fence đóng nhưng không có nội dung, nên biểu thức
# đòi-nội-dung ở trên không khớp. Ở đây rỗng là HỢP LỆ (`has_frontmatter()` trả
# True cho nó, và retrofit_frontmatter dựa vào điều đó để không ghi đè), nên nó
# cần nhánh riêng thay vì rơi vào "no-frontmatter-block".
_FM_EMPTY_RE = re.compile(r"^---\s*\n(?:---|\.\.\.)\s*\n?(.*)$", re.DOTALL)


class Doc:
    """Một file md đã parse: meta (frontmatter) + body + đường dẫn."""

    __slots__ = ("path", "rel", "meta", "body", "raw_error")

    def __init__(self, path: Path, rel: str, meta: dict | None, body: str, raw_error: str | None):
        self.path = path
        self.rel = rel
        self.meta = meta or {}
        self.body = body
        self.raw_error = raw_error

    @property
    def id(self):
        return self.meta.get("id")

    @property
    def type(self):
        return self.meta.get("type")

    def has_frontmatter(self) -> bool:
        # Trả True khi block --- tồn tại (kể cả FM rỗng --- \n ---)
        return self.raw_error is None


def parse(path: str | Path, rel: str | None = None) -> Doc:
    """Đọc + tách frontmatter. raw_error != None nếu YAML hỏng hoặc thiếu block."""
    path = Path(path)
    rel = rel if rel is not None else path.name
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        empty = _FM_EMPTY_RE.match(text)
        if empty:
            return Doc(path, rel, {}, empty.group(1), None)
        return Doc(path, rel, None, text, "no-frontmatter-block")
    try:
        meta = yaml_io.safe_load(m.group(1)) or {}
    except yaml_io.YAMLError as e:
        return Doc(path, rel, None, m.group(2), f"yaml-error: {e}")
    if not isinstance(meta, dict):
        return Doc(path, rel, None, m.group(2), "frontmatter-not-mapping")
    return Doc(path, rel, meta, m.group(2), None)


def validate(doc: Doc, findings) -> None:
    """Structural checks cho frontmatter một file → push vào findings."""
    if doc.raw_error == "no-frontmatter-block":
        findings.error("missing-frontmatter", doc.rel, "thiếu block frontmatter `---`")
        return
    if doc.raw_error:
        findings.error("bad-frontmatter", doc.rel, doc.raw_error)
        return
    meta = doc.meta
    for k in REQUIRED:
        if not meta.get(k):
            findings.error("missing-frontmatter-field", doc.rel, f"thiếu field bắt buộc `{k}`")
    _id = meta.get("id")
    if _id and not ID_RE.match(str(_id)):
        findings.error("bad-id-grammar", doc.rel, f"id `{_id}` sai grammar dot/kebab")
    t = meta.get("type")
    if t and t not in DOC_TYPES:
        findings.error("bad-type", doc.rel, f"type lạ `{t}`")
    st = meta.get("status")
    if st and st not in STATUSES:
        findings.error("bad-status", doc.rel, f"status lạ `{st}` (∈ {sorted(STATUSES)})")
    v = meta.get("version")
    if v and not SEMVER_RE.match(str(v)):
        findings.error("bad-version", doc.rel, f"version `{v}` không semver")
    tier = meta.get("tier")
    if tier and tier not in TIERS:
        findings.error("bad-tier", doc.rel, f"tier lạ `{tier}` (∈ {sorted(TIERS)})")
    own = meta.get("owner")
    if own and not isinstance(own, str):
        findings.error("bad-owner", doc.rel, "owner phải là chuỗi")
    # part docs sở hữu graph fact (DA5 frontmatter-as-SSOT): layer/reuses shape-check
    if t == "part":
        layer = meta.get("layer")
        if layer is not None and layer not in PART_LAYERS:
            findings.error("bad-part-layer", doc.rel, f"layer `{layer}` ∉ {sorted(PART_LAYERS)}")
        reuses = meta.get("reuses")
        if reuses is not None:
            if not isinstance(reuses, list):
                findings.error("bad-reuses", doc.rel, "reuses phải là list các {part, why}")
            else:
                for r in reuses:
                    if not isinstance(r, dict) or not r.get("part"):
                        findings.error("bad-reuses", doc.rel, f"reuses entry phải có khoá `part`: {r!r}")


def dump(meta: dict, body: str = "") -> str:
    """Serialize frontmatter + body → text (giữ thứ tự key đã cho, unicode nguyên bản)."""
    front = yaml_io.safe_dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{front}---\n{body or ''}"


def merge_frontmatter(path: str | Path, fields: dict) -> None:
    """Đọc part doc, gộp `fields` vào frontmatter (multi-touch writer), ghi lại — giữ body.

    Dùng cho one-time migration đẩy graph fact (layer/note/reuses) vào part doc.
    """
    path = Path(path)
    doc = parse(path)
    if doc.raw_error:
        # KHÔNG ghi đè khi frontmatter cũ hỏng (list/scalar/yaml-error) — parse trả meta={}
        # nên merge sẽ wipe nội dung gốc. Từ chối để caller xử (skip/sửa tay).
        raise ValueError(f"từ chối merge: frontmatter malformed ({doc.raw_error}) ở {path}")
    meta = dict(doc.meta)
    meta.update(fields)
    path.write_text(dump(meta, doc.body), encoding="utf-8")
