from fixtures.catalog import make_node, make_page, make_record, make_pins

from app.reasoning.relations import build_relation_graph


def test_relation_graph_reports_missing_parent_instead_of_dropping_it():
    record = make_record(
        case_id="ST-044-MISSING-PARENT",
        dossier="st044-missing-parent",
        pages=[make_page(1, "Dieu 1 noi dung")],
        nodes=[
            make_node("child", "CLAUSE", "Dieu 1", "Dieu 1 noi dung", parent_id="missing-parent"),
        ],
        pins=make_pins(source_snapshot_digest="sha256:st044"),
    )

    graph = build_relation_graph(record)

    assert any(issue.missing == "missing parent missing-parent" for issue in graph.issues)
