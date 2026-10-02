from __future__ import annotations

from evals.tests import test_no_eval_leakage as lint

ALLOWLIST = frozenset(
    {
        # Existing diagnostic compatibility paths; this list may only shrink.
        ("reasoning/gold.py", 9, "cl_9"),
        ("reasoning/gold.py", 10, "cl_1_1"),
        ("reasoning/gold.py", 11, "cl_8"),
        ("reasoning/gold.py", 12, "cl_5_body"),
        ("reasoning/gold.py", 13, "a_5_pl1"),
        ("reasoning/gold.py", 14, "a_5_pl2"),
        ("reasoning/gold.py", 15, "pl13_def"),
        ("reasoning/gold.py", 16, "unnum_pay"),
        ("reasoning/gold.py", 158, "tom tat toan bo hop ong va rui ro chinh"),
        ("reasoning/gold.py", 200, "co bao nhieu phap nhan trong hop ong"),
        ("reasoning/l0_rules.py", 292, "inj"),
        ("reasoning/l0_rules.py", 411, "cl_9"),
        ("reasoning/l0_rules.py", 428, "field_usd"),
        ("reasoning/l0_rules.py", 438, "field_penalty_build"),
        ("reasoning/l0_rules.py", 439, "field_penalty_equip"),
        ("reasoning/l0_rules.py", 519, "tbl_300"),
    }
)


def test_no_eval_leakage() -> None:
    hits = lint.scan_tree()
    assert set(hits) <= ALLOWLIST


def test_new_fixture_identifier_is_rejected(tmp_path) -> None:
    source_root = tmp_path / "ai-service" / "app"
    source_root.mkdir(parents=True)
    sample = source_root / "fixture.py"
    sample.write_text('NODE = "cl_9"\n', encoding="utf-8")
    assert any("cl_9" in issue for issue in lint.scan_tree(tmp_path))


def _normalize(value: str) -> str:
    import re
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value).casefold()
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def scan_tree(root=None):
    """Find production Python literals copied from golden/HD fixture material."""
    import ast
    import json
    from pathlib import Path

    from evals.golden.catalog import CONTRACTS

    repository = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    app_root = repository / "ai-service" / "app"
    if not app_root.exists():
        return []
    fixture_path = repository / "ai-service" / "fixtures" / "reasoning" / "hd_tong_hop_tasks.json"
    if not fixture_path.is_file():
        fixture_path = Path(__file__).resolve().parents[2] / "ai-service" / "fixtures" / "reasoning" / "hd_tong_hop_tasks.json"
    hd_tasks = json.loads(fixture_path.read_text(encoding="utf-8"))
    questions = {
        _normalize(question.text)
        for contract in CONTRACTS
        for question in contract.questions
        if len(_normalize(question.text)) >= 12
    }
    questions.update(
        _normalize(task["query"])
        for task in hd_tasks
        if isinstance(task, dict) and isinstance(task.get("query"), str) and len(_normalize(task["query"])) >= 12
    )
    node_ids = {
        str(node_id)
        for task in hd_tasks
        if isinstance(task, dict)
        for node_id in task.get("must_cite", [])
        if isinstance(node_id, str) and node_id
    }
    findings: set[tuple[str, int, str]] = set()
    for source in sorted(app_root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (OSError, SyntaxError, UnicodeError) as exc:
            findings.add((source.relative_to(app_root).as_posix(), 0, f"parse-error:{type(exc).__name__}"))
            continue
        relative = source.relative_to(app_root).as_posix()
        for item in ast.walk(tree):
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                continue
            normalized = _normalize(item.value)
            for question in questions:
                if question and question in normalized:
                    findings.add((relative, item.lineno, question))
            for node_id in node_ids:
                if item.value == node_id:
                    findings.add((relative, item.lineno, node_id))
    return sorted(findings)
