"""Embedding and egress gates keep a local job and score as expected.

EC-050 (embedding quota) stays BLOCKED. EC-055 (egress off) blocks external
calls only; the local job is NEEDS_REVIEW (ST-067/D-4).
"""

from fastapi.testclient import TestClient

from app.api.main import app
from fixtures.eval_suite import all_eval_cases
from scripts.live_eval import _evaluate_case


def test_ec050_and_ec055_match_when_local_job_succeeds():
    client = TestClient(app)
    cases = all_eval_cases()
    for case_id, expected_state in (("EC-050", "BLOCKED"), ("EC-055", "NEEDS_REVIEW")):
        for use_llm in (False, True):
            row, _review = _evaluate_case(
                client,
                cases[case_id],
                use_llm=use_llm,
                use_vector=False,
                run_label="live" if use_llm else "deterministic",
            )
            assert row["extract_http_ok"] is True
            assert row["actual_extract_state"] == expected_state
            assert row["expected_match"] is True
            assert row["forbidden_claims"] == []
