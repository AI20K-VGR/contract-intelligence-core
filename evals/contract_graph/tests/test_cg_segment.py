from __future__ import annotations

from conftest import fixture_text

from evals.contract_graph.normalize import html_to_text
from evals.contract_graph.segment import collapse_to_articles, segment


def _by_label(nodes: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for node in nodes:
        out.setdefault(node["raw_label"], []).append(node)
    return out


def test_article_clause_point_tree_has_parent_links():
    nodes = segment(html_to_text(fixture_text("mini_vbhn.html")), "vbhn:mini")
    ids = {n["node_id"]: n for n in nodes}

    dieu4 = next(n for n in nodes if n["raw_label"] == "Điều 4")
    khoans = [n for n in nodes if n["parent_id"] == dieu4["node_id"]]
    assert [k["raw_label"] for k in khoans] == ["1.", "2."]
    points_k2 = [n for n in nodes if n["parent_id"] == khoans[1]["node_id"]]
    assert [p["raw_label"] for p in points_k2] == ["a)", "d)", "đ)"]
    assert dieu4["parent_id"] is None
    assert dieu4["text"] == "Loại hợp đồng"
    for node in nodes:
        assert node["type"] == "CLAUSE"
        assert node["source_file_id"] == "vbhn:mini"
        assert node["page_range"] == [1]
        assert node["parent_id"] is None or node["parent_id"] in ids
    assert [n["order"] for n in nodes] == list(range(len(nodes)))


def test_note_markers_are_removed_from_node_text():
    nodes = segment(html_to_text(fixture_text("mini_vbhn.html")), "vbhn:mini")

    for node in nodes:
        assert "[" not in node["text"]
    k2 = next(n for n in nodes if n["text"] == "Nội dung mới của khoản 2 Điều 3.")
    assert k2["raw_label"] == "2."
    # the footnote block is not part of the structural tree
    assert not any("theo quy định tại" in n["text"] for n in nodes)


def test_annex_heading_becomes_root_node():
    nodes = segment(html_to_text(fixture_text("mini_suffix_vbhn.html")), "vbhn:suffix")

    annex = next(n for n in nodes if n["raw_label"].lower().startswith("phụ lục"))
    assert annex["raw_label"] == "Phụ lục 1"
    assert annex["parent_id"] is None
    child = next(n for n in nodes if n["parent_id"] == annex["node_id"])
    assert (child["raw_label"], child["text"]) == ("1.", "Mẫu hợp đồng.")


def test_unnumbered_annex_heading_closes_the_last_article():
    text = "Điều 9. Hiệu lực\n1. Thông tư có hiệu lực.\nPHỤ LỤC\nCác biểu mẫu kèm theo\n1.[29] Mẫu TMĐT-1.\nPhụ lục này gồm 2 mẫu."

    nodes = segment(text, "d")

    annex = next(n for n in nodes if n["raw_label"] == "Phụ lục")
    assert annex["parent_id"] is None
    assert annex["text"] == "Các biểu mẫu kèm theo"
    item = nodes[-1]
    assert (item["raw_label"], item["parent_id"], item["text"]) == (
        "1.",
        annex["node_id"],
        "Mẫu TMĐT-1.\nPhụ lục này gồm 2 mẫu.",
    )


def test_suffix_labels_become_own_nodes():
    nodes = segment(html_to_text(fixture_text("mini_suffix_vbhn.html")), "vbhn:suffix")
    labels = _by_label(nodes)

    d, d1, d2 = labels["d)"][0], labels["d1)"][0], labels["d2)"][0]
    k2 = labels["2."][0]
    assert d["parent_id"] == d1["parent_id"] == d2["parent_id"] == k2["node_id"]
    assert "chi phí cộng phí" not in d["text"]
    assert d1["text"] == "Hợp đồng theo chi phí cộng phí;"
    k5, k5a = labels["5."][0], labels["5a."][0]
    assert k5["parent_id"] == k5a["parent_id"] == labels["Điều 18"][0]["node_id"]
    assert labels["Điều 30a"][0]["parent_id"] is None
    assert (
        labels["Điều 30a"][0]["text"]
        == "Hợp đồng EPC\nCác bên thỏa thuận phạm vi công việc của hợp đồng EPC."
    )
    assert labels["Điều 30"][0]["text"] == "Hợp đồng tổng thầu\nNội dung Điều 30."


def test_collapse_to_articles_keeps_child_labels_at_line_start():
    nodes = segment(html_to_text(fixture_text("mini_suffix_vbhn.html")), "vbhn:suffix")
    original_ids = {n["raw_label"]: n["node_id"] for n in nodes if n["parent_id"] is None}

    collapsed = collapse_to_articles(nodes)

    assert [n["raw_label"] for n in collapsed] == [
        "Điều 3",
        "Điều 18",
        "Điều 30",
        "Điều 30a",
        "Phụ lục 1",
    ]
    for node in collapsed:
        assert node["node_id"] == original_ids[node["raw_label"]]
        assert node["parent_id"] is None
    dieu3 = collapsed[0]["text"].split("\n")
    assert dieu3 == [
        "Các loại hợp đồng xây dựng",
        "1. Theo tính chất công việc.",
        "2. Theo hình thức giá hợp đồng:",
        "a) Hợp đồng trọn gói;",
        "d) Hợp đồng theo thời gian;",
        "d1) Hợp đồng theo chi phí cộng phí;",
        "d2) Hợp đồng xây dựng khác.",
        "đ) Hợp đồng theo giá kết hợp.",
    ]
    assert collapsed[-1]["text"] == "1. Mẫu hợp đồng."
