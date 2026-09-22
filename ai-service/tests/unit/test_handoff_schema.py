"""Keep the files handed to other teams in sync with AI1's authoritative models."""

import json
from pathlib import Path

from contract_ocr.domain.snapshot import DocumentSnapshot, DossierManifest

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_handoff_json_schemas_match_models():
    for filename, model in (
        ("ai1.snapshot.v1.schema.json", DocumentSnapshot),
        ("ai1.dossier_manifest.v1.schema.json", DossierManifest),
    ):
        published = json.loads((DOCS / filename).read_text(encoding="utf-8"))
        generated = model.model_json_schema()
        assert published["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert {key: value for key, value in published.items() if key not in {"$schema", "title"}} == {
            key: value for key, value in generated.items() if key != "title"
        }
