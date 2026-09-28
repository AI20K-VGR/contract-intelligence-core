"""Finding model + JSON artifact + gate. Nguồn sự thật của mọi check là artifact JSON.

Quy ước severity:
  error  → gate exit 2 (chặn CI)
  warn   → gap / cần chú ý, KHÔNG chặn
  info   → ghi nhận

KHÔNG bao giờ phán xét chất lượng thiết kế — chỉ structural/objective.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

ERROR, WARN, INFO = "error", "warn", "info"


@dataclass
class Finding:
    code: str                       # machine code, kebab: missing-frontmatter-field
    severity: str                   # error|warn|info
    where: str                      # path tương đối hoặc id
    msg: str                        # mô tả người đọc (KHÔNG phán chất lượng)
    data: dict = field(default_factory=dict)


class Findings:
    """Bộ thu findings + xuất artifact JSON ổn định (deterministic, sort theo where/code)."""

    def __init__(self):
        self._items: list[Finding] = []

    def add(self, code, severity, where, msg, **data):
        self._items.append(Finding(code, severity, str(where), msg, data))

    def error(self, code, where, msg, **data):
        self.add(code, ERROR, where, msg, **data)

    def warn(self, code, where, msg, **data):
        self.add(code, WARN, where, msg, **data)

    def info(self, code, where, msg, **data):
        self.add(code, INFO, where, msg, **data)

    def extend(self, other: "Findings"):
        self._items.extend(other._items)

    @property
    def items(self) -> list[Finding]:
        return sorted(self._items, key=lambda f: (f.where, f.code, f.msg))

    def by_severity(self, sev) -> list[Finding]:
        return [f for f in self._items if f.severity == sev]

    @property
    def counts(self) -> dict:
        c = {ERROR: 0, WARN: 0, INFO: 0}
        for f in self._items:
            c[f.severity] = c.get(f.severity, 0) + 1
        c["total"] = len(self._items)
        return c

    def has_errors(self) -> bool:
        return any(f.severity == ERROR for f in self._items)

    def artifact(self, *, generated_from: str, schema: str = "docs-validation-artifact/v1",
                 extra: dict | None = None) -> dict:
        a = {
            "schema": schema,
            "generated_from": generated_from,
            "counts": self.counts,
            "findings": [asdict(f) for f in self.items],
        }
        if extra:
            a.update(extra)
        return a

    def write_artifact(self, path: str | Path, **kw) -> dict:
        a = self.artifact(**kw)
        Path(path).write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return a

    def print_summary(self, title="DOCS CHECK"):
        c = self.counts
        verdict = "FAIL" if self.has_errors() else ("WARN" if c[WARN] else "OK")
        print(f"{title}: {verdict}  (error={c[ERROR]} warn={c[WARN]} info={c[INFO]})")
        for f in self.items:
            tag = {"error": "✗", "warn": "!", "info": "·"}[f.severity]
            print(f"  {tag} [{f.code}] {f.where}: {f.msg}")
