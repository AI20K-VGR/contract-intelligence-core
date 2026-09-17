from app.domain import require


def citation(page, line, run_id):
    box = line["bbox"]
    require(0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1, "CITATION_ANCHOR_INVALID")
    return {
        "id": f"{run_id}:{line['id']}",
        "run_id": run_id,
        "document_id": page["document_id"],
        "source_hash": page["sha256"],
        "page_number": page["page_number"],
        "line_id": line["id"],
        "quote": line["text"],
        "bbox": box,
        "coordinate_system": "normalized_top_left_rendered_page",
        "geometry_source": page["engine"],
        "precision": "line",
    }


def validate_result(result):
    citations = {c["id"]: c for c in result["citations"]}
    lines = {line["id"]: (page, line) for page in result["pages"] for line in page["lines"]}
    for cit in citations.values():
        require(cit["line_id"] in lines, "CITATION_ANCHOR_INVALID")
        page, line = lines[cit["line_id"]]
        require(
            cit["quote"] == line["text"]
            and cit["bbox"] == line["bbox"]
            and cit["source_hash"] == page["sha256"],
            "CITATION_ANCHOR_INVALID",
        )
    for fact in result["facts"]:
        require(
            bool(fact["citation_ids"]) and all(c in citations for c in fact["citation_ids"]),
            "FACT_WITHOUT_EVIDENCE",
        )
    for finding in result["findings"]:
        for side in ("citations_a", "citations_b"):
            require(
                bool(finding[side]) and all(c in citations for c in finding[side]),
                "FINDING_WITHOUT_EVIDENCE",
            )
