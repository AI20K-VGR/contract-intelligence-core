import re


def clauses(pages, run_id):
    result = []
    for page in pages:
        for line in page["lines"]:
            if re.match(r"^(Điều|Article)\s+\d+", line["text"], re.IGNORECASE):
                result.append(
                    {
                        "id": f"clause:{line['id']}",
                        "type": "article",
                        "label": line["text"],
                        "parent_id": None,
                        "citation_ids": [f"{run_id}:{line['id']}"],
                    }
                )
    return result
