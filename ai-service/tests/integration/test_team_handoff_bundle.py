"""The shareable demo bundle must match the published AI1 snapshot contract."""

from contract_ocr.domain.snapshot import DocumentSnapshot, DossierManifest
from scripts import export_snapshot_demo


def test_demo_bundle_contains_snapshots_images_and_native_table(tmp_path):
    output = tmp_path / "handoff"
    export_snapshot_demo.main(output)
    root = output / "dossier-001"
    manifest = DossierManifest.model_validate_json(
        (root / "dossier_manifest.json").read_text(encoding="utf-8")
    )
    assert {item.document_id for item in manifest.documents} == {"contract-001", "annex-001"}

    snapshots = {}
    for item in manifest.documents:
        path = next((root / item.document_id).glob("*.json"))
        snapshot = DocumentSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        assert snapshot.document_id == item.document_id
        assert snapshot.dossier_id == manifest.dossier_id
        for page in snapshot.pages:
            assert page.page_image_ref is not None
            image_name = f"page-{page.page_number:03d}.png"
            assert page.page_image_ref.uri.endswith(f"/{snapshot.snapshot_id}/{image_name}")
            assert (path.parent / snapshot.snapshot_id / image_name).is_file()
        snapshots[item.document_id] = snapshot

    assert snapshots["contract-001"].pages[0].table_status == "DETECTED"
    assert len(snapshots["contract-001"].pages[0].tables) == 1
    assert snapshots["annex-001"].pages[0].input_type == "SCANNED_OCR"
