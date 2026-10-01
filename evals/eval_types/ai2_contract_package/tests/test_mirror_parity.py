"""Production replay gate for the contract-package domain."""

from pathlib import Path

from evals.release_verification import replay_production


def test_production_replay_uses_tracked_handoff_and_preserves_lineage():
    fixture = Path(__file__).resolve().parents[4] / "ai-service" / "fixtures" / "eval_inputs" / "snapshots" / "ai1.full.v1.json"
    result = replay_production(fixture)
    assert result["status"] == "PASS", result
    assert result["parity_executed"] is True
    assert result["snapshot_id"] == "eval-full-v1"
    assert result["production_entry"] == "app.ai2.v1.process_payloads_full"
