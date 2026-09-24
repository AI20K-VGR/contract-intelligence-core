"""Validate the AI1 package against the current source models and sample output."""

import json
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ai1"
sys.path.insert(0, str(ROOT / "ai-service" / "src"))

from contract_ocr.domain.snapshot import DocumentSnapshot, DossierManifest  # noqa: E402


def main() -> None:
    for name, model in (
        ("ai1.snapshot.v1.schema.json", DocumentSnapshot),
        ("ai1.dossier_manifest.v1.schema.json", DossierManifest),
    ):
        packaged = json.loads((PACKAGE / "contracts" / name).read_text(encoding="utf-8"))
        source = json.loads((ROOT / "ai-service" / "docs" / name).read_text(encoding="utf-8"))
        assert packaged == source
        generated = model.model_json_schema()
        assert {k: v for k, v in packaged.items() if k not in {"$schema", "title"}} == {
            k: v for k, v in generated.items() if k != "title"
        }

    example = PACKAGE / "examples" / "dossier-001"
    DossierManifest.model_validate_json((example / "dossier_manifest.json").read_text())
    for path in example.glob("*/*.json"):
        snapshot = DocumentSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        assert snapshot.execution and snapshot.run_id and snapshot.status
        for page in snapshot.pages:
            assert page.page_revision_id and page.raw_text_digest
            assert page.quality and page.table_coverage
            if page.page_image_ref:
                image_name = page.page_image_ref.uri.rsplit("/", 1)[-1]
                assert (path.parent / snapshot.snapshot_id / image_name).is_file()
            line_ids = {line.line_id for line in page.lines}
            for table in page.tables:
                assert table.logical_table_id and table.fragment_id
                for row in table.rows:
                    for cell in row.cells:
                        assert set(cell.line_ids) <= line_ids
        print(f"validated {path.relative_to(PACKAGE)}")

    with ZipFile(PACKAGE / "ai-service-source.zip") as archive:
        names = set(archive.namelist())
        assert "src/contract_ocr/domain/snapshot.py" in names
        assert "pyproject.toml" in names
        assert all("__pycache__" not in name and ".pyc" not in name for name in names)
        assert all(Path(name).name != ".env" for name in names)
    print("AI1 handoff package OK")


if __name__ == "__main__":
    main()
