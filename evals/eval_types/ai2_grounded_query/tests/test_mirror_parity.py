"""Production replay gate for the grounded-query domain.

The domain still has a mirror for local scorer probes, but release evidence
must execute the real AI2 handoff entry.  A mirror result can never satisfy
this assertion.
"""

from pathlib import Path

from evals.release_verification import replay_grounded_query


def test_production_replay_is_not_mirror_only():
    fixture = Path(__file__).resolve().parents[4] / "ai-service" / "fixtures" / "eval_inputs" / "snapshots" / "ai1.full.v1.json"
    result = replay_grounded_query(fixture)
    assert result["status"] == "PASS", result
    assert result["parity_executed"] is True
    assert result["production_entry"] == "app.reasoning.stack.FourLayerReasoner.run"
    assert result["snapshot_id"] == "eval-full-v1"
