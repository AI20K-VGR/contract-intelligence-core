"""Capability-driven required-set: từ `capabilities` của module README → suy ra doc bắt buộc.

Lai (quyết định 9): README + design LUÔN bắt buộc; còn lại theo "tờ khai" capabilities.
  exposes_api  → api.md
  has_workers  → workers.md
  tenant_config→ config.md
  has_features → features/<f>/spec.md mỗi f
  owns_agents  → agents/<a>/{agent.md,model-card.md,eval.md} + prompt/SYSTEM.md mỗi a

Thiếu doc đã-khai = finding `required-doc-missing` (WARN, không chặn build).
Doc tồn tại nhưng capability không khai = `undeclared-doc` (WARN).
"""
from __future__ import annotations

from pathlib import Path

ALWAYS = ("README.md", "design.md")

# capability flag (bool) -> file bắt buộc (tương đối module dir)
FLAG_DOC = {
    "exposes_api": "api.md",
    "has_workers": "workers.md",
    "tenant_config": "config.md",
}
# capability list -> hàm sinh path bắt buộc cho mỗi phần tử
AGENT_DOCS = ("agent.md", "model-card.md", "eval.md", "prompt/SYSTEM.md")


def required_docs(capabilities: dict) -> list[str]:
    """Danh sách path (tương đối module dir) bắt buộc theo tờ khai."""
    caps = capabilities or {}
    req = list(ALWAYS)
    for flag, doc in FLAG_DOC.items():
        if caps.get(flag):
            req.append(doc)
    # Guard: chỉ iterate khi giá trị là list (tránh crash khi nhận str/None/int)
    feats = caps.get("has_features", [])
    for feat in (feats if isinstance(feats, list) else []):
        req.append(f"features/{feat}/spec.md")
    agents = caps.get("owns_agents", [])
    for agent in (agents if isinstance(agents, list) else []):
        for d in AGENT_DOCS:
            req.append(f"agents/{agent}/{d}")
    return req


def check_module(mod_dir: Path, rel_dir: str, capabilities: dict, findings) -> list[str]:
    """So tờ khai vs file thực tế. Trả về danh sách required path còn thiếu."""
    missing = []
    for r in required_docs(capabilities):
        if not (mod_dir / r).is_file():
            missing.append(r)
            sev = findings.error if r in ALWAYS else findings.warn
            code = "mandatory-doc-missing" if r in ALWAYS else "required-doc-missing"
            sev(code, f"{rel_dir}/{r}", f"doc bắt buộc theo capability còn thiếu: `{r}`")
    # undeclared: file capability-driven tồn tại nhưng cờ không khai
    caps = capabilities or {}
    for flag, doc in FLAG_DOC.items():
        if (mod_dir / doc).is_file() and not caps.get(flag):
            findings.warn("undeclared-doc", f"{rel_dir}/{doc}",
                          f"có `{doc}` nhưng capability `{flag}` chưa khai trong README frontmatter")
    return missing
