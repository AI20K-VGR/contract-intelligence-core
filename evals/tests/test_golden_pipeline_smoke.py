from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.golden.build_golden import SPEC_COMMIT, build_golden


def test_golden_pipeline_smoke(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ai_service_root = repo_root / "ai-service"
    if str(ai_service_root) not in sys.path:
        sys.path.insert(0, str(ai_service_root))

    from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input
    from app.pipeline.idp import run_idp
    from app.pipeline.index import IndexStore
    from app.reasoning.query import QueryRouter
    from app.tools.gateway import ToolGateway
    from app.tools.store import InMemorySnapshotStore

    data_dir = tmp_path / "golden"
    assert build_golden(data_dir) == 0
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["spec_commit"] == SPEC_COMMIT
    questions = json.loads((data_dir / "questions.json").read_text(encoding="utf-8"))

    for entry in manifest["files"]:
        snapshot = json.loads((data_dir / entry["path"]).read_text(encoding="utf-8"))
        adapted = adapt_ai1_input(snapshot, scope_id=f"{snapshot['dossier_id']}:{snapshot['document_id']}")
        record = adapted.record
        line_ids = {line_id for page in record.pages for line_id in page.line_texts}
        contract_questions = [q for q in questions if q["contract_id"] == entry["contract_id"]]
        gold_line_ids = {
            line_id
            for question in contract_questions
            for span in question["required_spans"]
            for line_id in span["line_ids"]
        }
        assert gold_line_ids <= line_ids

        store = InMemorySnapshotStore()
        job = run_idp(record, adapted.envelope, store=store, index=IndexStore())
        assert job.status.value == "SUCCEEDED"
        assert any(node.type == "CLAUSE" for node in record.nodes)
        query = QueryRouter(store, ToolGateway(store)).query(
            adapted.envelope, contract_questions[0]["text"]
        )
        assert isinstance(query, dict)
        assert "review_state" in query
