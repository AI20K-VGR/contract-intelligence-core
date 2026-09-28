from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from pypdf import PdfReader

from app.api.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_demo_case_catalog_exposes_existing_and_synthetic_cases():
    response = TestClient(app).get("/api/cases")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 95
    assert any(item["case_id"] == "SYN-001" for item in items)
    assert any(item["case_id"] == "HD-TONG-HOP" for item in items)
    assert all("scenario" in item and "input_kind" in item for item in items)


def test_table_case_has_a_renderable_pdf_with_table_content():
    client = TestClient(app)
    session = client.post("/api/workspace/case/HAPPY-002").json()

    assert session["has_pdf"] is True
    assert session["n_tables"] == 1
    assert len(session["files"]) == 1
    file_id = session["files"][0]["file_id"]
    pdf = client.get(f"/api/workspace/{session['session_id']}/files/{file_id}")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    page_text = PdfReader(BytesIO(pdf.content)).pages[0].extract_text() or ""
    assert "Q1" in page_text and "100" in page_text and "Thanh toán" in page_text


def test_demo_case_query_exposes_answer_citation_and_trace_contract():
    response = TestClient(app).post(
        "/api/cases/SYN-009/query",
        json={"query": "Điều 5 liên quan thế nào đến phụ lục 1?", "use_llm": False, "use_vector": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "SYN-009"
    assert "review_state" in body
    assert "citations" in body
    assert "relation_edges" in body
    assert body["retrieval_trace"]["vector_status"] == "NOT_REQUESTED"


def test_demo_graph_and_table_routes_are_lazy_and_bounded():
    client = TestClient(app)
    graph = client.get("/api/cases/SYN-022/relation-graph")
    assert graph.status_code == 200
    assert "edges" in graph.json()

    detail = client.get("/api/cases/EC-010")
    assert detail.status_code == 200
    table_id = detail.json()["tables"][0]["table_id"]
    table = client.get(f"/api/cases/EC-010/tables/{table_id}?offset=0&limit=50")
    assert table.status_code == 200
    assert len(table.json()["rows"]) <= 50


def test_demo_exposes_separate_processing_and_embedding_policy_gates():
    client = TestClient(app)
    embedding_gate = client.get("/api/cases/EC-050").json()["policy"]
    assert embedding_gate["deterministic"] == "ALLOW"
    assert embedding_gate["external"] == "BLOCKED"
    assert any(item["code"] == "EMBEDDING_BUDGET_EXCEEDED" for item in embedding_gate["gates"])

    egress_gate = client.get("/api/cases/EC-055").json()["policy"]
    assert egress_gate["deterministic"] == "ALLOW"
    assert egress_gate["external"] == "BLOCKED"
    assert any(item["code"] == "EGRESS_DENIED" for item in egress_gate["gates"])

    blocked = client.post(
        "/api/cases/EC-055/query",
        json={"query": "Điều 1 nói gì?", "use_llm": True, "use_vector": False},
    )
    assert blocked.status_code == 200
    assert blocked.json()["review_state"] == "BLOCKED"
    assert blocked.json()["used_llm"] is False


def test_demo_static_contract_contains_case_loader_and_observability_panels():
    index = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    demo = (ROOT / "app" / "static" / "demo.js").read_text(encoding="utf-8")
    lab = (ROOT / "app" / "static" / "lab.html").read_text(encoding="utf-8")
    lab_js = (ROOT / "app" / "static" / "lab.js").read_text(encoding="utf-8")
    assert 'id="sample-case"' in index
    assert 'data-tab="graph"' in index
    assert "use_vector" in demo
    assert "95 kịch bản" in lab
    assert "relation_edges" in lab_js
    assert "retrieval_trace" in lab_js
